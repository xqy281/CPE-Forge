"""
端到端清洗管线运行脚本

按顺序执行：
1. auto_discovery.scan_directory() → 过滤有效周报
2. noise_reduction.flatten_and_deduplicate() → 清洗去重
3. 输出清洗结果统计报告

用法：
    python scripts/run_pipeline.py --input attachments --output output --report
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

# 确保 pipeline 包在 import 路径中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.auto_discovery import scan_directory
from pipeline.eml_extractor import build_date_calibration_map, extract_attachments_from_eml_dir
from pipeline.models import CleaningReport, FileStatus
from pipeline.noise_reduction import flatten_and_deduplicate


def setup_logging(verbose: bool = False):
    """配置日志输出"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def run_pipeline(
    input_dir: Path,
    output_dir: Path | None = None,
    report: bool = True,
    similarity_threshold: float = 0.98,
    emails_dir: Path | None = None,
) -> CleaningReport:
    """
    执行完整的数据清洗管线。

    Args:
        input_dir: 附件目录（包含员工子目录）
        output_dir: 输出目录（存放清洗结果）
        report: 是否输出统计报告
        similarity_threshold: 相似度阈值
        emails_dir: 可选，EML 邮件目录（用于年份校准）

    Returns:
        清洗统计报告
    """
    logger = logging.getLogger("pipeline")
    cleaning_report = CleaningReport()

    # ============================================================
    # 阶段 0: EML 邮件日期校准映射表
    # ============================================================
    calibration_map = None
    if emails_dir and emails_dir.exists():
        logger.info("=" * 60)
        logger.info("阶段 0: EML 邮件处理")
        logger.info("=" * 60)

        # 检查 attachments 目录是否为空（无员工子目录），如果是则自动从 EML 提取附件
        has_employee_dirs = any(
            d.is_dir() and "@" in d.name
            for d in input_dir.iterdir()
        ) if input_dir.exists() else False

        if not has_employee_dirs:
            logger.info("附件目录为空，从 EML 邮件提取附件...")
            calibration_map = extract_attachments_from_eml_dir(emails_dir, input_dir)
        else:
            logger.info("附件目录已有数据，仅构建校准映射表")
            calibration_map = build_date_calibration_map(emails_dir)

        logger.info("校准映射表: %d 个附件", len(calibration_map))

    # ============================================================
    # 阶段 1: 智能识别与过滤
    # ============================================================
    logger.info("=" * 60)
    logger.info("阶段 1: 智能识别与过滤 (Auto-Discovery)")
    logger.info("=" * 60)

    t0 = time.perf_counter()
    valid_files, rejected_files, error_files = scan_directory(
        input_dir, calibration_map=calibration_map
    )
    t1 = time.perf_counter()

    # 统计
    cleaning_report.total_files = len(valid_files) + len(rejected_files) + len(error_files)
    cleaning_report.valid_files = len(valid_files)
    cleaning_report.rejected_files = len(rejected_files)

    # 区分 corrupt / encrypted
    for ef in error_files:
        if ef.status == FileStatus.ENCRYPTED:
            cleaning_report.encrypted_files += 1
            cleaning_report.encrypted_file_list.append(str(ef.filepath))
        else:
            cleaning_report.corrupt_files += 1

    # 统计 Sheet 总数
    all_sheet_records = []
    for vf in valid_files:
        all_sheet_records.extend(vf.sheets)
    cleaning_report.total_sheets = len(all_sheet_records)

    logger.info("识别完成 (%.2fs):", t1 - t0)
    logger.info("  总文件数: %d", cleaning_report.total_files)
    logger.info("  有效周报文件: %d", cleaning_report.valid_files)
    logger.info("  被过滤文件: %d", cleaning_report.rejected_files)
    logger.info("  加密文件 (TSD): %d", cleaning_report.encrypted_files)
    logger.info("  损坏文件: %d", cleaning_report.corrupt_files)
    logger.info("  有效 Sheet 总数: %d", cleaning_report.total_sheets)

    if not all_sheet_records:
        logger.warning("没有找到有效周报 Sheet，管线终止。")
        return cleaning_report

    # ============================================================
    # 阶段 2: 数据清洗与去重
    # ============================================================
    logger.info("")
    logger.info("=" * 60)
    logger.info("阶段 2: 数据清洗与去重 (Noise Reduction)")
    logger.info("  相似度阈值: %.2f", similarity_threshold)
    logger.info("=" * 60)

    t2 = time.perf_counter()
    employee_timelines, all_dup_groups = flatten_and_deduplicate(
        all_sheet_records, similarity_threshold
    )
    t3 = time.perf_counter()

    # 统计
    total_survivors = sum(len(tl) for tl in employee_timelines.values())
    cleaning_report.unique_sheets = total_survivors
    cleaning_report.duplicate_groups = len(all_dup_groups)
    for emp_email, timeline in employee_timelines.items():
        cleaning_report.employees[emp_email] = len(timeline)

    logger.info("去重完成 (%.2fs):", t3 - t2)
    logger.info("  去重前 Sheet: %d", cleaning_report.total_sheets)
    logger.info("  去重后 Sheet: %d", total_survivors)
    logger.info("  剔除重复组: %d", cleaning_report.duplicate_groups)
    logger.info(
        "  去重率: %.1f%%",
        (1 - total_survivors / max(cleaning_report.total_sheets, 1)) * 100,
    )

    # ============================================================
    # 阶段 3: 每位员工详情
    # ============================================================
    logger.info("")
    logger.info("=" * 60)
    logger.info("阶段 3: 员工清洗结果详情")
    logger.info("=" * 60)

    for emp_email in sorted(employee_timelines.keys()):
        timeline = employee_timelines[emp_email]
        if timeline:
            first_name = timeline[0].employee_name
            first_date = timeline[0].date_range[0] if timeline[0].date_range else "N/A"
            last_date = timeline[-1].date_range[0] if timeline[-1].date_range else "N/A"
            logger.info(
                "  %-35s %s: %d 份周报 (%s → %s)",
                emp_email, first_name, len(timeline), first_date, last_date,
            )

    # ============================================================
    # 阶段 4: 重复组审计日志
    # ============================================================
    if all_dup_groups:
        logger.info("")
        logger.info("=" * 60)
        logger.info("阶段 4: 重复组审计日志 (前 20 组)")
        logger.info("=" * 60)

        for i, dg in enumerate(all_dup_groups[:20]):
            avg_sim = sum(dg.similarity_scores) / max(len(dg.similarity_scores), 1)
            logger.info(
                "  重复组 #%d (平均相似度: %.4f):", i + 1, avg_sim
            )
            logger.info(
                "    [保留] %s / %s (修改: %s, 字符: %d)",
                dg.survivor.source_file.name,
                dg.survivor.sheet_name,
                dg.survivor.file_modified_time,
                dg.survivor.char_count,
            )
            for dr in dg.discarded:
                logger.info(
                    "    [丢弃] %s / %s (修改: %s, 字符: %d)",
                    dr.source_file.name,
                    dr.sheet_name,
                    dr.file_modified_time,
                    dr.char_count,
                )

    # ============================================================
    # 输出结果
    # ============================================================
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)

        # 保存 JSON 报告
        if report:
            report_path = output_dir / "cleaning_report.json"
            report_data = {
                "总文件数": cleaning_report.total_files,
                "有效文件": cleaning_report.valid_files,
                "被过滤文件": cleaning_report.rejected_files,
                "加密文件": cleaning_report.encrypted_files,
                "损坏文件": cleaning_report.corrupt_files,
                "Sheet总数": cleaning_report.total_sheets,
                "去重后Sheet数": cleaning_report.unique_sheets,
                "重复组数": cleaning_report.duplicate_groups,
                "去重率": f"{(1 - cleaning_report.unique_sheets / max(cleaning_report.total_sheets, 1)) * 100:.1f}%",
                "员工明细": {
                    email: count
                    for email, count in sorted(cleaning_report.employees.items())
                },
                "加密文件清单": cleaning_report.encrypted_file_list,
            }
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(report_data, f, ensure_ascii=False, indent=2)
            logger.info("")
            logger.info("报告已保存: %s", report_path)

        # 保存每位员工的清洗后 Markdown 周报（用于后续喂给大模型）
        for emp_email, timeline in employee_timelines.items():
            if not timeline:
                continue
            emp_name = timeline[0].employee_name
            md_path = output_dir / f"{emp_email}.md"

            lines = [f"# {emp_name} 清洗后周报汇总\n"]
            for record in timeline:
                date_label = (
                    f"{record.date_range[0]} ~ {record.date_range[1]}"
                    if record.date_range
                    else "日期未知"
                )
                lines.append(f"\n## {date_label}\n")
                lines.append(f"来源: `{record.source_file.name}` / `{record.sheet_name}`\n")

                if record.tasks:
                    lines.append("\n| 序号 | 任务描述 | 进度 | 难点分析 |")
                    lines.append("|------|----------|------|----------|")
                    for t in record.tasks:
                        progress_str = f"{t.progress:.0%}" if t.progress is not None else ""
                        lines.append(
                            f"| {t.seq} | {t.description} | {progress_str} | {t.analysis} |"
                        )

                if record.plans:
                    lines.append("\n| 序号 | 计划内容 | 计划时间 | 描述 |")
                    lines.append("|------|----------|----------|------|")
                    for p in record.plans:
                        lines.append(
                            f"| {p.seq} | {p.content} | {p.planned_time} | {p.description} |"
                        )

            with open(md_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            logger.info("已生成: %s (%d 份周报)", md_path.name, len(timeline))

    return cleaning_report


def main():
    parser = argparse.ArgumentParser(
        description="CPE-Forge 数据清洗管线",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--input", "-i",
        type=Path,
        default=Path("attachments"),
        help="附件输入目录 (默认: attachments)",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=None,
        help="清洗结果输出目录 (默认: 不输出文件，仅打印报告)",
    )
    parser.add_argument(
        "--report", "-r",
        action="store_true",
        default=False,
        help="生成 JSON 统计报告",
    )
    parser.add_argument(
        "--threshold", "-t",
        type=float,
        default=0.98,
        help="相似度去重阈值 (默认: 0.98)",
    )
    parser.add_argument(
        "--emails", "-e",
        type=Path,
        default=None,
        help="EML 邮件目录，用于年份校准 (默认: 不校准)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        default=False,
        help="开启详细调试日志",
    )

    args = parser.parse_args()

    if not args.input.exists():
        print(f"错误: 输入目录不存在: {args.input}", file=sys.stderr)
        sys.exit(1)

    setup_logging(verbose=args.verbose)

    report = run_pipeline(
        input_dir=args.input,
        output_dir=args.output,
        report=args.report,
        similarity_threshold=args.threshold,
        emails_dir=args.emails,
    )

    # 最终汇总
    print()
    print("=" * 60)
    print("清洗管线执行完毕! 汇总：")
    print(f"  总文件: {report.total_files}")
    print(f"  有效: {report.valid_files} | 过滤: {report.rejected_files} | 加密: {report.encrypted_files} | 损坏: {report.corrupt_files}")
    print(f"  Sheet: {report.total_sheets} → {report.unique_sheets} (去重 {report.duplicate_groups} 组)")
    print(f"  员工: {len(report.employees)} 人")
    print("=" * 60)


if __name__ == "__main__":
    main()
