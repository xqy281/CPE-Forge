"""
成长时间轴分析器单元测试

所有 LLM 调用均通过 Mock 隔离，不依赖真实 API Key。
"""
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from pipeline.growth_analyzer import (
    analyze_growth,
    _validate_growth_result,
    _validate_issue,
    _validate_recursive_logic,
    _validate_recurring_pattern,
)
from pipeline.llm_client import CPELLMClient


# ============================================================================
# 模拟的 LLM 返回结果
# ============================================================================

_MOCK_VALID_RESULT = {
    "closed_loop_issues": [
        {
            "title": "M05 phy口芯片挂死问题",
            "first_appeared": "2025-01-12",
            "resolved_date": "2025-01-31",
            "duration_weeks": 3,
            "status": "resolved",
            "timeline": [
                {"date": "2025-01-12~2025-01-17", "progress": "80%", "description": "定位网口异常..."},
                {"date": "2025-01-26~2025-01-31", "progress": "100%", "description": "原厂patch修复"},
            ],
            "root_cause": "RJ45外部周期波动导致phy芯片扛不住冲击",
            "solution": "原厂patch修复",
            "tags": ["硬件问题", "PHY驱动"],
        }
    ],
    "growth_analysis": {
        "recursive_logic": [
            {
                "task_name": "M05 phy口芯片挂死",
                "pattern": "depth_first",
                "reasoning_chain": ["排除网线因素", "确认RJ45根因"],
                "label": "深度递进/求真严谨",
                "evidence_period": "2025-01-12~2025-01-31",
            }
        ]
    },
}


# ============================================================================
# System Prompt 加载测试
# ============================================================================

class TestGrowthPromptLoading:
    """Growth System Prompt 文件加载测试"""

    def test_default_prompt_exists(self):
        """默认的 growth_system.md 文件应存在"""
        prompt_path = Path(__file__).resolve().parent.parent / "prompts" / "growth_system.md"
        assert prompt_path.exists()

    def test_default_prompt_contains_key_sections(self):
        """默认 prompt 应包含闭环追踪和递进分析"""
        prompt_path = Path(__file__).resolve().parent.parent / "prompts" / "growth_system.md"
        content = prompt_path.read_text(encoding="utf-8")
        assert "闭环追踪" in content
        assert "closed_loop_issues" in content
        assert "depth_first" in content

    def test_prompt_contains_quality_and_patterns(self):
        """改进后的 prompt 应包含闭环质量和反复修补模式"""
        prompt_path = Path(__file__).resolve().parent.parent / "prompts" / "growth_system.md"
        content = prompt_path.read_text(encoding="utf-8")
        assert "closure_quality" in content, "缺少闭环质量字段"
        assert "root_fix" in content, "缺少 root_fix 闭环质量等级"
        assert "workaround" in content, "缺少 workaround 闭环质量等级"
        assert "surface_patch" in content, "缺少 surface_patch 中间模式"
        assert "recurring_fix_patterns" in content, "缺少反复修补模式"
        assert "has_refactor" in content, "缺少重构标记字段"


# ============================================================================
# 闭环问题校验测试
# ============================================================================

class TestValidateIssue:
    """单个闭环问题校验"""

    def test_complete_issue_passes(self):
        """完整的问题记录应通过"""
        issue = _validate_issue(_MOCK_VALID_RESULT["closed_loop_issues"][0].copy())
        assert issue["title"] == "M05 phy口芯片挂死问题"
        assert issue["duration_weeks"] == 3
        assert len(issue["timeline"]) == 2

    def test_missing_fields_filled(self):
        """缺失字段应自动补充默认值"""
        issue = _validate_issue({"title": "测试"})
        assert issue["first_appeared"] == ""
        assert issue["resolved_date"] is None
        assert issue["tags"] == []
        assert issue["timeline"] == []

    def test_invalid_duration_fixed(self):
        """非法 duration_weeks 应被修正"""
        issue = _validate_issue({"duration_weeks": "abc"})
        assert issue["duration_weeks"] == 0

    def test_closure_quality_default(self):
        """缺失 closure_quality 应自动补充空字符串"""
        issue = _validate_issue({"title": "测试"})
        assert issue["closure_quality"] == ""

    def test_valid_closure_quality_passes(self):
        """合法的 closure_quality 值应通过"""
        for quality in ["root_fix", "systematic_fix", "workaround", "escalated", "inconclusive"]:
            issue = _validate_issue({"closure_quality": quality})
            assert issue["closure_quality"] == quality

    def test_invalid_closure_quality_reset(self):
        """非法 closure_quality 应被重置为空字符串"""
        issue = _validate_issue({"closure_quality": "invalid_value"})
        assert issue["closure_quality"] == ""


