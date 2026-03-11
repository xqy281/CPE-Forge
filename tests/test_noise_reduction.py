"""
数据清洗与去重模块 — 单元测试

覆盖 PRD 2.2 节需求：
- 数据展平与文本拼接
- TF-IDF + 余弦相似度计算
- 94% 阈值去重规则（保留策略）
- 时间线容错重构
"""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import openpyxl
import pytest

from tests.conftest import (
    create_weekly_report_workbook,
    save_workbook_to_dir,
)


class TestDataFlattening:
    """数据展平与文本拼接测试"""

    def test_flatten_sheet_basic(self):
        """标准格式 Sheet 展平为正确纯文本"""
        from pipeline.noise_reduction import flatten_sheet_to_text

        wb = create_weekly_report_workbook(
            tasks=[
                (1, "WiFi驱动调试mt7993", 0.8, "MTK SDK接口变更，需要适配新的回调"),
                (2, "PCIe枚举定位", 1.0, "BAR空间配置错误"),
            ],
            plans=[
                (1, "继续WiFi驱动", "一周", "等待硬件"),
            ],
        )
        ws = wb.active

        text = flatten_sheet_to_text(ws)

        # 应包含任务描述和难点分析
        assert "WiFi驱动调试mt7993" in text
        assert "PCIe枚举定位" in text
        assert "MTK SDK接口变更" in text
        assert "BAR空间配置错误" in text
        # 应包含下周计划
        assert "继续WiFi驱动" in text
        # 不应为空
        assert len(text.strip()) > 0

    def test_flatten_empty_cells(self):
        """空单元格和空行被正确过滤，不产生多余空白"""
        from pipeline.noise_reduction import flatten_sheet_to_text

        wb = create_weekly_report_workbook(
            tasks=[
                (1, "唯一任务", 1.0, ""),  # 难点分析为空
            ],
            plans=[],
        )
        ws = wb.active

        text = flatten_sheet_to_text(ws)
        assert "唯一任务" in text
        # 不应有连续多个空行
        assert "\n\n\n" not in text

    def test_flatten_with_newlines_in_cells(self):
        """单元格内含换行符时应保留内容完整性"""
        from pipeline.noise_reduction import flatten_sheet_to_text

        wb = create_weekly_report_workbook(
            tasks=[
                (1, "1、mt7993驱动patch路径处理\n\n2、T830平台调试", 1.0,
                 "Griffin BE3600 虽然支持硬件ZWDFS\n但是必须工作在2T2R下"),
            ],
        )
        ws = wb.active

        text = flatten_sheet_to_text(ws)
        assert "mt7993驱动patch路径处理" in text
        assert "T830平台调试" in text
        assert "Griffin BE3600" in text


class TestSimilarityCalculation:
    """TF-IDF + 余弦相似度计算测试"""

    def test_similarity_identical_texts(self):
        """完全相同文本相似度应为 1.0"""
        from pipeline.noise_reduction import compute_similarity_matrix

        texts = [
            "WiFi驱动调试mt7993，MTK SDK接口变更需要适配新的回调函数",
            "WiFi驱动调试mt7993，MTK SDK接口变更需要适配新的回调函数",
        ]

        matrix = compute_similarity_matrix(texts)
        assert matrix[0][1] == pytest.approx(1.0, abs=0.01)

    def test_similarity_slightly_different(self):
        """微小差异（错别字/标点）应 ≥ 0.94"""
        from pipeline.noise_reduction import compute_similarity_matrix

        text_base = (
            "WiFi驱动调试mt7993，MTK SDK接口变更需要适配新的回调函数。"
            "PCIe枚举失败定位，根因是BAR空间配置错误导致设备无法被识别。"
            "修复网口link监听服务适配问题，默认指向MT7531。"
            "前端web编译整合到package框架，面向版本号适配。"
        )
        text_typo = (
            "WiFi驱动调试mt7993，MTK SDK接口变更需要适配新的回调函数。"
            "PCIe枚举失败定位，根因是BAR空间配置错误导致设备无法被识别。"
            "修复网口link监听服务适配问题，默认指向MT7531。"
            "前端web编译整合到package框架，面向版本号适配。"  # 仅标点差异
        )

        texts = [text_base, text_typo]
        matrix = compute_similarity_matrix(texts)
        assert matrix[0][1] >= 0.94

    def test_similarity_very_different(self):
        """完全不同内容的周报相似度应 < 0.94"""
        from pipeline.noise_reduction import compute_similarity_matrix

        texts = [
            "WiFi驱动调试mt7993，MTK SDK接口变更需要适配新的回调函数。PCIe枚举失败定位。",
            "EMMC分区表优化对齐4K扇区边界，解决了压测中AB分区切换异常的问题。固件升级流程重构。",
        ]

        matrix = compute_similarity_matrix(texts)
        assert matrix[0][1] < 0.94

    def test_similarity_empty_text(self):
        """空文本不应导致崩溃"""
        from pipeline.noise_reduction import compute_similarity_matrix

        texts = ["", "WiFi驱动调试mt7993"]
        matrix = compute_similarity_matrix(texts)
        assert matrix.shape == (2, 2)

    def test_similarity_single_text(self):
        """仅一条文本时返回 1x1 矩阵"""
        from pipeline.noise_reduction import compute_similarity_matrix

        texts = ["WiFi驱动调试mt7993"]
        matrix = compute_similarity_matrix(texts)
        assert matrix.shape == (1, 1)
        assert matrix[0][0] == pytest.approx(1.0, abs=0.01)


