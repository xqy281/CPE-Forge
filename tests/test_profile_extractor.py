"""
双层能力画像提取器单元测试

所有 LLM 调用均通过 Mock 隔离，不依赖真实 API Key。
"""
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from pipeline.profile_extractor import extract_profile, _validate_profile_result
from pipeline.llm_client import CPELLMClient


# ============================================================================
# 模拟的 LLM 返回结果（双轨制格式）
# ============================================================================

_MOCK_VALID_RESULT = {
    "radar_outer": {
        "system_platform": {"proportion": 0.25, "depth": 3},
        "driver_development": {"proportion": 0.20, "depth": 4},
        "application_software": {"proportion": 0.15, "depth": 2},
        "wireless_communication": {"proportion": 0.30, "depth": 5},
        "sqa_quality": {"proportion": 0.10, "depth": 3},
    },
    "radar_inner": {
        "truth_seeking": {
            "level": 4,
            "score": 0.8,
            "evidence": [
                "【2025-01-12~01-17】定位网口异常源自RJ45输入",
                "【2025-02-02~02-13】检查mdio总线上拉电阻，这就是根因",
            ],
        },
        "pragmatic": {
            "level": 3,
            "score": 0.6,
            "evidence": ["【2025-01-26~01-31】经过1200次+压测无异常"],
        },
        "rigorous": {
            "level": 3,
            "score": 0.65,
            "evidence": ["【2025-03-10~03-15】内存泄露为突发式行为，定位在mesh协议栈"],
        },
    },
    "summary": "该工程师在无线通信和系统平台方面投入最多，具有较强的根因定位能力。",
}


# ============================================================================
# System Prompt 加载测试
# ============================================================================

class TestPromptLoading:
    """System Prompt 文件加载测试"""

    def test_default_prompt_exists(self):
        """默认的 profile_system.md 文件应存在"""
        prompt_path = Path(__file__).resolve().parent.parent / "prompts" / "profile_system.md"
        assert prompt_path.exists(), f"默认 prompt 文件不存在: {prompt_path}"

    def test_default_prompt_contains_key_sections(self):
        """默认 prompt 应包含角色设定和双轨制关键词"""
        prompt_path = Path(__file__).resolve().parent.parent / "prompts" / "profile_system.md"
        content = prompt_path.read_text(encoding="utf-8")
        assert "角色设定" in content
        assert "radar_outer" in content
        assert "radar_inner" in content
        assert "proportion" in content
        assert "depth" in content

    def test_prompt_contains_anti_pattern_framework(self):
        """改进后的 prompt 应包含反模式检测框架关键段落"""
        prompt_path = Path(__file__).resolve().parent.parent / "prompts" / "profile_system.md"
        content = prompt_path.read_text(encoding="utf-8")
        # 自我美化偏差警告
        assert "自我美化偏差" in content, "缺少自我美化偏差警告段落"
        # 反模式信号词典
        assert "反模式信号词典" in content, "缺少反模式信号词典"
        assert "阻塞式补丁" in content, "缺少阻塞式补丁反模式"
        assert "关注点耦合" in content, "缺少关注点耦合反模式"
        assert "延时调参法" in content, "缺少延时调参法反模式"
        # 正负向证据标记
        assert "[+]" in content, "缺少正向证据标记 [+]"
        assert "[-]" in content, "缺少负向证据标记 [-]"
        # 严谨维度 Lv4 锚定
        assert "重构" in content and "解耦" in content, "严谨 Lv4 应要求重构/解耦证据"


# ============================================================================
# 格式校验测试
# ============================================================================

