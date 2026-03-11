"""
集成 API 单元测试 — 数据清洗管线 + LLM 分析管线的串联测试

通过 Mock LLM 调用验证：
1. run_full_analysis 完整流程
2. run_profile_only / run_growth_only 独立入口
3. AnalysisResult 序列化/反序列化
4. 缓存命中与未命中路径
5. 异常输入容错
"""
from __future__ import annotations

import json
import pytest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from pipeline.models import (
    SheetRecord, TaskRow, PlanRow, AnalysisResult
)
from pipeline.api import CPEPipelineAPI


# ============================================================================
# Fixtures：构造测试用的缓存数据
# ============================================================================

def _make_cached_employee(output_dir: Path, email: str = "test@jointelli.com"):
    """在 output_dir 下构造带缓存的员工数据"""
    cache_dir = output_dir / "cache" / email
    cache_dir.mkdir(parents=True)

    records = [
        SheetRecord(
            employee_name="测试员",
            employee_email=email,
            source_file=Path("dummy.xlsx"),
            sheet_name="Sheet1",
            date_range=(date(2025, 1, 6), date(2025, 1, 11)),
            tasks=[
                TaskRow(1, "WiFi驱动调试mt7993", 0.8, "MTK SDK接口变更"),
                TaskRow(2, "PCIe枚举失败定位", 1.0, "BAR空间配置错误"),
            ],
            plans=[PlanRow(1, "继续WiFi调试", "一周", "")],
            raw_text="WiFi驱动调试mt7993 PCIe枚举",
            char_count=50,
        ),
        SheetRecord(
            employee_name="测试员",
            employee_email=email,
            source_file=Path("dummy2.xlsx"),
            sheet_name="Sheet2",
            date_range=(date(2025, 1, 13), date(2025, 1, 17)),
            tasks=[
                TaskRow(1, "EMMC分区表优化", 0.9, "对齐4K扇区边界"),
            ],
            plans=[PlanRow(1, "EMMC压测", "一周", "")],
            raw_text="EMMC分区表优化",
            char_count=30,
        ),
    ]

    with open(cache_dir / "_meta.json", "w", encoding="utf-8") as f:
        json.dump([r.to_dict() for r in records], f, ensure_ascii=False)

    return email, records


# 模拟 LLM 返回的画像提取结果
MOCK_PROFILE_RESULT = {
    "radar_outer": {
        "system_platform": {"proportion": 0.30, "depth": 3},
        "driver_development": {"proportion": 0.25, "depth": 2},
        "application_software": {"proportion": 0.20, "depth": 2},
        "wireless_communication": {"proportion": 0.15, "depth": 1},
        "sqa_quality": {"proportion": 0.10, "depth": 1},
    },
    "radar_inner": {
        "truth_seeking": {"level": 3, "score": 0.72, "evidence": ["定位根因"]},
        "pragmatic": {"level": 4, "score": 0.85, "evidence": ["任务闭环"]},
        "rigorous": {"level": 2, "score": 0.55, "evidence": ["边界测试"]},
    },
    "summary": "测试总结",
}

# 模拟 LLM 返回的成长分析结果
MOCK_GROWTH_RESULT = {
    "closed_loop_issues": [
        {
            "title": "WiFi驱动适配问题",
            "first_appeared": "2025-01-06",
            "status": "resolved",
            "duration_weeks": 3,
            "root_cause": "MTK SDK接口变更导致驱动初始化失败",
            "solution": "回退SDK版本并适配新接口",
            "timeline": [
                {"date": "2025-01-06", "progress": "发现问题", "description": "初始化失败"},
                {"date": "2025-01-13", "progress": "定位根因", "description": "SDK接口变更"},
            ],
            "tags": ["driver", "wifi"],
        },
    ],
    "growth_analysis": {
        "recursive_logic": [
            {
                "task_name": "WiFi驱动调试",
                "pattern": "depth_first",
                "reasoning_chain": ["现象", "日志", "模块", "代码行"],
                "label": "深度递进",
                "evidence_period": "2025-01-06 ~ 2025-01-17",
            },
        ],
    },
}

