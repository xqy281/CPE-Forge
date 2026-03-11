"""
LLM 统一调用客户端单元测试

所有测试通过 Mock 隔离，不依赖真实 API Key。
"""
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from pipeline.llm_client import CPELLMClient


# ============================================================================
# 上下文动态组装测试
# ============================================================================

class TestBuildMessages:
    """消息组装功能测试"""

    def test_basic_message_assembly(self):
        """基本消息组装：system + user"""
        client = CPELLMClient(model="gpt-4o")
        messages = client.build_messages(
            system_prompt="你是一个分析师",
            user_content="这是周报内容"
        )
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "你是一个分析师"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "这是周报内容"

    def test_empty_system_prompt_omitted(self):
        """空 system prompt 时不生成 system 消息"""
        client = CPELLMClient()
        messages = client.build_messages(
            system_prompt="",
            user_content="用户内容"
        )
        assert len(messages) == 1
        assert messages[0]["role"] == "user"

    def test_long_markdown_content(self):
        """长文本 Markdown 内容应完整保留"""
        client = CPELLMClient()
        long_content = "# 标题\n" + "| 1 | 任务 | 100% | 分析 |\n" * 500
        messages = client.build_messages("系统提示", long_content)
        assert messages[1]["content"] == long_content


# ============================================================================
# JSON 解析容错测试
# ============================================================================

class TestParseJsonResponse:
    """JSON 解析容错功能测试"""

    def test_plain_json(self):
        """纯 JSON 字符串应直接解析"""
        result = CPELLMClient._parse_json_response('{"key": "value"}')
        assert result == {"key": "value"}

    def test_json_in_markdown_code_block(self):
        """Markdown 代码块包裹的 JSON 应正确提取"""
        raw = '```json\n{"radar_outer": {"score": 0.8}}\n```'
        result = CPELLMClient._parse_json_response(raw)
        assert result["radar_outer"]["score"] == 0.8

    def test_json_with_surrounding_text(self):
        """JSON 前后有多余文本时应正确提取"""
        raw = '分析结果如下：\n{"result": true}\n以上是分析。'
        result = CPELLMClient._parse_json_response(raw)
        assert result["result"] is True

    def test_json_with_trailing_comma(self):
        """含尾随逗号的 JSON 应容错处理"""
        raw = '{"a": 1, "b": 2,}'
        result = CPELLMClient._parse_json_response(raw)
        assert result == {"a": 1, "b": 2}

    def test_empty_content_raises(self):
        """空内容应抛异常"""
        with pytest.raises(ValueError, match="空内容"):
            CPELLMClient._parse_json_response("")

    def test_non_json_raises(self):
        """非 JSON 文本应抛异常"""
        with pytest.raises(ValueError, match="无法从 LLM 响应中解析"):
            CPELLMClient._parse_json_response("这不是json")

    def test_nested_json(self):
        """嵌套 JSON 应正确解析"""
        raw = json.dumps({
            "radar_outer": {"system_platform": 0.7, "driver": 0.5},
            "radar_inner": {"truth_seeking": {"level": 3, "evidence": ["证据1"]}}
        })
        result = CPELLMClient._parse_json_response(raw)
        assert result["radar_outer"]["system_platform"] == 0.7
        assert result["radar_inner"]["truth_seeking"]["level"] == 3


# ============================================================================
# 带重试的 LLM 调用测试
# ============================================================================

class TestCallWithRetry:
    """重试机制测试"""

    @patch("pipeline.llm_client.litellm.completion")
    def test_success_on_first_try(self, mock_completion):
        """首次调用成功时直接返回"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"result": "ok"}'
        mock_completion.return_value = mock_response

        client = CPELLMClient(model="gpt-4o")
        result = client.call("系统提示", "用户内容")
        assert result == {"result": "ok"}
        assert mock_completion.call_count == 1

    @patch("pipeline.llm_client.time.sleep")  # 不要真的等待
    @patch("pipeline.llm_client.litellm.completion")
    def test_retry_on_failure(self, mock_completion, mock_sleep):
        """首次失败后重试成功"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"result": "ok"}'

        mock_completion.side_effect = [
            Exception("API 超时"),
            mock_response,
        ]

        client = CPELLMClient(model="gpt-4o", max_retries=3)
        result = client.call("系统提示", "用户内容")
        assert result == {"result": "ok"}
        assert mock_completion.call_count == 2

    @patch("pipeline.llm_client.time.sleep")
    @patch("pipeline.llm_client.litellm.completion")
    def test_all_retries_exhausted_raises(self, mock_completion, mock_sleep):
        """所有重试耗尽后应抛异常"""
        mock_completion.side_effect = Exception("持续失败")

        client = CPELLMClient(model="gpt-4o", max_retries=2)
        with pytest.raises(RuntimeError, match="重试后仍失败"):
            client.call("系统提示", "用户内容")
        assert mock_completion.call_count == 2

    @patch("pipeline.llm_client.litellm.completion")
    def test_model_parameter_passed(self, mock_completion):
        """模型名称应正确传递给 litellm"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"ok": true}'
        mock_completion.return_value = mock_response

        client = CPELLMClient(model="deepseek/deepseek-chat", temperature=0.1)
        client.call("系统", "用户")
        call_kwargs = mock_completion.call_args
        assert call_kwargs.kwargs["model"] == "deepseek/deepseek-chat"
        assert call_kwargs.kwargs["temperature"] == 0.1


# ============================================================================
# Prompt 模板加载测试
# ============================================================================

class TestLoadPromptTemplate:
    """Prompt 模板加载测试"""

    def test_load_existing_file(self, tmp_path):
        """加载存在的 prompt 文件"""
        prompt_file = tmp_path / "test_prompt.md"
        prompt_file.write_text("你是资深分析师。\n## 任务\n提取画像", encoding="utf-8")

        content = CPELLMClient.load_prompt_template(prompt_file)
        assert "资深分析师" in content
        assert "提取画像" in content

    def test_load_nonexistent_file_raises(self):
        """加载不存在的文件应抛异常"""
        with pytest.raises(FileNotFoundError):
            CPELLMClient.load_prompt_template("/nonexistent/path.md")
