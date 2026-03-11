"""
LLM 模型配置管理 — 每个模型独立的参数持久化

设计要点：
- 每个模型拥有独立的 JSON 配置文件，存放在 config/models/ 目录下
- 配置包含 temperature、top_p、max_tokens、api_key 等参数
- 面向 Web UI 设计：提供增删改查 API，方便前端枚举和配置模型
- API Key 仅存储在本地配置文件中，不会硬编码到代码里

目录结构：
    config/
      models/
        deepseek_deepseek-chat.json
        gpt-4o.json
        gemini_gemini-2.0-flash.json
        ...
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# 配置文件根目录（相对于项目根）
_DEFAULT_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config" / "models"


@dataclass
class LLMModelConfig:
    """
    单个 LLM 模型的完整配置。

    Attributes:
        model_id: LiteLLM 模型标识（如 "deepseek/deepseek-chat"）
        display_name: 前端展示名称
        provider: 模型提供商（如 "deepseek", "openai"）
        api_key: API 密钥（可为空，运行时从环境变量兜底读取）
        api_base: 自定义 API 端点（可选，用于本地部署或代理）
        temperature: 生成温度 (0.0~2.0)
        top_p: 核采样参数 (0.0~1.0)
        max_tokens: 最大生成 Token 数
        max_retries: 重试次数
        context_window: 模型上下文窗口大小（Token 数）
        enabled: 是否启用（Web UI 可关闭不需要的模型）
        description: 模型描述说明
    """
    model_id: str = ""
    display_name: str = ""
    provider: str = ""
    api_key: str = ""
    api_base: str = ""
    temperature: float = 0.3
    top_p: float = 1.0
    max_tokens: int = 8192
    max_retries: int = 3
    context_window: int = 128000
    enabled: bool = True
    description: str = ""

    def to_dict(self) -> dict:
        """序列化为字典（用于 JSON 持久化）"""
        return asdict(self)

    def to_safe_dict(self) -> dict:
        """
        序列化为安全字典（隐藏 API Key，用于前端展示）。
        API Key 只显示末尾 4 位。
        """
        d = self.to_dict()
        if d["api_key"]:
            d["api_key"] = "***" + d["api_key"][-4:]
        return d

    @classmethod
    def from_dict(cls, data: dict) -> LLMModelConfig:
        """从字典反序列化"""
        # 只取 dataclass 中定义的字段，忽略多余字段
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)


def _model_id_to_filename(model_id: str) -> str:
    """
    将模型 ID 转换为安全的文件名。

    例: "deepseek/deepseek-chat" → "deepseek_deepseek-chat"
    """
    return re.sub(r'[/\\:*?"<>|]', '_', model_id)


def _get_config_path(model_id: str, config_dir: Path | None = None) -> Path:
    """获取指定模型的配置文件路径"""
    base_dir = Path(config_dir) if config_dir else _DEFAULT_CONFIG_DIR
    filename = _model_id_to_filename(model_id) + ".json"
    return base_dir / filename


# ============================================================================
# 核心 API：增删改查
# ============================================================================

def load_model_config(
    model_id: str,
    config_dir: Path | None = None,
) -> Optional[LLMModelConfig]:
    """
    加载指定模型的配置。

    若配置文件不存在，返回 None。

    Args:
        model_id: 模型标识
        config_dir: 配置文件目录（默认: config/models/）

    Returns:
        LLMModelConfig 或 None
    """
    path = _get_config_path(model_id, config_dir)
    if not path.exists():
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        config = LLMModelConfig.from_dict(data)
        logger.debug("已加载模型配置: %s (从 %s)", model_id, path.name)
        return config
    except Exception as e:
        logger.error("加载模型配置失败: %s, 错误: %s", path, e)
        return None


def save_model_config(
    config: LLMModelConfig,
    config_dir: Path | None = None,
) -> Path:
    """
    保存模型配置到文件。

    若目录不存在会自动创建。

    Args:
        config: 模型配置对象
        config_dir: 配置文件目录

    Returns:
        保存的文件路径
    """
    base_dir = Path(config_dir) if config_dir else _DEFAULT_CONFIG_DIR
    base_dir.mkdir(parents=True, exist_ok=True)

    path = _get_config_path(config.model_id, config_dir)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config.to_dict(), f, ensure_ascii=False, indent=2)

    logger.info("已保存模型配置: %s → %s", config.model_id, path.name)
    return path


def delete_model_config(
    model_id: str,
    config_dir: Path | None = None,
) -> bool:
    """
    删除指定模型的配置文件。

    Args:
        model_id: 模型标识
        config_dir: 配置文件目录

    Returns:
        是否成功删除
    """
    path = _get_config_path(model_id, config_dir)
    if path.exists():
        path.unlink()
        logger.info("已删除模型配置: %s", model_id)
        return True
    return False


def list_model_configs(
    config_dir: Path | None = None,
    enabled_only: bool = False,
) -> list[LLMModelConfig]:
    """
    列出所有已配置的模型。

    面向 Web UI 设计：前端调用此接口获取可选模型列表。

    Args:
        config_dir: 配置文件目录
        enabled_only: 是否只返回已启用的模型

    Returns:
        模型配置列表（按 display_name 排序）
    """
    base_dir = Path(config_dir) if config_dir else _DEFAULT_CONFIG_DIR
    if not base_dir.exists():
        return []

    configs = []
    for json_file in sorted(base_dir.glob("*.json")):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            config = LLMModelConfig.from_dict(data)
            if enabled_only and not config.enabled:
                continue
            configs.append(config)
        except Exception as e:
            logger.warning("跳过无效配置文件 %s: %s", json_file.name, e)

    return configs


def update_model_config(
    model_id: str,
    updates: dict,
    config_dir: Path | None = None,
) -> Optional[LLMModelConfig]:
    """
    部分更新指定模型的配置。

    面向 Web UI 设计：前端只传需要修改的字段。

    Args:
        model_id: 模型标识
        updates: 需要更新的字段键值对
        config_dir: 配置文件目录

    Returns:
        更新后的配置，若模型不存在则返回 None
    """
    config = load_model_config(model_id, config_dir)
    if config is None:
        return None

    # 只更新合法字段
    valid_fields = {f.name for f in LLMModelConfig.__dataclass_fields__.values()}
    for key, value in updates.items():
        if key in valid_fields and key != "model_id":  # model_id 不允许修改
            setattr(config, key, value)

    save_model_config(config, config_dir)
    return config


def get_or_create_config(
    model_id: str,
    config_dir: Path | None = None,
) -> LLMModelConfig:
    """
    获取模型配置，若不存在则创建默认配置。

    对运行时调用友好：即使用户未手动配置，也能基于合理默认值运行。

    Args:
        model_id: 模型标识
        config_dir: 配置文件目录

    Returns:
        模型配置
    """
    config = load_model_config(model_id, config_dir)
    if config:
        return config

    # 创建默认配置
    config = _build_default_config(model_id)
    save_model_config(config, config_dir)
    return config


def apply_config_to_env(config: LLMModelConfig):
    """
    将配置中的 API Key 应用到环境变量。

    LiteLLM 从环境变量读取 API Key，此函数在每次 LLM 调用前调用。

    Args:
        config: 模型配置
    """
    if not config.api_key:
        return

    provider_env_map = {
        "deepseek": "DEEPSEEK_API_KEY",
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "gpt": "OPENAI_API_KEY",
        "claude": "ANTHROPIC_API_KEY",
    }

    env_key = provider_env_map.get(config.provider)
    if not env_key:
        # 尝试从 model_id 前缀推断
        prefix = config.model_id.split("/")[0] if "/" in config.model_id else ""
        env_key = provider_env_map.get(prefix, "OPENAI_API_KEY")

    os.environ[env_key] = config.api_key
    logger.debug("已设置 %s 环境变量 (来自模型配置: %s)", env_key, config.model_id)

    # 如果有自定义 api_base，也设置到环境变量
    if config.api_base:
        os.environ["OPENAI_API_BASE"] = config.api_base


# ============================================================================
# 默认模型预设
# ============================================================================

_DEFAULT_PRESETS: dict[str, dict] = {
    "deepseek/deepseek-chat": {
        "display_name": "DeepSeek Chat",
        "provider": "deepseek",
        "temperature": 0.3,
        "top_p": 0.95,
        "max_tokens": 8192,
        "context_window": 65536,
        "description": "DeepSeek V3 对话模型，中文理解力强，性价比高",
    },
    "deepseek/deepseek-reasoner": {
        "display_name": "DeepSeek Reasoner (R1)",
        "provider": "deepseek",
        "temperature": 0.0,
        "top_p": 0.95,
        "max_tokens": 16384,
        "context_window": 65536,
        "description": "DeepSeek R1 推理模型，内置 CoT 思维链，适合复杂分析与根因定位",
    },
    "gpt-4o": {
        "display_name": "GPT-4o",
        "provider": "openai",
        "temperature": 0.3,
        "top_p": 1.0,
        "max_tokens": 8192,
        "context_window": 128000,
        "description": "OpenAI 旗舰多模态模型，128K 上下文",
    },
    "gpt-4o-mini": {
        "display_name": "GPT-4o Mini",
        "provider": "openai",
        "temperature": 0.3,
        "top_p": 1.0,
        "max_tokens": 4096,
        "context_window": 128000,
        "description": "OpenAI 轻量模型，速度快成本低",
    },
    "anthropic/claude-3.5-sonnet": {
        "display_name": "Claude 3.5 Sonnet",
        "provider": "anthropic",
        "temperature": 0.3,
        "top_p": 0.95,
        "max_tokens": 8192,
        "context_window": 200000,
        "description": "Anthropic 旗舰模型，200K 上下文，推理能力极强",
    },
    "gemini/gemini-2.0-flash": {
        "display_name": "Gemini 2.0 Flash",
        "provider": "gemini",
        "temperature": 0.3,
        "top_p": 0.95,
        "max_tokens": 8192,
        "context_window": 1048576,
        "description": "Google Gemini 高速模型，1M 上下文窗口",
    },
    "gemini/gemini-2.5-pro": {
        "display_name": "Gemini 2.5 Pro",
        "provider": "gemini",
        "temperature": 0.3,
        "top_p": 0.95,
        "max_tokens": 8192,
        "context_window": 1048576,
        "description": "Google Gemini 旗舰模型，1M 上下文窗口，推理能力顶级",
    },
}


def _build_default_config(model_id: str) -> LLMModelConfig:
    """根据模型 ID 构建默认配置"""
    preset = _DEFAULT_PRESETS.get(model_id, {})
    provider = preset.get("provider", "")
    if not provider and "/" in model_id:
        provider = model_id.split("/")[0]

    return LLMModelConfig(
        model_id=model_id,
        display_name=preset.get("display_name", model_id),
        provider=provider,
        api_key="",
        api_base="",
        temperature=preset.get("temperature", 0.3),
        top_p=preset.get("top_p", 1.0),
        max_tokens=preset.get("max_tokens", 8192),
        max_retries=3,
        context_window=preset.get("context_window", 128000),
        enabled=True,
        description=preset.get("description", ""),
    )


def init_default_configs(config_dir: Path | None = None):
    """
    初始化默认模型预设配置文件。

    仅在配置文件不存在时创建，不会覆盖用户已修改的配置。

    Args:
        config_dir: 配置文件目录
    """
    for model_id in _DEFAULT_PRESETS:
        existing = load_model_config(model_id, config_dir)
        if existing is None:
            config = _build_default_config(model_id)
            save_model_config(config, config_dir)
            logger.info("初始化默认配置: %s", model_id)
