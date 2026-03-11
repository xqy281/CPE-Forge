"""
Token 预估模块 — PRD 2.3 Token 极致压缩与预检

提供精确的 Token 计数、水位线判定和模型上下文限制查询功能。
使用 tiktoken 作为主要 Token 计算引擎，litellm 提供模型元数据查询。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import tiktoken

logger = logging.getLogger(__name__)

# ============================================================================
# 常量定义：已知模型的上下文窗口大小（Token 数）
# 当 litellm 无法获取信息时作为兜底
# ============================================================================
_MODEL_CONTEXT_LIMITS: dict[str, int] = {
    # OpenAI 系列
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "gpt-4-turbo": 128000,
    "gpt-4": 8192,
    "gpt-3.5-turbo": 16385,
    # Anthropic 系列
    "claude-3.5-sonnet": 200000,
    "claude-3-sonnet": 200000,
    "claude-3-haiku": 200000,
    "claude-3-opus": 200000,
    # DeepSeek 系列
    "deepseek-chat": 65536,
    "deepseek/deepseek-chat": 65536,
    "deepseek-reasoner": 65536,
    "deepseek/deepseek-reasoner": 65536,
    # Gemini 系列
    "gemini/gemini-2.0-flash": 1048576,
    "gemini/gemini-2.5-pro": 1048576,
    "gemini/gemini-2.5-flash": 1048576,
    "gemini-2.0-flash": 1048576,
    "gemini-2.5-pro": 1048576,
}

_DEFAULT_CONTEXT_LIMIT = 128000  # 默认兜底值


class TokenLevel(Enum):
    """
    Token 水位线级别

    按照 PRD 2.3 定义的三级水位线：
    - 绿色: < 50k, 安全可提交
    - 黄色: 50k ~ 100k, 需要注意
    - 红色: > 100k 或 > 模型上限, 有崩溃风险
    """
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"

    @property
    def label(self) -> str:
        """返回中文标签"""
        return {"green": "绿色", "yellow": "黄色", "red": "红色"}[self.value]

    @property
    def emoji(self) -> str:
        """返回表情符号"""
        return {"green": "🟢", "yellow": "🟡", "red": "🔴"}[self.value]


@dataclass
class TokenEstimate:
    """
    Token 预估结果数据对象

    Attributes:
        token_count: 精确的 Token 数量
        level: 水位线级别（绿/黄/红）
        model_limit: 模型的上下文窗口上限
        utilization_pct: Token 利用率百分比（token_count / model_limit * 100）
        model: 计算使用的模型名称
    """
    token_count: int
    level: TokenLevel
    model_limit: int
    utilization_pct: float
    model: str = "gpt-4o"

    def to_dict(self) -> dict:
        """序列化为字典，方便 JSON 输出"""
        return {
            "token_count": self.token_count,
            "level": self.level.value,
            "level_label": self.level.label,
            "level_emoji": self.level.emoji,
            "model_limit": self.model_limit,
            "utilization_pct": round(self.utilization_pct, 2),
            "model": self.model,
        }


# ============================================================================
# 核心函数
# ============================================================================

def count_tokens(text: str, model: str = "gpt-4o") -> int:
    """
    计算文本的精确 Token 数。

    优先使用 tiktoken（OpenAI 系列模型精确计算），
    对于不支持的模型退回到基于字符数的估算。

    Args:
        text: 待计算的文本内容
        model: 模型名称，用于选择合适的分词器

    Returns:
        Token 数量
    """
    if not text:
        return 0

    # 提取纯模型名称（去掉 provider 前缀如 "deepseek/"）
    pure_model = model.split("/")[-1] if "/" in model else model

    # 尝试使用 tiktoken 精确计算
    try:
        encoding = tiktoken.encoding_for_model(pure_model)
        return len(encoding.encode(text))
    except KeyError:
        pass

    # tiktoken 不支持此模型，尝试使用 cl100k_base 编码（GPT-4 系列通用）
    try:
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except Exception as e:
        logger.warning("tiktoken 编码失败，使用字符估算: %s", e)

    # 最终兜底：基于字符数的粗略估算
    # 英文约 4 字符/token，中文约 1.5 字符/token
    # 取一个折中估算：约 2 字符/token
    return len(text) // 2


def assess_token_level(
    token_count: int,
    model_context_limit: Optional[int] = None,
) -> TokenLevel:
    """
    根据 Token 数量判定水位线级别。

    判定规则（PRD 2.3）：
    - 绿色: token_count < 50k
    - 黄色: 50k <= token_count < 100k
    - 红色: token_count >= 100k 或 token_count >= model_context_limit

    Args:
        token_count: Token 数量
        model_context_limit: 模型上下文窗口上限（可选）。
            若提供且 token_count 超过此值，直接判定为红色。

    Returns:
        TokenLevel 枚举值
    """
    # 如果提供了模型上限且 Token 数超过，直接红色
    if model_context_limit and token_count >= model_context_limit:
        return TokenLevel.RED

    if token_count >= 100000:
        return TokenLevel.RED
    elif token_count >= 50000:
        return TokenLevel.YELLOW
    else:
        return TokenLevel.GREEN


def get_model_context_limit(model: str) -> int:
    """
    获取指定模型的上下文窗口大小（Token 数）。

    优先从内置字典查询，找不到则尝试通过 litellm 获取，
    最终兜底返回默认值。

    Args:
        model: 模型名称（如 "gpt-4o"、"deepseek/deepseek-chat"）

    Returns:
        上下文窗口大小（Token 数）
    """
    # 1. 先查内置字典
    if model in _MODEL_CONTEXT_LIMITS:
        return _MODEL_CONTEXT_LIMITS[model]

    # 2. 提取纯模型名再查一次
    pure_model = model.split("/")[-1] if "/" in model else model
    if pure_model in _MODEL_CONTEXT_LIMITS:
        return _MODEL_CONTEXT_LIMITS[pure_model]

    # 3. 尝试通过 litellm 获取
    try:
        import litellm
        model_info = litellm.get_model_info(model)
        if model_info and "max_input_tokens" in model_info:
            limit = model_info["max_input_tokens"]
            if isinstance(limit, int) and limit > 0:
                return limit
    except Exception as e:
        logger.debug("litellm 获取模型信息失败: %s (模型: %s)", e, model)

    # 4. 兜底默认值
    logger.info("未找到模型 '%s' 的上下文限制，使用默认值 %d", model, _DEFAULT_CONTEXT_LIMIT)
    return _DEFAULT_CONTEXT_LIMIT


def estimate_markdown_tokens(
    text: str,
    model: str = "gpt-4o",
) -> TokenEstimate:
    """
    对 Markdown 文本进行完整的 Token 预估。

    包含 Token 计数、水位线判定和利用率计算。

    Args:
        text: Markdown 格式的周报文本
        model: 模型名称

    Returns:
        TokenEstimate 数据对象
    """
    token_count = count_tokens(text, model=model)
    model_limit = get_model_context_limit(model)
    level = assess_token_level(token_count, model_context_limit=model_limit)
    utilization_pct = (token_count / model_limit * 100) if model_limit > 0 else 0.0

    return TokenEstimate(
        token_count=token_count,
        level=level,
        model_limit=model_limit,
        utilization_pct=utilization_pct,
        model=model,
    )
