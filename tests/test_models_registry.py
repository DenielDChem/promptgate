"""Tests for promptgate.models_registry — model resolution and capability profiles."""
from __future__ import annotations

import pytest
import yaml

from promptgate.models_registry import ModelCapabilities, list_models, resolve_model


class TestResolveModelExact:
    """resolve_model with exact registry key matches."""

    def test_known_model_returns_capabilities(self):
        """resolve_model returns capabilities for a registered model ID."""
        caps = resolve_model("gpt-4o")
        assert caps is not None
        assert caps.family == "openai"

    def test_known_model_context_window(self):
        """Registered model context_window matches expected value."""
        caps = resolve_model("gpt-4o")
        assert caps.context_window == 128_000

    def test_unknown_model_returns_none(self):
        """resolve_model returns None for completely unknown model IDs."""
        assert resolve_model("unknown-model-xyz-1234") is None

    def test_empty_string_returns_none(self):
        """Empty string resolves to None."""
        assert resolve_model("") is None


class TestResolveModelPrefix:
    """resolve_model prefix matching for versioned model IDs."""

    def test_versioned_openai_resolves(self):
        """Versioned gpt-4o-mini ID resolves via prefix match."""
        caps = resolve_model("gpt-4o-mini-2024-07-18")
        assert caps is not None
        assert caps.context_window == 128_000

    def test_longest_prefix_wins(self):
        """Prefix matching selects the longest matching registry key."""
        # gpt-4o-mini prefix (len=10) must beat gpt-4o (len=6)
        caps_mini = resolve_model("gpt-4o-mini-2024-07-18")
        caps_full = resolve_model("gpt-4o-2024-08-06")
        assert caps_mini.json_native is True  # gpt-4o-mini has json_native
        assert caps_full.context_window == 128_000  # gpt-4o also matches

    def test_versioned_claude_resolves(self):
        """Versioned claude-3-5-sonnet resolves via prefix."""
        caps = resolve_model("claude-3-5-sonnet-20241022")
        assert caps is not None
        assert caps.family == "anthropic"

    def test_versioned_deepseek_resolves(self):
        """Versioned deepseek-r1 ID resolves correctly."""
        caps = resolve_model("deepseek-r1-distill-qwen-7b")
        assert caps is not None
        assert caps.reasoning_mode == "native"


class TestReasoningModes:
    """Reasoning mode correctness across model families."""

    def test_native_reasoning_openai_o1(self):
        """o1 has native reasoning mode."""
        caps = resolve_model("o1")
        assert caps.reasoning_mode == "native"

    def test_native_reasoning_deepseek_r1(self):
        """deepseek-r1 has native reasoning mode."""
        caps = resolve_model("deepseek-r1")
        assert caps.reasoning_mode == "native"

    def test_native_reasoning_qwq(self):
        """QwQ-32B has native reasoning mode."""
        caps = resolve_model("qwq-32b")
        assert caps.reasoning_mode == "native"

    def test_chain_of_thought_llama_small(self):
        """Small LLaMA model has chain_of_thought mode."""
        caps = resolve_model("llama-3.1-8b")
        assert caps.reasoning_mode == "chain_of_thought"

    def test_no_reasoning_gpt4o(self):
        """GPT-4o has none reasoning mode."""
        caps = resolve_model("gpt-4o")
        assert caps.reasoning_mode == "none"

    def test_no_system_prompt_for_o1(self):
        """o1 family does not support system prompts."""
        for model in ["o1", "o1-mini", "o1-preview"]:
            assert resolve_model(model).supports_system_prompt is False

    def test_claude_sonnet4_has_reasoning_budget(self):
        """Claude Sonnet 4 has a reasoning_budget_tokens set."""
        caps = resolve_model("claude-sonnet-4")
        assert caps.reasoning_budget_tokens is not None
        assert caps.reasoning_budget_tokens > 0


