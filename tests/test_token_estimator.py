"""
Token 预估模块单元测试

覆盖范围：
- Token 计数准确性
- 水位线判定（绿/黄/红三级别）
- 模型上下文限制获取
- 边界情况（空文本、超长文本）
"""
import pytest
from pipeline.token_estimator import (
    count_tokens,
    assess_token_level,
    get_model_context_limit,
    estimate_markdown_tokens,
    TokenEstimate,
    TokenLevel,
)


# ============================================================================
# Token 计数准确性测试
# ============================================================================

class TestCountTokens:
    """Token 计数功能测试"""

    def test_english_text_token_count(self):
        """英文文本 Token 计数应在合理范围内"""
        text = "Hello, world! This is a test sentence."
        count = count_tokens(text)
        # 英文句子每个单词大约1个token，标点也占位
        assert 5 < count < 20

    def test_chinese_text_token_count(self):
        """中文文本 Token 计数应合理（中文字符通常1~2 token/字）"""
        text = "这是一段中文测试文本，用于验证Token计算的准确性。"
        count = count_tokens(text)
        # 中文字符在tiktoken中通常每字1~3个token
        assert count > 5

    def test_empty_text_returns_zero(self):
        """空文本应返回 0 Token"""
        assert count_tokens("") == 0
        assert count_tokens("   ") >= 0  # 空白字符可能有或无token

    def test_markdown_table_token_count(self):
        """Markdown 表格格式文本的 Token 计数"""
        markdown = (
            "| 序号 | 任务描述 | 进度 | 难点分析 |\n"
            "|------|----------|------|----------|\n"
            "| 1 | T830平台处理V18固件压测问题 | 80% | 定位网口异常 |\n"
        )
        count = count_tokens(markdown)
        assert count > 10  # 表格中有大量字符

    def test_large_text_token_count(self):
        """较大文本的 Token 计数性能与准确性"""
        text = "这是一段重复文本。" * 1000  # ~8000字符
        count = count_tokens(text)
        assert count > 500


# ============================================================================
# 水位线判定测试
# ============================================================================

class TestAssessTokenLevel:
    """水位线判定功能测试"""

    def test_green_level(self):
        """Token 数 < 50k 应判定为绿色"""
        result = assess_token_level(30000)
        assert result == TokenLevel.GREEN

    def test_yellow_level(self):
        """Token 数 50k~100k 应判定为黄色"""
        result = assess_token_level(75000)
        assert result == TokenLevel.YELLOW

    def test_red_level_exceed_100k(self):
        """Token 数 > 100k 应判定为红色"""
        result = assess_token_level(150000)
        assert result == TokenLevel.RED

    def test_boundary_50k(self):
        """边界值：恰好 50000 应判定为黄色"""
        result = assess_token_level(50000)
        assert result == TokenLevel.YELLOW

    def test_boundary_100k(self):
        """边界值：恰好 100000 应判定为红色"""
        result = assess_token_level(100000)
        assert result == TokenLevel.RED

    def test_zero_tokens(self):
        """0 Token 应判定为绿色"""
        result = assess_token_level(0)
        assert result == TokenLevel.GREEN

    def test_custom_model_limit(self):
        """自定义模型上限时超限应判定为红色"""
        # 模型上限 32k 的情况下 35000 token 应为红色
        result = assess_token_level(35000, model_context_limit=32000)
        assert result == TokenLevel.RED


# ============================================================================
# 模型上下文限制获取测试
# ============================================================================

class TestGetModelContextLimit:
    """模型上下文限制获取测试"""

    def test_known_model_returns_positive_limit(self):
        """已知模型应返回正整数上下文限制"""
        limit = get_model_context_limit("gpt-4o")
        assert limit > 0

    def test_unknown_model_returns_default(self):
        """未知模型应返回默认限制值"""
        limit = get_model_context_limit("unknown-model-xyz")
        assert limit > 0  # 应有默认值，不报错

    def test_deepseek_model_limit(self):
        """DeepSeek 模型应返回合理的上下文限制"""
        limit = get_model_context_limit("deepseek/deepseek-chat")
        assert limit >= 64000  # DeepSeek 支持 64k+


# ============================================================================
# 综合预估测试
# ============================================================================

class TestEstimateMarkdownTokens:
    """Markdown 文本综合 Token 预估"""

    def test_basic_estimate(self):
        """基本预估结果应包含完整字段"""
        text = "# 测试标题\n\n这是测试内容。" * 10
        result = estimate_markdown_tokens(text)
        assert isinstance(result, TokenEstimate)
        assert result.token_count > 0
        assert result.level in (TokenLevel.GREEN, TokenLevel.YELLOW, TokenLevel.RED)
        assert result.model_limit > 0
        assert 0 <= result.utilization_pct <= 200  # 可能超过100%

    def test_estimate_with_model(self):
        """指定模型的预估应正常工作"""
        text = "# 测试\n内容"
        result = estimate_markdown_tokens(text, model="gpt-4o")
        assert result.token_count > 0

    def test_estimate_empty_text(self):
        """空文本预估结果"""
        result = estimate_markdown_tokens("")
        assert result.token_count == 0
        assert result.level == TokenLevel.GREEN

    def test_estimate_level_display_name(self):
        """水位线级别应有可读的中文显示名"""
        assert TokenLevel.GREEN.label == "绿色"
        assert TokenLevel.YELLOW.label == "黄色"
        assert TokenLevel.RED.label == "红色"
