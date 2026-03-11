"""
LLM 模型配置管理单元测试

覆盖：
- 配置数据模型序列化/反序列化
- 配置文件 CRUD 操作
- 默认预设初始化
- 配置与客户端集成
"""
import json
import os
import pytest
from pathlib import Path
from pipeline.llm_config import (
    LLMModelConfig,
    load_model_config,
    save_model_config,
    delete_model_config,
    list_model_configs,
    update_model_config,
    get_or_create_config,
    apply_config_to_env,
    init_default_configs,
    _model_id_to_filename,
)
from pipeline.llm_client import CPELLMClient


# ============================================================================
# 数据模型测试
# ============================================================================

class TestLLMModelConfig:
    """模型配置数据类测试"""

    def test_default_values(self):
        """默认值应合理"""
        config = LLMModelConfig(model_id="test-model")
        assert config.temperature == 0.3
        assert config.top_p == 1.0
        assert config.max_tokens == 8192
        assert config.enabled is True

    def test_to_dict(self):
        """序列化为字典"""
        config = LLMModelConfig(
            model_id="deepseek/deepseek-chat",
            display_name="DeepSeek Chat",
            temperature=0.5,
            top_p=0.9,
            api_key="sk-test123",
        )
        d = config.to_dict()
        assert d["model_id"] == "deepseek/deepseek-chat"
        assert d["temperature"] == 0.5
        assert d["top_p"] == 0.9
        assert d["api_key"] == "sk-test123"

    def test_to_safe_dict_hides_api_key(self):
        """安全序列化应隐藏 API Key"""
        config = LLMModelConfig(model_id="test", api_key="sk-abcdefgh12345678")
        d = config.to_safe_dict()
        assert d["api_key"] == "***5678"

    def test_to_safe_dict_empty_key(self):
        """空 API Key 时安全序列化不变"""
        config = LLMModelConfig(model_id="test", api_key="")
        d = config.to_safe_dict()
        assert d["api_key"] == ""

    def test_from_dict(self):
        """从字典反序列化"""
        d = {
            "model_id": "gpt-4o",
            "temperature": 0.7,
            "top_p": 0.85,
            "extra_field": "should_be_ignored",
        }
        config = LLMModelConfig.from_dict(d)
        assert config.model_id == "gpt-4o"
        assert config.temperature == 0.7
        assert config.top_p == 0.85


# ============================================================================
# 文件名转换测试
# ============================================================================

class TestModelIdToFilename:
    """模型 ID 转文件名"""

    def test_slash_replaced(self):
        assert _model_id_to_filename("deepseek/deepseek-chat") == "deepseek_deepseek-chat"

    def test_no_slash(self):
        assert _model_id_to_filename("gpt-4o") == "gpt-4o"

    def test_multiple_slashes(self):
        assert _model_id_to_filename("gemini/gemini-2.0-flash") == "gemini_gemini-2.0-flash"


# ============================================================================
# CRUD 操作测试
# ============================================================================

class TestConfigCRUD:
    """配置文件增删改查测试"""

    def test_save_and_load(self, tmp_path):
        """保存后读取应一致"""
        config = LLMModelConfig(
            model_id="test/model",
            display_name="Test Model",
            temperature=0.5,
            top_p=0.9,
            api_key="sk-test",
        )
        save_model_config(config, tmp_path)

        loaded = load_model_config("test/model", tmp_path)
        assert loaded is not None
        assert loaded.model_id == "test/model"
        assert loaded.temperature == 0.5
        assert loaded.top_p == 0.9
        assert loaded.api_key == "sk-test"

    def test_load_nonexistent_returns_none(self, tmp_path):
        """加载不存在的配置返回 None"""
        result = load_model_config("nonexistent", tmp_path)
        assert result is None

    def test_delete(self, tmp_path):
        """删除配置后应不存在"""
        config = LLMModelConfig(model_id="to-delete")
        save_model_config(config, tmp_path)
        assert load_model_config("to-delete", tmp_path) is not None

        assert delete_model_config("to-delete", tmp_path) is True
        assert load_model_config("to-delete", tmp_path) is None

    def test_delete_nonexistent_returns_false(self, tmp_path):
        """删除不存在的配置返回 False"""
        assert delete_model_config("nonexistent", tmp_path) is False

    def test_list_configs(self, tmp_path):
        """列出所有配置"""
        save_model_config(LLMModelConfig(model_id="model-a", enabled=True), tmp_path)
        save_model_config(LLMModelConfig(model_id="model-b", enabled=False), tmp_path)

        all_configs = list_model_configs(tmp_path)
        assert len(all_configs) == 2

        enabled = list_model_configs(tmp_path, enabled_only=True)
        assert len(enabled) == 1
        assert enabled[0].model_id == "model-a"

    def test_update_config(self, tmp_path):
        """部分更新配置"""
        config = LLMModelConfig(
            model_id="update-me",
            temperature=0.3,
            top_p=1.0,
        )
        save_model_config(config, tmp_path)

        updated = update_model_config("update-me", {
            "temperature": 0.7,
            "top_p": 0.85,
        }, tmp_path)

        assert updated is not None
        assert updated.temperature == 0.7
        assert updated.top_p == 0.85
        assert updated.model_id == "update-me"  # model_id 不变

    def test_update_nonexistent_returns_none(self, tmp_path):
        """更新不存在的配置返回 None"""
        result = update_model_config("nope", {"temperature": 0.5}, tmp_path)
        assert result is None

    def test_get_or_create(self, tmp_path):
        """get_or_create 首次创建，后续读取"""
        config1 = get_or_create_config("deepseek/deepseek-chat", tmp_path)
        assert config1.model_id == "deepseek/deepseek-chat"
        assert config1.display_name == "DeepSeek Chat"  # 来自预设
        assert config1.top_p == 0.95  # 预设值

        # 修改后再次获取应读到修改后的值
        update_model_config("deepseek/deepseek-chat", {"temperature": 0.9}, tmp_path)
        config2 = get_or_create_config("deepseek/deepseek-chat", tmp_path)
        assert config2.temperature == 0.9