class TestCoTStrategies:
    """CoT strategy assignment for chain_of_thought models."""

    def test_llama_small_uses_structured_strategy(self):
        """llama-3.1-8b uses structured CoT strategy."""
        caps = resolve_model("llama-3.1-8b")
        assert caps.cot_strategy == "structured"

    def test_default_cot_strategy_is_zero_shot(self):
        """Models without explicit cot_strategy default to zero_shot."""
        caps = ModelCapabilities(family="test", context_window=8_000)
        assert caps.cot_strategy == "zero_shot"

    @pytest.mark.parametrize("strategy", ["zero_shot", "structured", "react"])
    def test_valid_cot_strategies_accepted(self, strategy):
        """All three CoT strategies are accepted by ModelCapabilities."""
        caps = ModelCapabilities(family="test", context_window=8_000, cot_strategy=strategy)
        assert caps.cot_strategy == strategy


class TestModelCapabilitiesDefaults:
    """ModelCapabilities field defaults are sensible."""

    def test_default_supports_system_prompt(self):
        """supports_system_prompt defaults to True."""
        caps = ModelCapabilities(family="test", context_window=8_000)
        assert caps.supports_system_prompt is True

    def test_default_json_native_false(self):
        """json_native defaults to False."""
        caps = ModelCapabilities(family="test", context_window=8_000)
        assert caps.json_native is False

    def test_default_reasoning_mode_none(self):
        """reasoning_mode defaults to none."""
        caps = ModelCapabilities(family="test", context_window=8_000)
        assert caps.reasoning_mode == "none"

    def test_default_reasoning_budget_is_none(self):
        """reasoning_budget_tokens defaults to None."""
        caps = ModelCapabilities(family="test", context_window=8_000)
        assert caps.reasoning_budget_tokens is None

    def test_default_max_output_tokens(self):
        """max_output_tokens defaults to 4096."""
        caps = ModelCapabilities(family="test", context_window=8_000)
        assert caps.max_output_tokens == 4096


class TestListModels:
    """list_models correctness."""

    def test_returns_list_of_strings(self):
        """list_models returns a list."""
        models = list_models()
        assert isinstance(models, list)
        assert len(models) > 0

    def test_contains_common_models(self):
        """Common models are present in the registry."""
        models = list_models()
        for expected in ["gpt-4o", "claude-3-5-sonnet", "deepseek-r1", "gemini-1.5-pro"]:
            assert expected in models

    def test_sorted_order(self):
        """list_models returns models in sorted alphabetical order."""
        models = list_models()
        assert models == sorted(models)