class TestDeduplication:
    """94% 阈值去重规则测试"""

    def test_dedup_keeps_latest(self):
        """重复组中应保留 file_modified_time 最新的"""
        from pipeline.noise_reduction import deduplicate_sheets
        from pipeline.models import SheetRecord

        # 两份内容完全相同的 Sheet，文件修改时间不同
        shared_text = (
            "WiFi驱动调试mt7993，MTK SDK接口变更需要适配新的回调函数。"
            "PCIe枚举失败定位，根因是BAR空间配置错误导致设备无法被识别。"
        )
        older = SheetRecord(
            employee_name="萧倩云",
            employee_email="xiaoqianyun@jointelli.com",
            source_file=Path("old.xlsx"),
            sheet_name="周报",
            raw_text=shared_text,
            char_count=len(shared_text),
            file_modified_time=datetime(2025, 1, 10, 18, 0),
        )
        newer = SheetRecord(
            employee_name="萧倩云",
            employee_email="xiaoqianyun@jointelli.com",
            source_file=Path("new.xlsx"),
            sheet_name="周报",
            raw_text=shared_text,
            char_count=len(shared_text),
            file_modified_time=datetime(2025, 1, 17, 18, 0),
        )

        survivors, dup_groups = deduplicate_sheets([older, newer])

        assert len(survivors) == 1
        # 应保留 newer（修改时间更新）
        assert survivors[0].file_modified_time == datetime(2025, 1, 17, 18, 0)
        assert len(dup_groups) == 1

    def test_dedup_keeps_longest_when_same_time(self):
        """时间相同时应保留有效字符数最多的"""
        from pipeline.noise_reduction import deduplicate_sheets
        from pipeline.models import SheetRecord

        # 使用足够长的基础文本，使微小差异下相似度 ≥ 0.94
        base_text = (
            "WiFi驱动调试mt7993，MTK SDK接口变更需要适配新的回调函数。"
            "PCIe枚举失败定位，根因是BAR空间配置错误导致设备无法被识别。"
            "修复网口link监听服务适配问题，默认指向MT7531，反向以适配更多型号。"
            "前端web编译整合到package框架，面向版本号适配，无需刻意编译。"
            "深度精简now_make编译业务，单命令行即可完成编译需求。"
            "统一从表征版本号信息解析出软件及硬件配置要求。"
            "服务器编译环境适配，兼容新SDK编译条件，修复兼容性问题。"
        )
        same_time = datetime(2025, 1, 17, 18, 0)

        shorter = SheetRecord(
            employee_name="萧倩云",
            employee_email="xiaoqianyun@jointelli.com",
            source_file=Path("short.xlsx"),
            sheet_name="周报",
            raw_text=base_text,
            char_count=len(base_text),
            file_modified_time=same_time,
        )
        # 仅追加极少量文字，确保相似度 ≥ 0.94
        longer_text = base_text + "备注。"
        longer = SheetRecord(
            employee_name="萧倩云",
            employee_email="xiaoqianyun@jointelli.com",
            source_file=Path("long.xlsx"),
            sheet_name="周报",
            raw_text=longer_text,
            char_count=len(longer_text),
            file_modified_time=same_time,
        )

        survivors, dup_groups = deduplicate_sheets([shorter, longer])

        assert len(survivors) == 1
        assert survivors[0].source_file == Path("long.xlsx")

    def test_dedup_preserves_unique(self):
        """不相似的 Sheet 应全部保留"""
        from pipeline.noise_reduction import deduplicate_sheets
        from pipeline.models import SheetRecord

        records = [
            SheetRecord(
                employee_name="萧倩云",
                employee_email="xiaoqianyun@jointelli.com",
                source_file=Path(f"week{i}.xlsx"),
                sheet_name="周报",
                raw_text=text,
                char_count=len(text),
                file_modified_time=datetime(2025, 1, 7 * i, 18, 0),
            )
            for i, text in enumerate([
                "WiFi驱动调试mt7993，MTK SDK接口变更需要适配新的回调函数。",
                "EMMC分区表优化对齐4K扇区边界，解决了压测中AB分区切换异常的问题。",
                "TR069代码编译通过固件版本号自动区分，逐渐实现自动化定制类型固件编译。",
            ], start=1)
        ]

        survivors, dup_groups = deduplicate_sheets(records)

        assert len(survivors) == 3
        assert len(dup_groups) == 0

    def test_dedup_transitive_group(self):
        """传递性重复：A≈B，B≈C → A、B、C 应为同一重复组"""
        from pipeline.noise_reduction import deduplicate_sheets
        from pipeline.models import SheetRecord

        base = "WiFi驱动调试mt7993，MTK SDK接口变更需要适配新的回调函数。PCIe枚举失败定位。" * 5
        records = [
            SheetRecord(
                employee_name="萧倩云",
                employee_email="xiaoqianyun@jointelli.com",
                source_file=Path(f"v{i}.xlsx"),
                sheet_name="周报",
                raw_text=base + ("。" * i),  # 微小差异
                char_count=len(base) + i,
                file_modified_time=datetime(2025, 1, 10 + i, 18, 0),
            )
            for i in range(3)
        ]

        survivors, dup_groups = deduplicate_sheets(records)

        # 3 份高度相似的 → 只保留 1 份
        assert len(survivors) == 1
        assert len(dup_groups) == 1


