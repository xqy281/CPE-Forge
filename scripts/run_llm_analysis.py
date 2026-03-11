"""
端到端 LLM 分析调试脚本 — CPE-Forge AIGC 分析入口

支持多种调试模式，方便独立打磨每个 System Prompt：

用法:
    # 仅 Token 预估（不调用 LLM）
    python scripts/run_llm_analysis.py --email xiaoqianyun@jointelli.com --token-only

    # 仅画像提取（调试 profile System Prompt）
    python scripts/run_llm_analysis.py --email xiaoqianyun@jointelli.com --profile-only --model deepseek/deepseek-chat

    # 仅成长时间轴（调试 growth System Prompt）
    python scripts/run_llm_analysis.py --email xiaoqianyun@jointelli.com --growth-only --model deepseek/deepseek-chat

    # 全流程（Token预估 + 画像 + 时间轴）
    python scripts/run_llm_analysis.py --email xiaoqianyun@jointelli.com --model deepseek/deepseek-chat

    # 从文件直接读取（跳过清洗管线）
    python scripts/run_llm_analysis.py --from-file output/xiaoqianyun@jointelli.com.md --profile-only

    # 使用自定义 System Prompt 文件
    python scripts/run_llm_analysis.py --from-file output/xiaoqianyun@jointelli.com.md --profile-only --prompt-file prompts/my_custom.md
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
from pipeline.llm_client import CPELLMClient
from pipeline.llm_config import list_model_configs, init_default_configs, load_model_config
from pipeline.token_estimator import estimate_markdown_tokens
from pipeline.profile_extractor import extract_profile
from pipeline.growth_analyzer import analyze_growth


def setup_logging(verbose: bool = False):
    """配置日志"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def load_markdown_content(
    from_file: Path | None = None,
    email: str = "",
    attachments_dir: Path = Path("attachments"),
    output_dir: Path = Path("output"),
) -> tuple[str, str]:
    """
    加载 Markdown 周报内容。

    优先使用 --from-file 直接读取，否则通过 API 从清洗管线获取全量数据。

    Returns:
        (markdown_content, employee_display_name)
    """
    if from_file:
        if not from_file.exists():
            print(f"错误: 文件不存在: {from_file}", file=sys.stderr)
            sys.exit(1)
        content = from_file.read_text(encoding="utf-8")
        name = from_file.stem.split("@")[0] if "@" in from_file.stem else from_file.stem
        print(f"📄 从文件加载: {from_file} ({len(content)} 字符)")
        return content, name

    if not email:
        print("错误: 必须指定 --email 或 --from-file", file=sys.stderr)
        sys.exit(1)

    # 通过 API 加载
    api = CPEPipelineAPI(attachments_dir, output_dir)

    # 先检查是否已有清洗后的 Markdown 缓存
    md_file = output_dir / f"{email}.md"
    if md_file.exists():
        content = md_file.read_text(encoding="utf-8")
        name = email.split("@")[0]
        print(f"📄 从已有缓存加载: {md_file} ({len(content)} 字符)")
        return content, name

    # 触发清洗
    print(f"🔧 触发清洗管线，为 {email} 生成 Markdown...")
    ranges = api.get_employee_report_ranges(email)
    if not ranges:
        print(f"错误: 未找到 {email} 的有效周报数据", file=sys.stderr)
        sys.exit(1)

    all_ids = [r["id"] for r in ranges]
    md_path = api.generate_cleaned_markdown(email, all_ids)
    content = md_path.read_text(encoding="utf-8")
    name = email.split("@")[0]
    print(f"✅ 清洗完成: {md_path} ({len(content)} 字符)")
    return content, name


def run_token_estimate(content: str, model: str, name: str):
    """运行 Token 预估"""
    print("\n" + "=" * 60)
    print("📊 Token 预估")
    print("=" * 60)

    result = estimate_markdown_tokens(content, model=model)
    info = result.to_dict()

    print(f"  员工: {name}")
    print(f"  模型: {info['model']}")
    print(f"  Token 数: {info['token_count']:,}")
    print(f"  模型上限: {info['model_limit']:,}")
    print(f"  利用率: {info['utilization_pct']:.1f}%")
    print(f"  水位线: {info['level_emoji']} {info['level_label']}")

    return info


def run_profile_extraction(
    content: str, model: str, name: str,
    prompt_file: Path | None, output_dir: Path,
):
    """运行画像提取"""
    print("\n" + "=" * 60)
    print("🎯 双层能力画像提取")
    print("=" * 60)

    client = CPELLMClient.from_config(model)
    t0 = time.perf_counter()
    result = extract_profile(content, client, prompt_path=prompt_file)
    elapsed = time.perf_counter() - t0

    print(f"  耗时: {elapsed:.1f}s")
    print(f"\n  外层雷达图（技术广度 — 双轨制）:")
    print(f"    {'维度':25s} {'精力占比':10s}  {'投入深度':8s}")
    print(f"    {'─' * 55}")
    for dim, entry in result["radar_outer"].items():
        if isinstance(entry, dict):
            prop = entry.get("proportion", 0.0)
            depth = entry.get("depth", 0)
        else:
            prop = float(entry) if entry else 0.0
            depth = 0
        bar = "█" * int(prop * 20) + "░" * (20 - int(prop * 20))
        stars = "★" * depth + "☆" * (5 - depth)
        print(f"    {dim:25s} {bar} {prop:.0%}   {stars}")

    print(f"\n  内层内核（工程素养）:")
    for dim in ["truth_seeking", "pragmatic", "rigorous"]:
        inner = result["radar_inner"][dim]
        print(f"    {dim:15s}  Lv{inner['level']}  ({inner['score']:.2f})")
        for ev in inner.get("evidence", [])[:2]:
            print(f"      📌 {ev[:80]}...")

    if result.get("summary"):
        print(f"\n  总结: {result['summary']}")

    # 保存结果
    out_path = output_dir / f"{name}_profile.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n  💾 结果已保存: {out_path}")

    return result