# 模拟 Token 预估结果
MOCK_TOKEN_ESTIMATE = {
    "model": "deepseek/deepseek-chat",
    "token_count": 1200,
    "model_limit": 65536,
    "utilization_pct": 1.8,
    "level_emoji": "🟢",
    "level_label": "绿色安全区",
}


# ============================================================================
# 测试 AnalysisResult 数据模型
# ============================================================================

class TestAnalysisResult:
    """AnalysisResult 数据模型的序列化/反序列化测试"""

    def test_to_dict_and_from_dict(self):
        """测试完整的序列化→反序列化往返"""
        result = AnalysisResult(
            employee_email="test@jointelli.com",
            employee_name="测试员",
            date_range_ids=["2025-01-06_2025-01-11"],
            model_id="deepseek/deepseek-chat",
            token_estimate=MOCK_TOKEN_ESTIMATE,
            profile=MOCK_PROFILE_RESULT,
            growth=MOCK_GROWTH_RESULT,
            markdown_content="# 测试 Markdown 内容",
            generated_at="2026-03-10T16:00:00",
            elapsed_seconds=120.5,
        )

        d = result.to_dict()
        assert d["employee_email"] == "test@jointelli.com"
        assert d["employee_name"] == "测试员"
        assert len(d["date_range_ids"]) == 1
        assert d["elapsed_seconds"] == 120.5
        assert "markdown_content" in d

        # JSON 序列化往返
        json_str = json.dumps(d, ensure_ascii=False)
        restored_data = json.loads(json_str)
        restored = AnalysisResult.from_dict(restored_data)
        assert restored.employee_email == result.employee_email
        assert restored.profile == result.profile
        assert restored.growth == result.growth

    def test_to_web_response_excludes_markdown(self):
        """to_web_response 不包含 markdown_content 字段"""
        result = AnalysisResult(
            employee_email="test@jointelli.com",
            markdown_content="# 很长的 Markdown 内容...",
        )
        web = result.to_web_response()
        assert "markdown_content" not in web
        assert "employee_email" in web

    def test_from_dict_ignores_extra_keys(self):
        """from_dict 忽略多余的未知字段"""
        data = {
            "employee_email": "a@b.com",
            "unknown_field": "should_be_ignored",
            "another_nonsense": 42,
        }
        result = AnalysisResult.from_dict(data)
        assert result.employee_email == "a@b.com"
        assert not hasattr(result, "unknown_field")


# ============================================================================
# 测试集成 API
# ============================================================================