class TestTimelineReconstruction:
    """时间线容错重构测试"""

    def test_timeline_regex_extraction(self):
        """从表头/内容中正则提取日期"""
        from pipeline.utils import parse_date_from_text

        # 标准格式
        result = parse_date_from_text("2025年1月6日~1月11日")
        assert result is not None
        assert result[0] == date(2025, 1, 6)
        assert result[1] == date(2025, 1, 11)

    def test_timeline_short_date_format(self):
        """短格式日期：1/6 ~ 1/11"""
        from pipeline.utils import parse_date_from_text

        result = parse_date_from_text("1/6 ~ 1/11", reference_year=2025)
        assert result is not None
        assert result[0] == date(2025, 1, 6)
        assert result[1] == date(2025, 1, 11)

    def test_timeline_dot_format(self):
        """点分格式：01.06-01.11"""
        from pipeline.utils import parse_date_from_text

        result = parse_date_from_text("01.06-01.11", reference_year=2025)
        assert result is not None
        assert result[0] == date(2025, 1, 6)
        assert result[1] == date(2025, 1, 11)

    def test_timeline_cross_year(self):
        """跨年日期：12月30日~1月3日"""
        from pipeline.utils import parse_date_from_text

        result = parse_date_from_text("2024年12月30日~1月3日")
        assert result is not None
        assert result[0] == date(2024, 12, 30)
        assert result[1] == date(2025, 1, 3)

    def test_timeline_no_date_returns_none(self):
        """无日期文本返回 None"""
        from pipeline.utils import parse_date_from_text

        result = parse_date_from_text("这是一段没有日期的文字")
        assert result is None

    def test_timeline_short_date_cross_year_with_context(self):
        """短格式跨年日期应从上下文推断年份：
        文件名含 '2024年' 时，'12/30 ~ 1/3' 应解析为 2024-12-30 ~ 2025-01-03
        """
        from pipeline.utils import parse_date_from_text

        # 模拟文件名作为输入文本，含有完整年份 2024
        result = parse_date_from_text(
            "工作周报_何宗峰(2024年12月30日-2025年1月3日)"
        )
        assert result is not None
        assert result[0] == date(2024, 12, 30)
        assert result[1] == date(2025, 1, 3)

    def test_timeline_short_date_no_year_pure(self):
        """纯短格式（无年份上下文），仍使用 reference_year 默认值"""
        from pipeline.utils import parse_date_from_text

        result = parse_date_from_text("1/6 ~ 1/11")
        assert result is not None
        # 默认 reference_year=2025
        assert result[0] == date(2025, 1, 6)
        assert result[1] == date(2025, 1, 11)

    def test_timeline_filename_priority_over_content(self):
        """文件名日期应优先于 Sheet 内容中的 A 列日期"""
        from pipeline.utils import parse_date_from_text

        # 文件名有明确日期
        filename = "工作周报_何宗峰(2025年1月6日-2025年1月11日)"
        result = parse_date_from_text(filename)
        assert result is not None
        assert result[0] == date(2025, 1, 6)
        assert result[1] == date(2025, 1, 11)

        # 即使某个 A 列代码提取到 "12/30 ~ 1/3"，文件名日期优先
        content_date = "12/30 ~ 1/3"
        content_result = parse_date_from_text(content_date)
        # 无年份上下文时，使用默认 reference_year=2025 → 2025-12-30
        assert content_result[0] == date(2025, 12, 30)

    def test_timeline_sorted_order(self):
        """重构后的时间线应按日期正序排列"""
        from pipeline.noise_reduction import reconstruct_timeline
        from pipeline.models import SheetRecord

        records = [
            SheetRecord(
                employee_name="萧倩云",
                employee_email="xiaoqianyun@jointelli.com",
                source_file=Path("w3.xlsx"),
                sheet_name="周报",
                date_range=(date(2025, 1, 20), date(2025, 1, 24)),
            ),
            SheetRecord(
                employee_name="萧倩云",
                employee_email="xiaoqianyun@jointelli.com",
                source_file=Path("w1.xlsx"),
                sheet_name="周报",
                date_range=(date(2025, 1, 6), date(2025, 1, 11)),
            ),
            SheetRecord(
                employee_name="萧倩云",
                employee_email="xiaoqianyun@jointelli.com",
                source_file=Path("w2.xlsx"),
                sheet_name="周报",
                date_range=(date(2025, 1, 13), date(2025, 1, 17)),
            ),
        ]

        sorted_records = reconstruct_timeline(records)
        dates = [r.date_range[0] for r in sorted_records]
        assert dates == sorted(dates)

    def test_timeline_fallback_to_mtime(self):
        """内容无日期时降级使用文件修改时间"""
        from pipeline.noise_reduction import reconstruct_timeline
        from pipeline.models import SheetRecord

        records = [
            SheetRecord(
                employee_name="萧倩云",
                employee_email="xiaoqianyun@jointelli.com",
                source_file=Path("w2.xlsx"),
                sheet_name="周报",
                date_range=None,
                file_modified_time=datetime(2025, 1, 17, 18, 0),
            ),
            SheetRecord(
                employee_name="萧倩云",
                employee_email="xiaoqianyun@jointelli.com",
                source_file=Path("w1.xlsx"),
                sheet_name="周报",
                date_range=None,
                file_modified_time=datetime(2025, 1, 10, 18, 0),
            ),
        ]

        sorted_records = reconstruct_timeline(records)
        # w1 修改时间更早，应排在前面
        assert sorted_records[0].source_file == Path("w1.xlsx")
        assert sorted_records[1].source_file == Path("w2.xlsx")