# ============================================================================
# 递进分析校验测试
# ============================================================================

class TestValidateRecursiveLogic:
    """递进分析记录校验"""

    def test_valid_depth_first(self):
        """合法的深度递进记录应通过"""
        item = _validate_recursive_logic({
            "task_name": "测试任务",
            "pattern": "depth_first",
            "reasoning_chain": ["步骤1", "步骤2"],
            "label": "深度递进",
        })
        assert item["pattern"] == "depth_first"
        assert len(item["reasoning_chain"]) == 2

    def test_invalid_pattern_reset(self):
        """非法 pattern 值应被重置为 unknown"""
        item = _validate_recursive_logic({"pattern": "invalid"})
        assert item["pattern"] == "unknown"

    def test_surface_patch_pattern_valid(self):
        """surface_patch 应为合法的 pattern 值"""
        item = _validate_recursive_logic({"pattern": "surface_patch"})
        assert item["pattern"] == "surface_patch"

    def test_missing_fields_filled(self):
        """缺失字段应补充默认值"""
        item = _validate_recursive_logic({})
        assert item["task_name"] == ""
        assert item["reasoning_chain"] == []


# ============================================================================
# 完整结果校验测试
# ============================================================================

class TestValidateGrowthResult:
    """完整成长分析结果校验"""

    def test_valid_result_passes(self):
        """合法的完整结果应通过"""
        result = _validate_growth_result(_MOCK_VALID_RESULT.copy())
        assert len(result["closed_loop_issues"]) == 1
        assert len(result["growth_analysis"]["recursive_logic"]) == 1

    def test_missing_sections_filled(self):
        """缺失的顶层字段应补充"""
        result = _validate_growth_result({})
        assert result["closed_loop_issues"] == []
        assert result["growth_analysis"]["recursive_logic"] == []
        assert result["growth_analysis"]["recurring_fix_patterns"] == []

    def test_invalid_issues_type_fixed(self):
        """非列表的 issues 应修正"""
        result = _validate_growth_result({"closed_loop_issues": "not a list"})
        assert result["closed_loop_issues"] == []


# ============================================================================
# 端到端流程测试（Mock LLM）
# ============================================================================

class TestAnalyzeGrowth:
    """成长分析端到端流程测试"""

    @patch.object(CPELLMClient, "call")
    def test_analyze_growth_success(self, mock_call, tmp_path):
        """正常流程：加载 prompt → 调用 LLM → 解析结果"""
        mock_call.return_value = _MOCK_VALID_RESULT.copy()

        prompt_file = tmp_path / "test_growth.md"
        prompt_file.write_text("你是分析师", encoding="utf-8")

        client = CPELLMClient(model="gpt-4o")
        result = analyze_growth(
            markdown_content="# 测试周报",
            llm_client=client,
            prompt_path=prompt_file,
        )
        assert len(result["closed_loop_issues"]) == 1
        assert result["closed_loop_issues"][0]["title"] == "M05 phy口芯片挂死问题"
        mock_call.assert_called_once()

    @patch.object(CPELLMClient, "call")
    def test_analyze_growth_with_default_prompt(self, mock_call):
        """使用默认 prompt 文件的正常流程"""
        mock_call.return_value = _MOCK_VALID_RESULT.copy()

        client = CPELLMClient(model="gpt-4o")
        result = analyze_growth(
            markdown_content="# 测试",
            llm_client=client,
        )
        assert "closed_loop_issues" in result
        assert "growth_analysis" in result


# ============================================================================
# 反复修补模式校验测试
# ============================================================================

class TestValidateRecurringPattern:
    """反复修补模式记录校验"""

    def test_valid_pattern(self):
        """合法的反复修补记录应通过"""
        item = _validate_recurring_pattern({
            "module_name": "mesh组网",
            "fix_count": 15,
            "span_weeks": 20,
            "has_refactor": False,
            "summary": "跨20周反复修补",
        })
        assert item["module_name"] == "mesh组网"
        assert item["fix_count"] == 15
        assert item["has_refactor"] is False

    def test_missing_fields_filled(self):
        """缺失字段应补充默认值"""
        item = _validate_recurring_pattern({})
        assert item["module_name"] == ""
        assert item["fix_count"] == 0
        assert item["span_weeks"] == 0
        assert item["has_refactor"] is False
        assert item["summary"] == ""

    def test_invalid_fix_count_fixed(self):
        """非法 fix_count 应被修正"""
        item = _validate_recurring_pattern({"fix_count": "abc"})
        assert item["fix_count"] == 0