class TestIntegratedAPI:
    """集成 API 的核心集成测试（Mock LLM 调用）"""

    @pytest.fixture
    def api_env(self, tmp_path):
        """构造完整的 API 测试环境"""
        attachments_dir = tmp_path / "attachments"
        attachments_dir.mkdir()
        (attachments_dir / "test@jointelli.com").mkdir()

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        email, records = _make_cached_employee(output_dir, "test@jointelli.com")
        api = CPEPipelineAPI(attachments_dir, output_dir)
        return api, email, output_dir

    @patch("pipeline.api.extract_profile")
    @patch("pipeline.api.analyze_growth")
    @patch("pipeline.api.CPELLMClient")
    def test_run_full_analysis_success(
        self, mock_client_cls, mock_growth, mock_profile, api_env
    ):
        """正常路径：全流程分析应返回完整的 AnalysisResult"""
        api, email, output_dir = api_env

        # 构造 Mock
        mock_client = MagicMock()
        mock_client_cls.from_config.return_value = mock_client
        mock_profile.return_value = MOCK_PROFILE_RESULT.copy()
        mock_growth.return_value = MOCK_GROWTH_RESULT.copy()

        result = api.run_full_analysis(
            email=email,
            date_range_ids=["2025-01-06_2025-01-11", "2025-01-13_2025-01-17"],
            model_id="deepseek/deepseek-chat",
        )

        # 断言返回类型和结构
        assert isinstance(result, AnalysisResult)
        assert result.employee_email == email
        assert result.employee_name == "测试员"
        assert result.model_id == "deepseek/deepseek-chat"
        assert result.generated_at != ""
        assert result.elapsed_seconds >= 0

        # 断言 Token 预估有值
        assert result.token_estimate != {}
        assert "token_count" in result.token_estimate

        # 断言画像和成长分析有值
        assert "radar_outer" in result.profile
        assert "closed_loop_issues" in result.growth

        # 断言 LLM 调用传参正确
        mock_client_cls.from_config.assert_called_once_with("deepseek/deepseek-chat")
        mock_profile.assert_called_once()
        mock_growth.assert_called_once()

        # 断言结果文件已持久化
        result_files = list(output_dir.glob("test@jointelli.com/*_analysis.json"))
        assert len(result_files) == 1

    @patch("pipeline.api.extract_profile")
    @patch("pipeline.api.analyze_growth")
    @patch("pipeline.api.CPELLMClient")
    def test_run_full_analysis_partial_ranges(
        self, mock_client_cls, mock_growth, mock_profile, api_env
    ):
        """部分时间范围选择：只选第一周"""
        api, email, output_dir = api_env
        mock_client = MagicMock()
        mock_client_cls.from_config.return_value = mock_client
        mock_profile.return_value = MOCK_PROFILE_RESULT.copy()
        mock_growth.return_value = MOCK_GROWTH_RESULT.copy()

        result = api.run_full_analysis(
            email=email,
            date_range_ids=["2025-01-06_2025-01-11"],
            model_id="deepseek/deepseek-chat",
        )

        assert isinstance(result, AnalysisResult)
        assert len(result.date_range_ids) == 1
        # Markdown 内容应仅包含第一周的数据
        assert "WiFi驱动调试" in result.markdown_content
        # 第二周数据不应出现
        assert "EMMC分区" not in result.markdown_content

    def test_run_full_analysis_empty_ranges(self, api_env):
        """空时间范围应抛出 ValueError"""
        api, email, _ = api_env
        with pytest.raises(ValueError, match="时间范围"):
            api.run_full_analysis(
                email=email,
                date_range_ids=[],
                model_id="deepseek/deepseek-chat",
            )

    def test_run_full_analysis_nonexistent_employee(self, api_env):
        """不存在的员工应抛出 FileNotFoundError"""
        api, _, _ = api_env
        with pytest.raises(FileNotFoundError):
            api.run_full_analysis(
                email="nobody@jointelli.com",
                date_range_ids=["2025-01-06_2025-01-11"],
                model_id="deepseek/deepseek-chat",
            )

    @patch("pipeline.api.extract_profile")
    @patch("pipeline.api.CPELLMClient")
    def test_run_profile_only(self, mock_client_cls, mock_profile, api_env):
        """仅画像提取模式"""
        api, email, _ = api_env
        mock_client = MagicMock()
        mock_client_cls.from_config.return_value = mock_client
        mock_profile.return_value = MOCK_PROFILE_RESULT.copy()

        result = api.run_profile_only(
            email=email,
            date_range_ids=["2025-01-06_2025-01-11"],
            model_id="deepseek/deepseek-chat",
        )

        assert "radar_outer" in result
        assert "radar_inner" in result
        mock_profile.assert_called_once()

    @patch("pipeline.api.analyze_growth")
    @patch("pipeline.api.CPELLMClient")
    def test_run_growth_only(self, mock_client_cls, mock_growth, api_env):
        """仅成长分析模式"""
        api, email, _ = api_env
        mock_client = MagicMock()
        mock_client_cls.from_config.return_value = mock_client
        mock_growth.return_value = MOCK_GROWTH_RESULT.copy()

        result = api.run_growth_only(
            email=email,
            date_range_ids=["2025-01-06_2025-01-11"],
            model_id="deepseek/deepseek-chat",
        )

        assert "closed_loop_issues" in result
        assert "growth_analysis" in result
        mock_growth.assert_called_once()