class TestValidateProfileResult:
    """画像结果格式校验测试"""

    def test_valid_result_passes(self):
        """合法的双轨制结果应直接通过"""
        import copy
        result = _validate_profile_result(copy.deepcopy(_MOCK_VALID_RESULT))
        assert "radar_outer" in result
        assert "radar_inner" in result
        outer = result["radar_outer"]["system_platform"]
        assert outer["proportion"] == 0.25
        assert outer["depth"] == 3

    def test_missing_outer_dim_filled(self):
        """缺失的外层维度应自动补充默认双轨值"""
        result = _validate_profile_result({
            "radar_outer": {
                "system_platform": {"proportion": 0.5, "depth": 4},
            },
            "radar_inner": {},
        })
        dd = result["radar_outer"]["driver_development"]
        assert dd["proportion"] == 0.0
        assert dd["depth"] == 0
        assert result["radar_outer"]["system_platform"]["proportion"] > 0

    def test_missing_inner_dim_filled(self):
        """缺失的内层维度应自动补充默认值"""
        result = _validate_profile_result({
            "radar_outer": {},
            "radar_inner": {"truth_seeking": {"level": 3, "score": 0.7, "evidence": []}},
        })
        assert result["radar_inner"]["pragmatic"]["level"] == 1
        assert result["radar_inner"]["rigorous"]["score"] == 0.0

    def test_outer_proportion_normalization(self):
        """外层 proportion 权重和偏差超过 5% 时应归一化"""
        result = _validate_profile_result({
            "radar_outer": {
                "system_platform": {"proportion": 5.0, "depth": 4},
                "driver_development": {"proportion": 3.0, "depth": 3},
                "application_software": {"proportion": 2.0, "depth": 2},
                "wireless_communication": {"proportion": 0.0, "depth": 0},
                "sqa_quality": {"proportion": 0.0, "depth": 0},
            },
            "radar_inner": {},
        })
        total = sum(
            entry["proportion"]
            for entry in result["radar_outer"].values()
            if isinstance(entry, dict)
        )
        assert abs(total - 1.0) < 0.01

    def test_depth_clamped_to_range(self):
        """外层 depth 应被限制在 0~5 范围内"""
        result = _validate_profile_result({
            "radar_outer": {
                "system_platform": {"proportion": 0.5, "depth": 10},
                "driver_development": {"proportion": 0.5, "depth": -3},
            },
            "radar_inner": {},
        })
        assert result["radar_outer"]["system_platform"]["depth"] == 5
        assert result["radar_outer"]["driver_development"]["depth"] == 0

    def test_legacy_float_format_converted(self):
        """旧格式纯浮点数应自动转换为双轨结构"""
        result = _validate_profile_result({
            "radar_outer": {
                "system_platform": 0.30,
                "driver_development": 0.40,
                "application_software": 0.10,
                "wireless_communication": 0.15,
                "sqa_quality": 0.05,
            },
            "radar_inner": {},
        })
        sp = result["radar_outer"]["system_platform"]
        assert isinstance(sp, dict)
        assert "proportion" in sp
        assert "depth" in sp
        assert sp["proportion"] == 0.30

    def test_level_clamped_to_range(self):
        """内层 level 应被限制在 1~5 范围内"""
        result = _validate_profile_result({
            "radar_outer": {},
            "radar_inner": {
                "truth_seeking": {"level": 10, "score": 0.5, "evidence": []},
                "pragmatic": {"level": -1, "score": 0.3, "evidence": []},
                "rigorous": {"level": 3, "score": 0.6, "evidence": []},
            },
        })
        assert result["radar_inner"]["truth_seeking"]["level"] == 5
        assert result["radar_inner"]["pragmatic"]["level"] == 1

    def test_summary_default(self):
        """缺少 summary 字段时应补充空字符串"""
        result = _validate_profile_result({"radar_outer": {}, "radar_inner": {}})
        assert "summary" in result


# ============================================================================
# 端到端流程测试（Mock LLM）
# ============================================================================

class TestExtractProfile:
    """画像提取端到端流程测试"""

    @patch.object(CPELLMClient, "call")
    def test_extract_profile_success(self, mock_call, tmp_path):
        """正常流程：加载 prompt → 调用 LLM → 解析结果"""
        import copy
        mock_call.return_value = copy.deepcopy(_MOCK_VALID_RESULT)

        # 创建临时 prompt 文件
        prompt_file = tmp_path / "test_profile.md"
        prompt_file.write_text("你是分析师\n## 输出JSON", encoding="utf-8")

        client = CPELLMClient(model="gpt-4o")
        result = extract_profile(
            markdown_content="# 测试\n| 1 | 任务 | 100% | 分析 |",
            llm_client=client,
            prompt_path=prompt_file,
        )
        assert result["radar_outer"]["wireless_communication"]["proportion"] == 0.30
        assert result["radar_outer"]["wireless_communication"]["depth"] == 5
        assert result["radar_inner"]["truth_seeking"]["level"] == 4
        mock_call.assert_called_once()

    @patch.object(CPELLMClient, "call")
    def test_extract_profile_with_default_prompt(self, mock_call):
        """使用默认 prompt 文件的正常流程"""
        import copy
        mock_call.return_value = copy.deepcopy(_MOCK_VALID_RESULT)

        client = CPELLMClient(model="gpt-4o")
        result = extract_profile(
            markdown_content="# 测试内容",
            llm_client=client,
        )
        assert "radar_outer" in result
