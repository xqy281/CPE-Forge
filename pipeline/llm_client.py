"""
LLM 统一调用客户端 — 基于 LiteLLM 封装

为 3.1 双层画像和 3.2 成长时间轴提供模型无关的 LLM 调用基座。
支持 OpenAI/Claude/DeepSeek/Gemini 等 100+ 模型一行切换。
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Optional

import litellm

logger = logging.getLogger(__name__)

# 关闭 litellm 的冗余日志，只保留警告以上
litellm.suppress_debug_info = True


class CPELLMClient:
    """
    CPE-Forge 专用的 LLM 统一调用客户端。

    基于 LiteLLM 封装，提供：
    - 多模型无缝切换
    - 上下文动态组装（system prompt + Markdown 周报内容）
    - JSON 格式输出的智能解析与容错
    - 带指数退避的重试机制
    - 从模型配置文件加载 temperature/top_p/api_key 等参数
    """

    def __init__(
        self,
        model: str = "deepseek/deepseek-chat",
        api_key: Optional[str] = None,
        temperature: float = 0.3,
        top_p: float = 1.0,
        max_tokens: int = 8192,
        max_retries: int = 3,
    ):
        """
        初始化 LLM 客户端。

        Args:
            model: LiteLLM 模型标识（如 "deepseek/deepseek-chat", "gpt-4o"）
            api_key: API Key，为 None 时从配置文件或环境变量自动读取
            temperature: 生成温度（0~2.0），越低越确定性
            top_p: 核采样参数（0~1.0），控制输出多样性
            max_tokens: 最大生成 Token 数
            max_retries: API 调用重试次数
        """
        self.model = model
        self.temperature = temperature
        self.top_p = top_p
        self.max_tokens = max_tokens
        self.max_retries = max_retries

        # 如果提供了 api_key，设置到环境变量供 litellm 使用
        if api_key:
            self._set_api_key(api_key)

    @classmethod
    def from_config(
        cls,
        model_id: str,
        config_dir: Optional[str | Path] = None,
    ) -> "CPELLMClient":
        """
        从模型配置文件创建客户端实例。

        优先读取 config/models/ 目录下的模型配置，
        若不存在则自动创建默认配置。

        Args:
            model_id: 模型标识
            config_dir: 配置文件目录（默认: config/models/）

        Returns:
            初始化好的 CPELLMClient 实例
        """
        from pipeline.llm_config import get_or_create_config, apply_config_to_env

        config = get_or_create_config(model_id, config_dir)

        # 将配置中的 API Key 应用到环境变量
        apply_config_to_env(config)

        return cls(
            model=config.model_id,
            temperature=config.temperature,
            top_p=config.top_p,
            max_tokens=config.max_tokens,
            max_retries=config.max_retries,
        )

    def _set_api_key(self, api_key: str):
        """根据模型前缀设置对应的环境变量"""
        prefix = self.model.split("/")[0] if "/" in self.model else self.model
        key_map = {
            "deepseek": "DEEPSEEK_API_KEY",
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "gemini": "GEMINI_API_KEY",
        }
        env_key = key_map.get(prefix, "OPENAI_API_KEY")
        os.environ[env_key] = api_key

    def build_messages(
        self,
        system_prompt: str,
        user_content: str,
    ) -> list[dict[str, str]]:
        """
        动态组装上下文消息数组。

        Args:
            system_prompt: System Prompt 文本
            user_content: 用户内容（Markdown 周报等）

        Returns:
            LLM 消息数组 [{"role": "system/user", "content": "..."}]
        """
        messages = []

        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt,
            })

        messages.append({
            "role": "user",
            "content": user_content,
        })

        return messages

    def call(
        self,
        system_prompt: str,
        user_content: str,
        parse_json: bool = True,
    ) -> dict[str, Any] | str:
        """
        发起 LLM 调用。

        Args:
            system_prompt: System Prompt（角色设定 + 任务描述 + 输出格式）
            user_content: 用户消息（Markdown 周报内容）
            parse_json: 是否尝试将响应解析为 JSON

        Returns:
            parse_json=True 时返回解析后的 dict，
            parse_json=False 时返回原始字符串

        Raises:
            RuntimeError: 重试耗尽后仍失败
        """
        messages = self.build_messages(system_prompt, user_content)
        return self.call_with_retry(messages, parse_json=parse_json)

    def call_with_retry(
        self,
        messages: list[dict[str, str]],
        parse_json: bool = True,
    ) -> dict[str, Any] | str:
        """
        带指数退避的重试 LLM 调用。

        Args:
            messages: 消息数组
            parse_json: 是否解析 JSON

        Returns:
            LLM 响应结果
        """
        last_error = None

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(
                    "调用 LLM [%s] (第 %d/%d 次, temp=%.2f, top_p=%.2f)...",
                    self.model, attempt, self.max_retries,
                    self.temperature, self.top_p,
                )

                response = litellm.completion(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                    top_p=self.top_p,
                    max_tokens=self.max_tokens,
                )

                raw_content = response.choices[0].message.content
                logger.info(
                    "LLM 响应成功，原始内容长度: %d 字符",
                    len(raw_content) if raw_content else 0
                )

                if parse_json:
                    return self._parse_json_response(raw_content)
                return raw_content

            except Exception as e:
                last_error = e
                wait_time = 2 ** attempt  # 指数退避: 2s, 4s, 8s
                logger.warning(
                    "LLM 调用失败 (第 %d/%d 次): %s. 等待 %ds 后重试...",
                    attempt, self.max_retries, str(e)[:200], wait_time
                )
                if attempt < self.max_retries:
                    time.sleep(wait_time)

        raise RuntimeError(
            f"LLM 调用在 {self.max_retries} 次重试后仍失败: {last_error}"
        )

    @staticmethod
    def _parse_json_response(raw_content: str) -> dict[str, Any]:
        """
        智能解析 LLM 返回的 JSON 内容。

        处理常见的格式问题：
        - 包裹在 ```json ... ``` Markdown 代码块中
        - 前后有多余文字或空白
        - JSON 中包含尾随逗号

        Args:
            raw_content: LLM 原始响应文本

        Returns:
            解析后的 dict

        Raises:
            ValueError: JSON 解析失败
        """
        if not raw_content:
            raise ValueError("LLM 返回空内容")

        text = raw_content.strip()

        # 尝试提取 ```json ... ``` 代码块
        json_block_match = re.search(
            r'```(?:json)?\s*\n?(.*?)\n?\s*```',
            text,
            re.DOTALL
        )
        if json_block_match:
            text = json_block_match.group(1).strip()

        # 尝试直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 尝试查找第一个 { 到最后一个 } 之间的内容
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            json_str = text[first_brace:last_brace + 1]
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass

            # 尝试移除尾随逗号后再解析
            cleaned = re.sub(r',\s*([}\]])', r'\1', json_str)
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                pass

        raise ValueError(
            f"无法从 LLM 响应中解析 JSON。原始内容前 500 字符: {raw_content[:500]}"
        )

    @staticmethod
    def load_prompt_template(prompt_path: str | Path) -> str:
        """
        从文件加载 System Prompt 模板。

        Args:
            prompt_path: Prompt 文件路径

        Returns:
            Prompt 文本内容

        Raises:
            FileNotFoundError: 文件不存在
        """
        path = Path(prompt_path)
        if not path.exists():
            raise FileNotFoundError(f"Prompt 模板文件不存在: {path}")

        return path.read_text(encoding="utf-8")