# ============================================================================
# 环境变量设置测试
# ============================================================================

class TestApplyConfigToEnv:
    """API Key 环境变量设置"""

    def test_deepseek_key_set(self):
        """DeepSeek 配置应设置 DEEPSEEK_API_KEY"""
        config = LLMModelConfig(
            model_id="deepseek/deepseek-chat",
            provider="deepseek",
            api_key="sk-test-ds",
        )
        apply_config_to_env(config)
        assert os.environ.get("DEEPSEEK_API_KEY") == "sk-test-ds"

    def test_empty_key_skipped(self):
        """空 API Key 不设置环境变量"""
        old_val = os.environ.get("OPENAI_API_KEY", "")
        config = LLMModelConfig(model_id="test", api_key="")
        apply_config_to_env(config)
        # 环境变量应不变
        assert os.environ.get("OPENAI_API_KEY", "") == old_val


# ============================================================================
# 默认预设初始化测试
# ============================================================================

class TestInitDefaultConfigs:
    """默认预设初始化"""

    def test_creates_default_configs(self, tmp_path):
        """初始化应创建所有预设模型的配置文件"""
        init_default_configs(tmp_path)
        configs = list_model_configs(tmp_path)
        assert len(configs) >= 5  # 至少 5 个预设模型
        model_ids = [c.model_id for c in configs]
        assert "deepseek/deepseek-chat" in model_ids
        assert "gpt-4o" in model_ids

    def test_does_not_overwrite_existing(self, tmp_path):
        """初始化不覆盖已存在的配置"""
        custom = LLMModelConfig(
            model_id="deepseek/deepseek-chat",
            temperature=0.99,
            api_key="my-custom-key",
        )
        save_model_config(custom, tmp_path)

        init_default_configs(tmp_path)

        loaded = load_model_config("deepseek/deepseek-chat", tmp_path)
        assert loaded.temperature == 0.99  # 保持用户修改
        assert loaded.api_key == "my-custom-key"


# ============================================================================
# 客户端集成测试
# ============================================================================

class TestClientFromConfig:
    """CPELLMClient.from_config() 集成测试"""

    def test_from_config_loads_params(self, tmp_path):
        """from_config 应正确加载 temperature/top_p 等参数"""
        config = LLMModelConfig(
            model_id="test/model",
            temperature=0.8,
            top_p=0.92,
            max_tokens=4096,
        )
        save_model_config(config, tmp_path)

        client = CPELLMClient.from_config("test/model", config_dir=tmp_path)
        assert client.model == "test/model"
        assert client.temperature == 0.8
        assert client.top_p == 0.92
        assert client.max_tokens == 4096

    def test_from_config_auto_creates_default(self, tmp_path):
        """from_config 对未知模型应自动创建默认配置"""
        client = CPELLMClient.from_config("deepseek/deepseek-chat", config_dir=tmp_path)
        assert client.model == "deepseek/deepseek-chat"
        assert client.top_p == 0.95  # DeepSeek 预设值

        # 确认配置文件已被创建
        loaded = load_model_config("deepseek/deepseek-chat", tmp_path)
        assert loaded is not None
