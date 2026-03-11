"""
双层能力画像提取器 — PRD 3.1

从清洗后的 Markdown 周报中提取员工的双层能力画像：
- 外层雷达图（5维技术广度与投入度）
- 内层内核（3维工程素养成熟度）
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from pipeline.llm_client import CPELLMClient

logger = logging.getLogger(__name__)

# System Prompt 模板默认路径
_DEFAULT_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "profile_system.md"

# 外层雷达图必须包含的维度字段
_REQUIRED_OUTER_DIMS = [
    "system_platform",
    "driver_development",
    "application_software",
    "wireless_communication",
    "sqa_quality",
]

# 内层必须包含的维度字段
_REQUIRED_INNER_DIMS = [
    "truth_seeking",
    "pragmatic",
    "rigorous",
]


def extract_profile(
    markdown_content: str,
    llm_client: CPELLMClient,
    prompt_path: str | Path | None = None,
) -> dict[str, Any]:
    """
    从 Markdown 周报中提取双层能力画像。

    Args:
        markdown_content: 清洗后的 Markdown 周报全文
        llm_client: 已初始化的 LLM 客户端
        prompt_path: System Prompt 模板文件路径（为 None 时使用默认路径）

    Returns:
        符合 JSON Schema 的画像结果字典

    Raises:
        FileNotFoundError: Prompt 文件不存在
        RuntimeError: LLM 调用失败
        ValueError: JSON 解析或格式校验失败
    """
    # 1. 加载 System Prompt
    path = Path(prompt_path) if prompt_path else _DEFAULT_PROMPT_PATH
    system_prompt = CPELLMClient.load_prompt_template(path)
    logger.info("已加载画像提取 System Prompt: %s (%d 字符)", path.name, len(system_prompt))

    # 2. 调用 LLM
    logger.info("开始调用 LLM 提取双层能力画像...")
    result = llm_client.call(
        system_prompt=system_prompt,
        user_content=markdown_content,
        parse_json=True,
    )

    # 3. 校验输出格式
    validated = _validate_profile_result(result)
    proportions = sum(
        entry["proportion"] for entry in validated["radar_outer"].values()
        if isinstance(entry, dict)
    )
    logger.info("画像提取完成，外层雷达5维度 proportion 合计: %.2f", proportions)

    return validated


def _validate_profile_result(result: dict[str, Any]) -> dict[str, Any]:
    """
    校验并修复 LLM 输出的画像结果格式。

    确保包含所有必要字段，缺失时填充默认值。

    Args:
        result: LLM 返回的原始 JSON dict

    Returns:
        校验后的结果字典
    """
    # 校验外层雷达（双轨制：proportion + depth）
    radar_outer = result.get("radar_outer", {})
    for dim in _REQUIRED_OUTER_DIMS:
        if dim not in radar_outer:
            logger.warning("外层雷达缺失维度 '%s'，已补充默认值", dim)
            radar_outer[dim] = {"proportion": 0.0, "depth": 0}
        elif isinstance(radar_outer[dim], dict):
            # 双轨结构 {proportion, depth}：校验必要字段
            entry = radar_outer[dim]
            try:
                entry["proportion"] = float(entry.get("proportion", 0.0))
            except (TypeError, ValueError):
                entry["proportion"] = 0.0
            try:
                entry["depth"] = int(entry.get("depth", 0))
                entry["depth"] = max(0, min(5, entry["depth"]))
            except (TypeError, ValueError):
                entry["depth"] = 0
        else:
            # 兼容旧格式：纯浮点数 → 转换为双轨结构（depth 默认根据 proportion 推估）
            try:
                proportion = float(radar_outer[dim])
            except (TypeError, ValueError):
                proportion = 0.0
            # 粗略推估 depth：0~0.05→0, 0.05~0.15→1, 0.15~0.25→2, 0.25~0.35→3, 0.35~0.45→4, >0.45→5
            estimated_depth = min(5, int(proportion * 12))
            radar_outer[dim] = {"proportion": proportion, "depth": estimated_depth}
            logger.info("维度 '%s' 从旧格式转换为双轨制 (proportion=%.2f, depth=%d)",
                        dim, proportion, estimated_depth)

    # 归一化 proportion 检查（允许 5% 的误差）
    total = sum(entry["proportion"] for entry in radar_outer.values()
                if isinstance(entry, dict))
    if total > 0 and abs(total - 1.0) > 0.05:
        logger.warning("外层雷达 proportion 权重和为 %.3f，进行归一化修正", total)
        for dim in radar_outer:
            if isinstance(radar_outer[dim], dict):
                radar_outer[dim]["proportion"] = round(
                    radar_outer[dim]["proportion"] / total, 4
                )

    result["radar_outer"] = radar_outer

    # 校验内层内核
    radar_inner = result.get("radar_inner", {})
    for dim in _REQUIRED_INNER_DIMS:
        if dim not in radar_inner:
            logger.warning("内层内核缺失维度 '%s'，已补充默认值", dim)
            radar_inner[dim] = {"level": 1, "score": 0.0, "evidence": []}
        else:
            inner_dim = radar_inner[dim]
            if not isinstance(inner_dim, dict):
                radar_inner[dim] = {"level": 1, "score": 0.0, "evidence": []}
            else:
                # 确保必要字段存在
                inner_dim.setdefault("level", 1)
                inner_dim.setdefault("score", 0.0)
                inner_dim.setdefault("evidence", [])
                # 类型校验
                try:
                    inner_dim["level"] = int(inner_dim["level"])
                    inner_dim["level"] = max(1, min(5, inner_dim["level"]))
                except (TypeError, ValueError):
                    inner_dim["level"] = 1
                try:
                    inner_dim["score"] = float(inner_dim["score"])
                except (TypeError, ValueError):
                    inner_dim["score"] = 0.0
                if not isinstance(inner_dim["evidence"], list):
                    inner_dim["evidence"] = []

    result["radar_inner"] = radar_inner

    # 确保 summary 字段存在
    result.setdefault("summary", "")

    return result