class TestEmployeeNameExtraction:
    """员工姓名提取测试"""

    def test_extract_from_report_format(self):
        """工作周报_萧倩云(2025年...) → 萧倩云"""
        from pipeline.utils import extract_employee_name_from_filename

        name = extract_employee_name_from_filename(
            "工作周报_萧倩云(2025年1月6日~1月11日).xlsx"
        )
        assert name == "萧倩云"

    def test_extract_from_summary_format(self):
        """萧倩云软件部2025年... → 萧倩云"""
        from pipeline.utils import extract_employee_name_from_filename

        name = extract_employee_name_from_filename(
            "萧倩云软件部2025年01月12日-01月17日工作总结及次周计划.xlsx"
        )
        assert name == "萧倩云"

    def test_extract_with_underscore(self):
        """吴开健_软件部（2025年...） → 吴开健"""
        from pipeline.utils import extract_employee_name_from_filename

        name = extract_employee_name_from_filename(
            "吴开健_软件部（2025年09月15日-09月19日）工作总结及次周计划.xlsx"
        )
        assert name == "吴开健"

    def test_extract_with_parenthesis_variants(self):
        """含全角括号的文件名"""
        from pipeline.utils import extract_employee_name_from_filename

        name = extract_employee_name_from_filename(
            "工作周报_赖灿辉（2025年1月13日-2025年1月17日）.xlsx"
        )
        assert name == "赖灿辉"