def run_growth_analysis(
    content: str, model: str, name: str,
    prompt_file: Path | None, output_dir: Path,
):
    """运行成长时间轴分析"""
    print("\n" + "=" * 60)
    print("📈 成长时间轴分析")
    print("=" * 60)

    client = CPELLMClient.from_config(model)
    t0 = time.perf_counter()
    result = analyze_growth(content, client, prompt_path=prompt_file)
    elapsed = time.perf_counter() - t0

    print(f"  耗时: {elapsed:.1f}s")

    issues = result.get("closed_loop_issues", [])
    print(f"\n  问题闭环追踪: 共 {len(issues)} 个")
    for i, issue in enumerate(issues[:5]):
        status_icon = "✅" if issue.get("status") == "resolved" else "🔄"
        print(f"    {status_icon} [{issue.get('first_appeared', '?')}] {issue['title']}")
        if issue.get("duration_weeks"):
            print(f"       跨越 {issue['duration_weeks']} 周")
        if issue.get("root_cause"):
            print(f"       根因: {issue['root_cause'][:60]}...")
    if len(issues) > 5:
        print(f"    ... 还有 {len(issues) - 5} 个")

    recursive = result.get("growth_analysis", {}).get("recursive_logic", [])
    print(f"\n  递进分析: 共 {len(recursive)} 个")
    for item in recursive[:5]:
        icon = "🧅" if item.get("pattern") == "depth_first" else "🎲"
        print(f"    {icon} {item.get('task_name', '?')} → {item.get('label', '?')}")
        chain = item.get("reasoning_chain", [])
        if chain:
            print(f"       链路: {' → '.join(chain[:4])}")

    # 保存结果
    out_path = output_dir / f"{name}_growth.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n  💾 结果已保存: {out_path}")

    return result


def main():
    parser = argparse.ArgumentParser(
        description="CPE-Forge AIGC 分析调试工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 仅 Token 预估
  python scripts/run_llm_analysis.py --email xiaoqianyun@jointelli.com --token-only

  # 画像提取调试
  python scripts/run_llm_analysis.py --from-file output/xiaoqianyun@jointelli.com.md --profile-only --model deepseek/deepseek-chat

  # 全流程
  python scripts/run_llm_analysis.py --email xiaoqianyun@jointelli.com --model deepseek/deepseek-chat
        """,
    )

    # 数据源参数
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--email", "-e", type=str, help="员工邮箱")
    source.add_argument("--from-file", "-f", type=Path, help="直接从 Markdown 文件读取（跳过清洗管线）")

    # 模型参数
    parser.add_argument("--model", "-m", type=str, default="deepseek/deepseek-chat",
                        help="LLM 模型标识 (默认: deepseek/deepseek-chat)")

    # 运行模式
    parser.add_argument("--token-only", action="store_true", help="仅计算 Token（不调用 LLM）")
    parser.add_argument("--profile-only", action="store_true", help="仅提取双层画像")
    parser.add_argument("--growth-only", action="store_true", help="仅提取成长时间轴")

    # 模型配置管理
    parser.add_argument("--list-models", action="store_true",
                        help="列出所有已配置的 LLM 模型及其参数")
    parser.add_argument("--init-configs", action="store_true",
                        help="初始化默认模型配置文件到 config/models/")

    # 自定义 prompt
    parser.add_argument("--prompt-file", "-p", type=Path, default=None,
                        help="自定义 System Prompt 文件路径")

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

    # 模型配置管理命令
    if args.init_configs:
        print("🔧 初始化默认模型配置...")
        init_default_configs()
        configs = list_model_configs()
        print(f"✅ 已初始化 {len(configs)} 个模型配置到 config/models/")
        print("   请编辑对应 JSON 文件填入 API Key")
        return

    if args.list_models:
        configs = list_model_configs()
        if not configs:
            print("未找到模型配置。请先运行: --init-configs")
            return
        print(f"\n📋 已配置的 LLM 模型 (共 {len(configs)} 个):\n")
        for c in configs:
            status = "✅" if c.enabled else "❌"
            key_hint = "***" + c.api_key[-4:] if c.api_key else "未配置"
            print(f"  {status} {c.display_name}")
            print(f"     model_id:    {c.model_id}")
            print(f"     temperature: {c.temperature}")
            print(f"     top_p:       {c.top_p}")
            print(f"     max_tokens:  {c.max_tokens}")
            print(f"     api_key:     {key_hint}")
            print(f"     描述:        {c.description}")
            print()
        return

    # 加载内容
    content, name = load_markdown_content(
        from_file=args.from_file,
        email=args.email or "",
        attachments_dir=args.input,
        output_dir=args.output,
    )

    # 确定运行模式
    run_all = not (args.token_only or args.profile_only or args.growth_only)

    # 1. Token 预估（总是运行）
    if run_all or args.token_only:
        run_token_estimate(content, args.model, name)

    if args.token_only:
        print("\n✅ Token 预估完成（--token-only 模式，不调用 LLM）")
        return

    # 2. 画像提取
    if run_all or args.profile_only:
        prompt = args.prompt_file
        run_profile_extraction(content, args.model, name, prompt, args.output)

    # 3. 成长时间轴
    if run_all or args.growth_only:
        prompt = args.prompt_file
        run_growth_analysis(content, args.model, name, prompt, args.output)

    print("\n" + "=" * 60)
    print("✅ 分析完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
