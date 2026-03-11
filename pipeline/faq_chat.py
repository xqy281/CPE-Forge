"""
全量上下文 FAQ 智能对话引擎 — PRD 3.3

核心设计：
- 弃用 RAG，将员工全量清洗后 Markdown 周报作为 System Prompt 的上下文注入
- 维护多轮对话历史（Message History Array），支持连续追问
- Token 溢出保护：当历史过长时自动裁剪最早轮次
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from pipeline.llm_client import CPELLMClient

logger = logging.getLogger(__name__)

# FAQ System Prompt 模板默认路径
_DEFAULT_FAQ_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "faq_system.md"

# 单轮对话（user + assistant）大约消耗的 Token 最大预估
_MAX_HISTORY_TURNS = 20


class FAQChatEngine:
    """
    全量上下文 FAQ 对话引擎。

    将员工的全量清洗后 Markdown 周报注入 System Prompt，
    维护多轮对话历史，支持连续追问。

    面向 Web UI 设计：
    - session_id 标识每个独立会话
    - get_history() 导出完整对话记录供前端渲染
    - reset() 清空历史开始新对话
    """

    def __init__(
        self,
        markdown_content: str,
        llm_client: CPELLMClient,
        prompt_path: str | Path | None = None,
        max_history_turns: int = _MAX_HISTORY_TURNS,
    ):
        """
        初始化 FAQ 对话引擎。

        Args:
            markdown_content: 清洗后的 Markdown 周报全文（作为上下文注入）
            llm_client: 已初始化的 LLM 客户端
            prompt_path: FAQ System Prompt 模板路径（为 None 时使用默认路径）
            max_history_turns: 最大保留对话轮次（超过后裁剪最早的）
        """
        self.llm_client = llm_client
        self.max_history_turns = max_history_turns
        self.session_id = str(uuid.uuid4())
        self.created_at = datetime.now().isoformat()

        # 加载并组装 System Prompt（将周报内容注入模板）
        path = Path(prompt_path) if prompt_path else _DEFAULT_FAQ_PROMPT_PATH
        template = CPELLMClient.load_prompt_template(path)
        self.system_prompt = template.replace("{markdown_content}", markdown_content)
        logger.info(
            "FAQ 对话引擎初始化完成 (session=%s, 上下文 %d 字符, System Prompt %d 字符)",
            self.session_id[:8], len(markdown_content), len(self.system_prompt),
        )

        # 对话历史：仅存储 user/assistant 消息，system 消息每次调用时重新注入
        self._history: list[dict[str, str]] = []

    def chat(self, user_message: str) -> str:
        """
        发送用户消息并获取助手回复。

        自动将用户消息和助手回复追加到对话历史，
        下次调用时会携带完整历史上下文。

        Args:
            user_message: 用户输入的问题

        Returns:
            助手的回复文本

        Raises:
            RuntimeError: LLM 调用失败
        """
        if not user_message.strip():
            return "请输入您的问题。"

        # 1. 构建完整消息数组：system + history + 当前 user
        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(self._history)
        messages.append({"role": "user", "content": user_message})

        # 2. 调用 LLM（不解析 JSON，原样返回文本）
        logger.info("FAQ 对话: 发送消息 (%d 字符), 历史 %d 轮", len(user_message), len(self._history) // 2)
        response = self.llm_client.call_with_retry(messages, parse_json=False)

        # 3. 追加到对话历史
        self._history.append({"role": "user", "content": user_message})
        self._history.append({"role": "assistant", "content": response})

        # 4. 超出轮次上限时裁剪最早的对话（每轮 = 2 条消息）
        max_messages = self.max_history_turns * 2
        if len(self._history) > max_messages:
            trimmed = len(self._history) - max_messages
            self._history = self._history[trimmed:]
            logger.info("对话历史已裁剪 %d 条消息（保留最近 %d 轮）", trimmed, self.max_history_turns)

        return response

    def reset(self):
        """清空对话历史，开始新会话。"""
        old_count = len(self._history)
        self._history.clear()
        self.session_id = str(uuid.uuid4())
        logger.info("对话历史已重置 (清除 %d 条消息, 新 session=%s)", old_count, self.session_id[:8])

    def get_history(self) -> list[dict[str, Any]]:
        """
        导出完整对话历史，面向 Web UI 渲染。

        Returns:
            对话记录列表，每条含 role / content 字段
        """
        return [
            {"role": msg["role"], "content": msg["content"]}
            for msg in self._history
        ]

    @property
    def turn_count(self) -> int:
        """当前已完成的对话轮次（1轮 = user + assistant 各1条）"""
        return len(self._history) // 2