class TestUserRegistry:
    """register_model / unregister_model / _load_user_models round-trips."""

    def _fresh_registry(self):
        """Return a clean module-level _USER_REGISTRY dict (clear between tests)."""
        import promptgate.models_registry as mr
        mr._USER_REGISTRY.clear()
        return mr._USER_REGISTRY

    def test_register_model_adds_to_user_registry(self):
        """register_model stores caps in _USER_REGISTRY without persisting to disk."""
        import promptgate.models_registry as mr
        self._fresh_registry()
        caps = ModelCapabilities(family="custom", context_window=8_000)
        mr._USER_REGISTRY["test-model-xyz"] = caps
        assert "test-model-xyz" in mr._USER_REGISTRY
        mr._USER_REGISTRY.pop("test-model-xyz", None)

    def test_unregister_model_removes_known_entry(self, tmp_path, monkeypatch):
        """unregister_model returns True and removes the entry from _USER_REGISTRY."""
        import promptgate.models_registry as mr
        self._fresh_registry()
        monkeypatch.setattr(mr, "_USER_MODELS_PATH", tmp_path / "models.yaml")
        caps = ModelCapabilities(family="custom", context_window=4_000)
        mr.register_model("temp-model-a", caps)
        result = mr.unregister_model("temp-model-a")
        assert result is True
        assert "temp-model-a" not in mr._USER_REGISTRY

    def test_unregister_model_returns_false_for_unknown(self, tmp_path, monkeypatch):
        """unregister_model returns False when model_id not in user registry."""
        import promptgate.models_registry as mr
        self._fresh_registry()
        monkeypatch.setattr(mr, "_USER_MODELS_PATH", tmp_path / "models.yaml")
        result = mr.unregister_model("nonexistent-xyz-never-exists")
        assert result is False

    def test_register_persists_to_yaml(self, tmp_path, monkeypatch):
        """register_model writes models.yaml that can be re-read."""
        import promptgate.models_registry as mr
        self._fresh_registry()
        yaml_path = tmp_path / "models.yaml"
        monkeypatch.setattr(mr, "_USER_MODELS_PATH", yaml_path)
        caps = ModelCapabilities(family="openai", context_window=64_000, json_native=True)
        mr.register_model("my-custom-gpt", caps)
        assert yaml_path.exists()
        data = yaml.safe_load(yaml_path.read_text())
        assert "my-custom-gpt" in data["models"]
        assert data["models"]["my-custom-gpt"]["family"] == "openai"
        mr._USER_REGISTRY.pop("my-custom-gpt", None)

    def test_load_user_models_populates_registry(self, tmp_path, monkeypatch):
        """_load_user_models reads YAML and populates _USER_REGISTRY."""
        import promptgate.models_registry as mr
        self._fresh_registry()
        yaml_path = tmp_path / "models.yaml"
        yaml_path.write_text(
            yaml.dump({"models": {"loaded-model": {"family": "meta", "context_window": 32_000}}}),
            encoding="utf-8",
        )
        monkeypatch.setattr(mr, "_USER_MODELS_PATH", yaml_path)
        mr._load_user_models()
        assert "loaded-model" in mr._USER_REGISTRY
        assert mr._USER_REGISTRY["loaded-model"].family == "meta"
        mr._USER_REGISTRY.pop("loaded-model", None)

    def test_load_user_models_skips_malformed_entry(self, tmp_path, monkeypatch):
        """_load_user_models skips bad entries with warnings.warn, keeps good ones."""
        import promptgate.models_registry as mr
        self._fresh_registry()
        yaml_path = tmp_path / "models.yaml"
        yaml_path.write_text(
            yaml.dump({"models": {
                "good-model": {"family": "google", "context_window": 1_000_000},
                "bad-model": {"context_window": "not-a-number"},
            }}),
            encoding="utf-8",
        )
        monkeypatch.setattr(mr, "_USER_MODELS_PATH", yaml_path)
        import warnings
        with warnings.catch_warnings(record=True):
            mr._load_user_models()
        assert "good-model" in mr._USER_REGISTRY
        assert "bad-model" not in mr._USER_REGISTRY
        mr._USER_REGISTRY.pop("good-model", None)

    def test_load_user_models_no_op_when_file_absent(self, tmp_path, monkeypatch):
        """_load_user_models silently does nothing when models.yaml does not exist."""
        import promptgate.models_registry as mr
        self._fresh_registry()
        monkeypatch.setattr(mr, "_USER_MODELS_PATH", tmp_path / "nonexistent.yaml")
        mr._load_user_models()  # must not raise
        assert mr._USER_REGISTRY == {}

    def test_user_registry_overrides_builtin(self, tmp_path, monkeypatch):
        """User-defined model takes priority over built-in registry in resolve_model."""
        import promptgate.models_registry as mr
        self._fresh_registry()
        monkeypatch.setattr(mr, "_USER_MODELS_PATH", tmp_path / "models.yaml")
        custom = ModelCapabilities(family="openai", context_window=999_999)
        mr.register_model("gpt-4o", custom)
        caps = mr.resolve_model("gpt-4o")
        assert caps.context_window == 999_999
        mr._USER_REGISTRY.pop("gpt-4o", None)
