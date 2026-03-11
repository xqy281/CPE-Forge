"""
FAQ 对话引擎单元测试 — PRD 3.3

通过 Mock LLM 调用验证：
1. 单轮对话
2. 多轮连续对话（历史累积）
3. reset() 清空历史
4. 历史导出
5. 溢出裁剪
6. API 层 start_chat_session / chat 集成测试
"""
from __future__ import annotations

import json
import pytest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

from pipeline.faq_chat import FAQChatEngine
from pipeline.models import SheetRecord, TaskRow, PlanRow
from pipeline.api import CPEPipelineAPI


# ============================================================================
# Fixtures
# ============================================================================

MOCK_MARKDOWN = """# 测试员 清洗后周报汇总

## 2025-01-06 ~ 2025-01-11

| 序号 | 任务描述 | 进度 | 难点分析 |
|------|----------|------|----------|
| 1 | WiFi驱动调试mt7993 | 80% | MTK SDK接口变更 |
| 2 | PCIe枚举失败定位 | 100% | BAR空间配置错误 |

## 2025-01-13 ~ 2025-01-17

| 序号 | 任务描述 | 进度 | 难点分析 |
|------|----------|------|----------|
| 1 | EMMC分区表优化 | 90% | 对齐4K扇区边界 |
"""

MOCK_FAQ_PROMPT = """你是团队内部顾问。

以下是周报数据：
{markdown_content}"""


@pytest.fixture
def mock_prompt_file(tmp_path):
    """创建mock FAQ prompt文件"""
    prompt_file = tmp_path / "faq_system.md"
    prompt_file.write_text(MOCK_FAQ_PROMPT, encoding="utf-8")
    return prompt_file


@pytest.fixture
def mock_client():
    """创建 Mock LLM 客户端"""
    client = MagicMock()
    # 默认返回一个简单回复
    client.call_with_retry.return_value = "根据周报记录，该员工主要负责WiFi驱动调试和PCIe问题定位。"
    return client


@pytest.fixture
def engine(mock_client, mock_prompt_file):
    """创建带 Mock 的 FAQ 引擎"""
    return FAQChatEngine(
        markdown_content=MOCK_MARKDOWN,
        llm_client=mock_client,
        prompt_path=mock_prompt_file,
        max_history_turns=5,
    )


# ============================================================================
# 测试 FAQChatEngine
# ============================================================================

class TestFAQChatEngine:
    """FAQ 对话引擎核心测试"""

    def test_single_turn_chat(self, engine, mock_client):
        """单轮对话：发送一个问题，应返回回复"""
        reply = engine.chat("这位员工主要负责什么？")

        assert reply == "根据周报记录，该员工主要负责WiFi驱动调试和PCIe问题定位。"
        assert engine.turn_count == 1

        # 验证 LLM 调用参数
        call_args = mock_client.call_with_retry.call_args
        messages = call_args[0][0]  # 第一个位置参数
        assert messages[0]["role"] == "system"
        assert "WiFi驱动调试mt7993" in messages[0]["content"]  # 上下文已注入
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "这位员工主要负责什么？"

    def test_multi_turn_chat(self, engine, mock_client):
        """多轮连续对话：历史消息应累积"""
        # 第一轮
        mock_client.call_with_retry.return_value = "主要方向是WiFi和PCIe。"
        engine.chat("主要技术方向？")

        # 第二轮
        mock_client.call_with_retry.return_value = "WiFi方面遇到了MTK SDK接口变更的问题。"
        reply2 = engine.chat("WiFi方面有什么难题？")

        assert engine.turn_count == 2

        # 验证第二次调用包含第一轮对话历史
        call_args = mock_client.call_with_retry.call_args
        messages = call_args[0][0]
        # system(1) + 第一轮 user(1) + 第一轮 assistant(1) + 第二轮 user(1) = 4 条
        assert len(messages) == 4
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "主要技术方向？"
        assert messages[2]["role"] == "assistant"
        assert messages[2]["content"] == "主要方向是WiFi和PCIe。"
        assert messages[3]["role"] == "user"
        assert messages[3]["content"] == "WiFi方面有什么难题？"

    def test_reset_clears_history(self, engine, mock_client):
        """reset() 应清空所有对话历史"""
        engine.chat("问题1")
        engine.chat("问题2")
        assert engine.turn_count == 2

        engine.reset()
        assert engine.turn_count == 0
        assert engine.get_history() == []

        # reset 后新对话不应包含旧历史
        engine.chat("问题3")
        call_args = mock_client.call_with_retry.call_args
        messages = call_args[0][0]
        # 仅 system(1) + 当前 user(1) = 2 条
        assert len(messages) == 2

    def test_get_history(self, engine, mock_client):
        """get_history() 应返回完整的对话记录"""
        mock_client.call_with_retry.return_value = "回复1"
        engine.chat("问题1")
        mock_client.call_with_retry.return_value = "回复2"
        engine.chat("问题2")

        history = engine.get_history()
        assert len(history) == 4  # 2轮 × 2条
        assert history[0] == {"role": "user", "content": "问题1"}
        assert history[1] == {"role": "assistant", "content": "回复1"}
        assert history[2] == {"role": "user", "content": "问题2"}
        assert history[3] == {"role": "assistant", "content": "回复2"}

    def test_history_overflow_trimming(self, mock_client, mock_prompt_file):
        """超过 max_history_turns 时应裁剪最早的对话"""
        engine = FAQChatEngine(
            markdown_content=MOCK_MARKDOWN,
            llm_client=mock_client,
            prompt_path=mock_prompt_file,
            max_history_turns=2,  # 只保留2轮
        )

        mock_client.call_with_retry.return_value = "回复"
        engine.chat("问题1")
        engine.chat("问题2")
        engine.chat("问题3")  # 第3轮，应裁剪第1轮

        assert engine.turn_count == 2  # 保留最近2轮
        history = engine.get_history()
        assert history[0]["content"] == "问题2"  # 最早的应该是第2轮
        assert history[2]["content"] == "问题3"

    def test_empty_message_returns_hint(self, engine):
        """空消息不应调用 LLM"""
        reply = engine.chat("   ")
        assert "请输入" in reply
        assert engine.turn_count == 0

    def test_system_prompt_contains_context(self, engine):
        """System Prompt 应包含注入的周报内容"""
        assert "WiFi驱动调试mt7993" in engine.system_prompt
        assert "PCIe枚举失败定位" in engine.system_prompt
        assert "EMMC分区表优化" in engine.system_prompt


