"""
成长时间轴分析器 — PRD 3.2

从清洗后的 Markdown 周报中提取：
- 功能1：问题闭环追踪（跨周 issue 的故事线）
- 功能2：剥洋葱式深度递进 vs 乱试验识别
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from pipeline.llm_client import CPELLMClient

logger = logging.getLogger(__name__)

# System Prompt 模板默认路径
_DEFAULT_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "growth_system.md"


def analyze_growth(
    markdown_content: str,
    llm_client: CPELLMClient,
    prompt_path: str | Path | None = None,
) -> dict[str, Any]:
    """
    从 Markdown 周报中提取成长时间轴分析。

    Args:
        markdown_content: 清洗后的 Markdown 周报全文
        llm_client: 已初始化的 LLM 客户端
        prompt_path: System Prompt 模板文件路径

    Returns:
        符合 JSON Schema 的时间轴分析结果字典

    Raises:
        FileNotFoundError: Prompt 文件不存在
        RuntimeError: LLM 调用失败
        ValueError: JSON 解析或格式校验失败
    """
    # 1. 加载 System Prompt
    path = Path(prompt_path) if prompt_path else _DEFAULT_PROMPT_PATH
    system_prompt = CPELLMClient.load_prompt_template(path)
    logger.info("已加载成长分析 System Prompt: %s (%d 字符)", path.name, len(system_prompt))

    # 2. 调用 LLM
    logger.info("开始调用 LLM 提取成长时间轴...")
    result = llm_client.call(
        system_prompt=system_prompt,
        user_content=markdown_content,
        parse_json=True,
    )

    # 3. 校验输出格式
    validated = _validate_growth_result(result)
    logger.info(
        "成长分析完成，提取 %d 个闭环问题，%d 个递进分析记录",
        len(validated.get("closed_loop_issues", [])),
        len(validated.get("growth_analysis", {}).get("recursive_logic", [])),
    )

    return validated


def _validate_growth_result(result: dict[str, Any]) -> dict[str, Any]:
    """
    校验并修复 LLM 输出的成长分析结果格式。

    Args:
        result: LLM 返回的原始 JSON dict

    Returns:
        校验后的结果字典
    """
    # 校验 closed_loop_issues
    issues = result.get("closed_loop_issues", [])
    if not isinstance(issues, list):
        issues = []

    validated_issues = []
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        validated_issue = _validate_issue(issue)
        validated_issues.append(validated_issue)

    result["closed_loop_issues"] = validated_issues

    # 校验 growth_analysis
    growth = result.get("growth_analysis", {})
    if not isinstance(growth, dict):
        growth = {}

    recursive = growth.get("recursive_logic", [])
    if not isinstance(recursive, list):
        recursive = []

    validated_recursive = []
    for item in recursive:
        if not isinstance(item, dict):
            continue
        validated_item = _validate_recursive_logic(item)
        validated_recursive.append(validated_item)

    growth["recursive_logic"] = validated_recursive

    # 校验 recurring_fix_patterns（新增功能3）
    recurring = growth.get("recurring_fix_patterns", [])
    if not isinstance(recurring, list):
        recurring = []

    validated_recurring = []
    for item in recurring:
        if not isinstance(item, dict):
            continue
        validated_recurring.append(_validate_recurring_pattern(item))

    growth["recurring_fix_patterns"] = validated_recurring
    result["growth_analysis"] = growth

    return result


def _validate_issue(issue: dict) -> dict:
    """校验单个闭环问题记录"""
    issue.setdefault("title", "未命名问题")
    issue.setdefault("first_appeared", "")
    issue.setdefault("resolved_date", None)
    issue.setdefault("duration_weeks", 0)
    issue.setdefault("status", "unknown")
    issue.setdefault("timeline", [])
    issue.setdefault("root_cause", "")
    issue.setdefault("solution", "")
    issue.setdefault("closure_quality", "")
    issue.setdefault("tags", [])

    # closure_quality 合法值校验
    _VALID_CLOSURE_QUALITIES = (
        "root_fix", "systematic_fix", "workaround", "escalated", "inconclusive", ""
    )
    if issue["closure_quality"] not in _VALID_CLOSURE_QUALITIES:
        logger.warning("闭环质量值 '%s' 不合法，已重置为空", issue["closure_quality"])
        issue["closure_quality"] = ""

    # 确保 timeline 是列表
    if not isinstance(issue["timeline"], list):
        issue["timeline"] = []

    # 校验 timeline 中的每个条目
    validated_timeline = []
    for entry in issue["timeline"]:
        if isinstance(entry, dict):
            entry.setdefault("date", "")
            entry.setdefault("progress", "")
            entry.setdefault("description", "")
            validated_timeline.append(entry)
    issue["timeline"] = validated_timeline

    # 确保 tags 是列表
    if not isinstance(issue["tags"], list):
        issue["tags"] = []

    # duration_weeks 类型校验
    try:
        issue["duration_weeks"] = int(issue["duration_weeks"])
    except (TypeError, ValueError):
        issue["duration_weeks"] = 0

    return issue


def _validate_recursive_logic(item: dict) -> dict:
    """校验单个递进分析记录"""
    item.setdefault("task_name", "")
    item.setdefault("pattern", "unknown")
    item.setdefault("reasoning_chain", [])
    item.setdefault("label", "")
    item.setdefault("evidence_period", "")

    # 确保 pattern 值合法（新增 surface_patch）
    if item["pattern"] not in ("depth_first", "surface_patch", "trial_error", "unknown"):
        item["pattern"] = "unknown"

    # 确保 reasoning_chain 是列表
    if not isinstance(item["reasoning_chain"], list):
        item["reasoning_chain"] = []

    return item


def _validate_recurring_pattern(item: dict) -> dict:
    """校验单个反复修补模式记录"""
    item.setdefault("module_name", "")
    item.setdefault("fix_count", 0)
    item.setdefault("span_weeks", 0)
    item.setdefault("has_refactor", False)
    item.setdefault("summary", "")

    # 类型校验
    try:
        item["fix_count"] = int(item["fix_count"])
    except (TypeError, ValueError):
        item["fix_count"] = 0
    try:
        item["span_weeks"] = int(item["span_weeks"])
    except (TypeError, ValueError):
        item["span_weeks"] = 0
    if not isinstance(item["has_refactor"], bool):
        item["has_refactor"] = bool(item["has_refactor"])

    return item
