"""
PRD 3.3: 全量上下文 FAQ 智能对话 — 终端 REPL 验证脚本

在没有 Web UI 的条件下，通过命令行交互式对话验证 FAQ 功能。

使用方式:
    # 交互式模式（默认）
    python scripts/run_chat.py

    # 命令行指定员工和时间范围
    python scripts/run_chat.py --email xiaoqianyun@jointelli.com --all-ranges --model deepseek/deepseek-chat

特殊命令:
    /quit   退出对话
    /reset  清空历史，开始新对话
    /history 查看对话历史
    /turns  查看当前轮次数
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# 确保 pipeline 包在 import 路径中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.api import CPEPipelineAPI
from pipeline.llm_config import list_model_configs


def setup_logging(verbose: bool = False):
    """配置日志（对话模式下默认关闭 logger，仅显示对话内容）"""
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def select_employee_interactive(api: CPEPipelineAPI) -> str:
    """交互式选择员工"""
    employees = api.get_employee_list()
    if not employees:
        print("❌ 未找到任何员工数据。")
        sys.exit(1)

    print("\n📋 可用员工:")
    for i, emp in enumerate(sorted(employees, key=lambda x: x["email"]), 1):
        print(f"  {i:2d}. {emp['name']:20s} ({emp['email']})")

    while True:
        try:
            choice = input(f"\n请选择员工 [1-{len(employees)}]: ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(employees):
                return sorted(employees, key=lambda x: x["email"])[idx]["email"]
        except (ValueError, KeyboardInterrupt):
            print("\n已取消。")
            sys.exit(0)


def select_ranges_interactive(api: CPEPipelineAPI, email: str) -> list[str]:
    """交互式选择时间范围"""
    ranges = api.get_employee_report_ranges(email)
    if not ranges:
        print(f"❌ 未找到 {email} 的周报数据。")
        sys.exit(1)

    print(f"\n📅 可用周报范围 ({len(ranges)} 个):")
    for i, r in enumerate(ranges, 1):
        print(f"  {i:2d}. {r['start']} ~ {r['end']}")
    print(f"   0. 全部选择")

    while True:
        try:
            choice = input("\n请选择 [0=全部, 或编号逗号分隔]: ").strip()
            if choice == "0":
                return [r["id"] for r in ranges]
            indices = [int(x.strip()) - 1 for x in choice.split(",")]
            selected = [ranges[idx]["id"] for idx in indices if 0 <= idx < len(ranges)]
            if selected:
                return selected
        except (ValueError, KeyboardInterrupt):
            print("\n已取消。")
            sys.exit(0)


def select_model_interactive() -> str:
    """交互式选择模型"""
    configs = list_model_configs(enabled_only=True)
    if not configs:
        return "deepseek/deepseek-chat"

    print(f"\n🤖 可用模型:")
    for i, c in enumerate(configs, 1):
        key_hint = "✅" if c.api_key else "❌"
        print(f"  {i:2d}. {c.display_name:25s} ({c.model_id})  {key_hint}")

    while True:
        try:
            choice = input(f"\n请选择模型 [1-{len(configs)}, 回车用第1个]: ").strip()
            if not choice:
                return configs[0].model_id
            idx = int(choice) - 1
            if 0 <= idx < len(configs):
                return configs[idx].model_id
        except (ValueError, KeyboardInterrupt):
            print("\n已取消。")
            sys.exit(0)


def run_chat_repl(api: CPEPipelineAPI, session_id: str):
    """交互式对话 REPL 主循环"""
    print("\n" + "═" * 60)
    print("  💬 FAQ 智能对话已就绪")
    print("  输入您的问题，按回车发送")
    print("  特殊命令: /quit 退出  /reset 重置  /history 查看历史")
    print("═" * 60)

    while True:
        try:
            user_input = input("\n🧑 您: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n👋 对话结束。")
            break

        if not user_input:
            continue

        # 处理特殊命令
        if user_input.lower() == "/quit":
            print("\n👋 对话结束。")
            break

        elif user_input.lower() == "/reset":
            # 获取引擎并重置
            engine = api._chat_sessions.get(session_id)
            if engine:
                engine.reset()
            print("🔄 对话历史已清空，可以开始新话题。")
            continue

        elif user_input.lower() == "/history":
            history = api.get_chat_history(session_id)
            if not history:
                print("📭 暂无对话历史。")
            else:
                print(f"\n📜 对话历史 ({len(history) // 2} 轮):")
                print("-" * 50)
                for msg in history:
                    role_icon = "🧑" if msg["role"] == "user" else "🤖"
                    content_preview = msg["content"][:100]
                    if len(msg["content"]) > 100:
                        content_preview += "..."
                    print(f"  {role_icon} {content_preview}")
            continue

        elif user_input.lower() == "/turns":
            engine = api._chat_sessions.get(session_id)
            if engine:
                print(f"📊 当前已完成 {engine.turn_count} 轮对话")
            continue

        # 正常对话
        print("\n🤖 助手: ", end="", flush=True)
        try:
            result = api.chat(session_id, user_input)
            print(result["content"])
            print(f"\n  [第 {result['turn']} 轮]", end="")
        except Exception as e:
            print(f"\n❌ 出错: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="CPE-Forge FAQ 智能对话（终端 REPL 验证）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--email", "-e", type=str, help="员工邮箱")
    parser.add_argument("--all-ranges", action="store_true", help="选择全部时间范围")
    parser.add_argument("--ranges", "-r", type=str, help="时间范围 ID（逗号分隔）")
    parser.add_argument("--model", "-m", type=str, default="deepseek/deepseek-chat",
                        help="LLM 模型标识")
    parser.add_argument("--input", "-i", type=Path, default=Path("attachments"))
    parser.add_argument("--output", "-o", type=Path, default=Path("output"))
    parser.add_argument("--verbose", "-v", action="store_true", help="显示详细日志")

    args = parser.parse_args()
    setup_logging(verbose=args.verbose)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║    CPE-Forge FAQ 智能对话                                ║")
    print("║    全量上下文注入 · 连续多轮对话                         ║")
    print("╚══════════════════════════════════════════════════════════╝")

    api = CPEPipelineAPI(args.input, args.output)

    # 1. 选择员工
    if args.email:
        email = args.email
        print(f"\n📧 员工: {email}")
    else:
        email = select_employee_interactive(api)

    # 2. 选择时间范围
    if args.all_ranges:
        ranges = api.get_employee_report_ranges(email)
        date_range_ids = [r["id"] for r in ranges]
        print(f"📅 已选择全部 {len(date_range_ids)} 个时间范围")
    elif args.ranges:
        date_range_ids = [r.strip() for r in args.ranges.split(",")]
    else:
        date_range_ids = select_ranges_interactive(api, email)

    # 3. 选择模型
    if not args.email:
        model_id = select_model_interactive()
    else:
        model_id = args.model
    print(f"🤖 使用模型: {model_id}")

    # 4. 创建对话会话
    print("\n⏳ 正在初始化对话上下文...")
    session_id = api.start_chat_session(email, date_range_ids, model_id)
    print(f"✅ 会话已创建 (ID: {session_id[:8]}...)")

    # 5. 进入 REPL
    run_chat_repl(api, session_id)


if __name__ == "__main__":
    main()
