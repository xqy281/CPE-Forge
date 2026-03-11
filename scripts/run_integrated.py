"""
端到端集成调试脚本 — 数据清洗 + LLM 分析完整流程

支持两种使用方式：

1. 交互式模式（默认）:
    python scripts/run_integrated.py

2. 命令行模式（非交互，适用于 CI/CD 或 Web 后台调度）:
    python scripts/run_integrated.py --email xiaoqianyun@jointelli.com --all-ranges --model deepseek/deepseek-chat

可选参数:
    --email, -e        员工邮箱
    --all-ranges       选择该员工全部可用时间范围
    --ranges, -r       指定时间范围 ID（逗号分隔）
    --model, -m        LLM 模型标识（默认: deepseek/deepseek-chat）
    --profile-only     仅画像提取
    --growth-only      仅成长分析
    --token-only       仅 Token 预估（不调用 LLM）
    --input, -i        附件目录（默认: attachments）
    --output, -o       输出目录（默认: output）
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

from pipeline.api import CPEPipelineAPI
from pipeline.llm_config import list_model_configs, init_default_configs
from pipeline.token_estimator import estimate_markdown_tokens


def setup_logging(verbose: bool = False):
    """配置日志"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def select_employee_interactive(api: CPEPipelineAPI) -> str:
    """交互式选择员工"""
    employees = api.get_employee_list()
    if not employees:
        print("❌ 未找到任何员工数据，请确认 attachments 目录结构正确。")
        sys.exit(1)

    print("\n📋 可用员工列表:")
    print("-" * 50)
    for i, emp in enumerate(sorted(employees, key=lambda x: x["email"]), 1):
        print(f"  {i:2d}. {emp['name']:20s} ({emp['email']})")

    while True:
        try:
            choice = input(f"\n请选择员工编号 [1-{len(employees)}]: ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(employees):
                selected = sorted(employees, key=lambda x: x["email"])[idx]
                return selected["email"]
            print(f"  ⚠️ 请输入 1 到 {len(employees)} 之间的数字")
        except (ValueError, KeyboardInterrupt):
            print("\n已取消。")
            sys.exit(0)


def select_ranges_interactive(
    api: CPEPipelineAPI, email: str
) -> list[str]:
    """交互式选择时间范围"""
    print(f"\n🔍 正在获取 {email} 的周报时间范围...")
    ranges = api.get_employee_report_ranges(email)

    if not ranges:
        print(f"❌ 未找到 {email} 的有效周报数据。")
        sys.exit(1)

    print(f"\n📅 可用周报时间范围 (共 {len(ranges)} 个):")
    print("-" * 50)
    for i, r in enumerate(ranges, 1):
        print(f"  {i:2d}. {r['start']} ~ {r['end']}")

    print(f"\n  0. 全部选择 ({len(ranges)} 个)")

    while True:
        try:
            choice = input(f"\n请选择 [0=全部, 或输入编号，逗号分隔]: ").strip()
            if choice == "0":
                return [r["id"] for r in ranges]
            indices = [int(x.strip()) - 1 for x in choice.split(",")]
            selected = []
            for idx in indices:
                if 0 <= idx < len(ranges):
                    selected.append(ranges[idx]["id"])
                else:
                    print(f"  ⚠️ 编号 {idx + 1} 超出范围")
                    continue
            if selected:
                return selected
            print("  ⚠️ 未选择任何有效时间范围")
        except (ValueError, KeyboardInterrupt):
            print("\n已取消。")
            sys.exit(0)


def select_model_interactive() -> str:
    """交互式选择 LLM 模型"""
    configs = list_model_configs(enabled_only=True)

    if not configs:
        print("⚠️ 未找到任何已启用的模型配置，使用默认模型。")
        return "deepseek/deepseek-chat"

    print(f"\n🤖 可用 LLM 模型 (共 {len(configs)} 个):")
    print("-" * 50)
    for i, c in enumerate(configs, 1):
        key_hint = "✅" if c.api_key else "❌未配置Key"
        print(f"  {i:2d}. {c.display_name:25s} ({c.model_id})  {key_hint}")

    while True:
        try:
            choice = input(f"\n请选择模型编号 [1-{len(configs)}, 回车使用第1个]: ").strip()
            if not choice:
                selected = configs[0]
                return selected.model_id
            idx = int(choice) - 1
            if 0 <= idx < len(configs):
                selected = configs[idx]
                return selected.model_id
            print(f"  ⚠️ 请输入 1 到 {len(configs)} 之间的数字")
        except (ValueError, KeyboardInterrupt):
            print("\n已取消。")
            sys.exit(0)


def print_analysis_summary(result):
    """格式化打印分析结果摘要"""
    print("\n" + "=" * 60)
    print("🎯 分析结果摘要")
    print("=" * 60)

    print(f"\n  员工: {result.employee_name} ({result.employee_email})")
    print(f"  模型: {result.model_id}")
    print(f"  时间范围: {len(result.date_range_ids)} 个周报区间")
    print(f"  总耗时: {result.elapsed_seconds:.1f}s")

    # Token 预估
    te = result.token_estimate
    if te:
        print(f"\n  📊 Token 预估:")
        print(f"    Token 数: {te.get('token_count', 0):,}")
        print(f"    水位线: {te.get('level_emoji', '')} {te.get('level_label', '')}")

    # 画像提取
    profile = result.profile
    if profile and "radar_outer" in profile:
        print(f"\n  🎯 外层雷达图（技术广度 — 双轨制）:")
        print(f"    {'维度':25s} {'精力占比':10s}  {'投入深度':8s}")
        print(f"    {'─' * 55}")
        for dim, entry in profile["radar_outer"].items():
            if isinstance(entry, dict):
                prop = entry.get("proportion", 0.0)
                depth = entry.get("depth", 0)
            else:
                prop = float(entry) if entry else 0.0
                depth = 0
            bar = "█" * int(prop * 20) + "░" * (20 - int(prop * 20))
            stars = "★" * depth + "☆" * (5 - depth)
            print(f"    {dim:25s} {bar} {prop:.0%}   {stars}")

        print(f"\n  🧠 内层内核（工程素养）:")
        for dim in ["truth_seeking", "pragmatic", "rigorous"]:
            inner = profile.get("radar_inner", {}).get(dim, {})
            level = inner.get("level", 0)
            score = inner.get("score", 0.0)
            print(f"    {dim:15s}  Lv{level}  ({score:.2f})")
            for ev in inner.get("evidence", [])[:2]:
                print(f"      📌 {ev[:80]}")

        # 画像总结摘要
        if profile.get("summary"):
            print(f"\n  📝 总结: {profile['summary']}")

    # 成长分析
    growth = result.growth
    if growth:
        issues = growth.get("closed_loop_issues", [])
        print(f"\n  📈 问题闭环追踪: 共 {len(issues)} 个")
        for issue in issues[:5]:
            status_icon = "✅" if issue.get("status") == "resolved" else "🔄"
            print(f"    {status_icon} [{issue.get('first_appeared', '?')}] {issue['title']}")

        recursive = growth.get("growth_analysis", {}).get("recursive_logic", [])
        print(f"\n  🧅 递进分析: 共 {len(recursive)} 个")
        for item in recursive[:5]:
            icon = "🧅" if item.get("pattern") == "depth_first" else "🎲"
            print(f"    {icon} {item.get('task_name', '?')} → {item.get('label', '?')}")


def main():
    parser = argparse.ArgumentParser(
        description="CPE-Forge 集成分析调试工具（数据清洗 + LLM 分析完整流程）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 交互式模式
  python scripts/run_integrated.py

  # 命令行模式（全量时间范围）
  python scripts/run_integrated.py --email xiaoqianyun@jointelli.com --all-ranges --model deepseek/deepseek-chat

  # 仅 Token 预估（不调用 LLM）
  python scripts/run_integrated.py --email xiaoqianyun@jointelli.com --all-ranges --token-only
        """,
    )

    # 数据源参数
    parser.add_argument("--email", "-e", type=str, help="员工邮箱")
    parser.add_argument("--all-ranges", action="store_true", help="选择全部可用时间范围")
    parser.add_argument("--ranges", "-r", type=str, help="时间范围 ID（逗号分隔）")

    # 模型参数
    parser.add_argument("--model", "-m", type=str, default="deepseek/deepseek-chat",
                        help="LLM 模型标识 (默认: deepseek/deepseek-chat)")

    # 运行模式
    parser.add_argument("--token-only", action="store_true", help="仅 Token 预估（不调用 LLM）")
    parser.add_argument("--profile-only", action="store_true", help="仅画像提取")
    parser.add_argument("--growth-only", action="store_true", help="仅成长分析")

    # 路径参数
    parser.add_argument("--input", "-i", type=Path, default=Path("attachments"),
                        help="附件目录 (默认: attachments)")
    parser.add_argument("--output", "-o", type=Path, default=Path("output"),
                        help="输出目录 (默认: output)")

    # 日志
    parser.add_argument("--verbose", "-v", action="store_true", help="详细日志")

    args = parser.parse_args()
    setup_logging(verbose=args.verbose)

    # 强制 UTF-8 输出
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║    CPE-Forge 集成分析调试工具                            ║")
    print("║    数据清洗管线 + LLM 分析管线 端到端执行                ║")
    print("╚══════════════════════════════════════════════════════════╝")

    api = CPEPipelineAPI(args.input, args.output)

    # 1. 选择员工
    if args.email:
        email = args.email
        print(f"\n📧 目标员工: {email}")
    else:
        email = select_employee_interactive(api)
        print(f"\n✅ 已选择: {email}")

    # 2. 选择时间范围
    if args.all_ranges:
        ranges = api.get_employee_report_ranges(email)
        if not ranges:
            print(f"❌ 未找到 {email} 的有效周报数据。")
            sys.exit(1)
        date_range_ids = [r["id"] for r in ranges]
        print(f"📅 已选择全部 {len(date_range_ids)} 个时间范围")
    elif args.ranges:
        date_range_ids = [r.strip() for r in args.ranges.split(",")]
        print(f"📅 已指定 {len(date_range_ids)} 个时间范围")
    else:
        date_range_ids = select_ranges_interactive(api, email)
        print(f"✅ 已选择 {len(date_range_ids)} 个时间范围")

    # 3. Token 预估模式（不调用 LLM）
    if args.token_only:
        print("\n" + "=" * 60)
        print("📊 Token 预估模式（不调用 LLM）")
        print("=" * 60)
        md_path = api.generate_cleaned_markdown(email, date_range_ids)
        content = md_path.read_text(encoding="utf-8")
        print(f"\n  Markdown 内容长度: {len(content):,} 字符")

        for model_name in ["deepseek/deepseek-chat", "gpt-4o", "anthropic/claude-3.5-sonnet"]:
            result = estimate_markdown_tokens(content, model=model_name)
            info = result.to_dict()
            print(f"\n  📊 {model_name}:")
            print(f"    Token 数: {info['token_count']:,}")
            print(f"    模型上限: {info['model_limit']:,}")
            print(f"    利用率: {info['utilization_pct']:.1f}%")
            print(f"    水位线: {info['level_emoji']} {info['level_label']}")

        print("\n✅ Token 预估完成")
        return

    # 4. 选择模型
    if not args.email:
        # 交互模式才进入模型选择
        model_id = select_model_interactive()
    else:
        model_id = args.model
    print(f"🤖 使用模型: {model_id}")

    # 5. 执行分析
    print("\n" + "=" * 60)
    if args.profile_only:
        print("🎯 仅画像提取模式")
        print("=" * 60)
        t0 = time.perf_counter()
        profile = api.run_profile_only(email, date_range_ids, model_id)
        elapsed = time.perf_counter() - t0

        # 打印结果
        from pipeline.models import AnalysisResult
        dummy = AnalysisResult(
            employee_email=email,
            employee_name=email.split("@")[0],
            profile=profile,
            elapsed_seconds=round(elapsed, 2),
        )
        print_analysis_summary(dummy)

        # 保存结果
        out_path = args.output / f"{email.split('@')[0]}_profile.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(profile, f, ensure_ascii=False, indent=2)
        print(f"\n💾 结果已保存: {out_path}")

    elif args.growth_only:
        print("📈 仅成长分析模式")
        print("=" * 60)
        t0 = time.perf_counter()
        growth = api.run_growth_only(email, date_range_ids, model_id)
        elapsed = time.perf_counter() - t0

        from pipeline.models import AnalysisResult
        dummy = AnalysisResult(
            employee_email=email,
            employee_name=email.split("@")[0],
            growth=growth,
            elapsed_seconds=round(elapsed, 2),
        )
        print_analysis_summary(dummy)

        out_path = args.output / f"{email.split('@')[0]}_growth.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(growth, f, ensure_ascii=False, indent=2)
        print(f"\n💾 结果已保存: {out_path}")

    else:
        print("🚀 完整分析模式（Token 预估 + 画像提取 + 成长分析）")
        print("=" * 60)
        result = api.run_full_analysis(email, date_range_ids, model_id)
        print_analysis_summary(result)

        # 提示持久化路径
        result_files = list((args.output / email).glob("*_analysis.json"))
        if result_files:
            latest = sorted(result_files)[-1]
            print(f"\n💾 完整结果已保存: {latest}")

    print("\n" + "=" * 60)
    print("✅ 集成分析完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