# ============================================================================
# 测试 API 层集成
# ============================================================================

def _make_cached_employee(output_dir: Path, email: str = "test@jointelli.com"):
    """构造缓存数据"""
    cache_dir = output_dir / "cache" / email
    cache_dir.mkdir(parents=True)
    records = [
        SheetRecord(
            employee_name="测试员",
            employee_email=email,
            source_file=Path("dummy.xlsx"),
            sheet_name="Sheet1",
            date_range=(date(2025, 1, 6), date(2025, 1, 11)),
            tasks=[TaskRow(1, "WiFi驱动调试", 0.8, "SDK变更")],
            plans=[],
        ),
    ]
    with open(cache_dir / "_meta.json", "w", encoding="utf-8") as f:
        json.dump([r.to_dict() for r in records], f, ensure_ascii=False)
    return email


class TestFAQChatAPI:
    """API 层 FAQ 对话集成测试"""

    @pytest.fixture
    def api_env(self, tmp_path):
        """构造 API 测试环境"""
        attachments_dir = tmp_path / "attachments"
        attachments_dir.mkdir()
        (attachments_dir / "test@jointelli.com").mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        email = _make_cached_employee(output_dir, "test@jointelli.com")
        api = CPEPipelineAPI(attachments_dir, output_dir)
        return api, email

    @patch("pipeline.api.CPELLMClient")
    def test_start_chat_session(self, mock_client_cls, api_env):
        """start_chat_session 应返回 session_id"""
        api, email = api_env
        mock_client = MagicMock()
        mock_client_cls.from_config.return_value = mock_client

        session_id = api.start_chat_session(
            email=email,
            date_range_ids=["2025-01-06_2025-01-11"],
            model_id="deepseek/deepseek-chat",
        )

        assert isinstance(session_id, str)
        assert len(session_id) > 0

    @patch("pipeline.api.CPELLMClient")
    def test_chat_returns_reply(self, mock_client_cls, api_env):
        """chat 应返回助手回复"""
        api, email = api_env
        mock_client = MagicMock()
        mock_client.call_with_retry.return_value = "这位员工主要负责WiFi。"
        mock_client_cls.from_config.return_value = mock_client

        session_id = api.start_chat_session(email, ["2025-01-06_2025-01-11"], "deepseek/deepseek-chat")
        result = api.chat(session_id, "这位员工负责什么？")

        assert result["role"] == "assistant"
        assert "WiFi" in result["content"]

    @patch("pipeline.api.CPELLMClient")
    def test_get_chat_history(self, mock_client_cls, api_env):
        """get_chat_history 应返回完整对话记录"""
        api, email = api_env
        mock_client = MagicMock()
        mock_client.call_with_retry.return_value = "回复内容"
        mock_client_cls.from_config.return_value = mock_client

        session_id = api.start_chat_session(email, ["2025-01-06_2025-01-11"], "deepseek/deepseek-chat")
        api.chat(session_id, "问题1")
        api.chat(session_id, "问题2")

        history = api.get_chat_history(session_id)
        assert len(history) == 4  # 2轮 x 2条
