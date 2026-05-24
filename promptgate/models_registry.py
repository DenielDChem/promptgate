"""LLM model capability registry — resolve model IDs to structured capability profiles."""
from __future__ import annotations

import warnings
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel


_USER_MODELS_PATH: Path = Path.home() / ".promptgate" / "models.yaml"
# User-defined overrides — loaded at import, take precedence over _REGISTRY.
_USER_REGISTRY: dict[str, ModelCapabilities] = {}


ReasoningMode = Literal["none", "chain_of_thought", "native"]
"""Reasoning handling strategy for a model:

- ``none``: standard text model, no special reasoning handling.
- ``chain_of_thought``: requires explicit CoT instruction in the prompt to reason step-by-step.
- ``native``: built-in thinking (o1/o3, Claude extended thinking, DeepSeek-R1, QwQ).
"""

CoTStrategy = Literal["zero_shot", "structured", "react"]
"""Chain-of-thought injection strategy (only relevant when reasoning_mode == 'chain_of_thought'):

- ``zero_shot``: "Think step by step" prefix — works for most instruction-tuned models.
- ``structured``: numbered analysis steps — better for analytical/long-form tasks.
- ``react``: Thought/Action/Observation loop — best for tool-use and agentic tasks.
"""


class ModelCapabilities(BaseModel):
    """Capabilities and constraints for a registered LLM model.

    Args:
        family: Provider family (openai, anthropic, deepseek, google, mistral, meta, qwen).
        context_window: Maximum input tokens accepted by the model.
        max_output_tokens: Maximum tokens the model can generate per request.
        supports_system_prompt: Whether the model accepts a separate system message.
        json_native: Whether the model has a native JSON output mode (response_format).
        reasoning_mode: How thinking/reasoning is handled by this model.
        cot_strategy: Which CoT algorithm to auto-inject (chain_of_thought mode only).
        reasoning_budget_tokens: Suggested token budget for native reasoning models.

    Examples:
        >>> caps = ModelCapabilities(family="openai", context_window=128_000)
        >>> caps.supports_system_prompt
        True
        >>> caps.reasoning_mode
        'none'
        >>> caps.cot_strategy
        'zero_shot'
    """

    family: str
    context_window: int
    max_output_tokens: int = 4096
    supports_system_prompt: bool = True
    json_native: bool = False
    reasoning_mode: ReasoningMode = "none"
    cot_strategy: CoTStrategy = "zero_shot"
    reasoning_budget_tokens: int | None = None


# Registry keyed by canonical model name prefix (matched longest-first on model_id).
_REGISTRY: dict[str, ModelCapabilities] = {
    # ── OpenAI ──────────────────────────────────────────────────────────────
    "gpt-3.5-turbo": ModelCapabilities(family="openai", context_window=16_385, json_native=True),
    "gpt-4": ModelCapabilities(family="openai", context_window=8_192),
    "gpt-4-32k": ModelCapabilities(family="openai", context_window=32_768),
    "gpt-4-turbo": ModelCapabilities(family="openai", context_window=128_000),
    "gpt-4o-mini": ModelCapabilities(family="openai", context_window=128_000, json_native=True),
    "gpt-4o": ModelCapabilities(family="openai", context_window=128_000, json_native=True),
    "o1-mini": ModelCapabilities(
        family="openai", context_window=128_000,
        reasoning_mode="native", supports_system_prompt=False,
    ),
    "o1-preview": ModelCapabilities(
        family="openai", context_window=128_000,
        reasoning_mode="native", supports_system_prompt=False,
    ),
    "o1": ModelCapabilities(
        family="openai", context_window=200_000,
        reasoning_mode="native", supports_system_prompt=False,
    ),
    "o3-mini": ModelCapabilities(
        family="openai", context_window=200_000, reasoning_mode="native",
    ),
    "o3": ModelCapabilities(
        family="openai", context_window=200_000, reasoning_mode="native",
    ),
    # ── Anthropic ───────────────────────────────────────────────────────────
    "claude-2": ModelCapabilities(family="anthropic", context_window=200_000),
    "claude-3-haiku": ModelCapabilities(family="anthropic", context_window=200_000),
    "claude-3-sonnet": ModelCapabilities(family="anthropic", context_window=200_000),
    "claude-3-opus": ModelCapabilities(family="anthropic", context_window=200_000),
    "claude-3-5-haiku": ModelCapabilities(family="anthropic", context_window=200_000),
    "claude-3-5-sonnet": ModelCapabilities(family="anthropic", context_window=200_000),
    "claude-3-7-sonnet": ModelCapabilities(
        family="anthropic", context_window=200_000,
        reasoning_mode="native", reasoning_budget_tokens=10_000,
    ),
    "claude-haiku-4": ModelCapabilities(family="anthropic", context_window=200_000),
    "claude-sonnet-4": ModelCapabilities(
        family="anthropic", context_window=200_000,
        reasoning_mode="native", reasoning_budget_tokens=10_000,
    ),
    "claude-opus-4": ModelCapabilities(
        family="anthropic", context_window=200_000,
        reasoning_mode="native", reasoning_budget_tokens=32_000,
    ),
    # ── DeepSeek ────────────────────────────────────────────────────────────
    "deepseek-chat": ModelCapabilities(family="deepseek", context_window=64_000),
    "deepseek-coder": ModelCapabilities(family="deepseek", context_window=128_000),
    "deepseek-v3": ModelCapabilities(family="deepseek", context_window=128_000),
    "deepseek-r1": ModelCapabilities(
        family="deepseek", context_window=128_000, reasoning_mode="native",
    ),
    # ── Google ──────────────────────────────────────────────────────────────
    "gemini-1.5-flash": ModelCapabilities(family="google", context_window=1_000_000),
    "gemini-1.5-pro": ModelCapabilities(family="google", context_window=2_000_000),
    "gemini-2.0-flash": ModelCapabilities(
        family="google", context_window=1_000_000, reasoning_mode="native",
    ),
    "gemini-2.5-pro": ModelCapabilities(
        family="google", context_window=2_000_000, reasoning_mode="native",
    ),
    # ── Mistral ─────────────────────────────────────────────────────────────
    "mistral-small": ModelCapabilities(family="mistral", context_window=32_000),
    "mistral-medium": ModelCapabilities(family="mistral", context_window=32_000),
    "mistral-large": ModelCapabilities(family="mistral", context_window=128_000),
    "mistral-medium-3": ModelCapabilities(family="mistral", context_window=128_000),
    # ── Meta ────────────────────────────────────────────────────────────────
    "llama-3.1-8b": ModelCapabilities(
        family="meta", context_window=128_000,
        reasoning_mode="chain_of_thought", cot_strategy="structured",
    ),
    "llama-3.1-70b": ModelCapabilities(family="meta", context_window=128_000),
    "llama-3.3-70b": ModelCapabilities(family="meta", context_window=128_000),
    # ── Qwen / Alibaba ──────────────────────────────────────────────────────
    "qwen2.5-72b": ModelCapabilities(family="qwen", context_window=128_000),
    "qwq-32b": ModelCapabilities(
        family="qwen", context_window=32_000, reasoning_mode="native",
    ),
}


def _longest_prefix_match(
    registry: dict[str, ModelCapabilities], model_id: str
) -> ModelCapabilities | None:
    """Return capabilities via exact then longest-prefix match in registry."""
    if model_id in registry:
        return registry[model_id]
    candidates = [(k, v) for k, v in registry.items() if model_id.startswith(k)]
    if candidates:
        return max(candidates, key=lambda x: len(x[0]))[1]
    return None


def resolve_model(model_id: str) -> ModelCapabilities | None:
    """Resolve a model ID to its capabilities via exact then longest-prefix match.

    User-defined models (from ``~/.promptgate/models.yaml``) take precedence
    over built-in entries, allowing overrides of context windows or reasoning modes.

    Args:
        model_id: Full or versioned model identifier string.

    Returns:
        ModelCapabilities if a match is found, None if the model is unknown.

    Examples:
        >>> caps = resolve_model("gpt-4o")
        >>> caps.family
        'openai'
        >>> resolve_model("unknown-model-xyz") is None
        True
        >>> resolve_model("gpt-4o-mini-2024-07-18").context_window
        128000
    """
    result = _longest_prefix_match(_USER_REGISTRY, model_id)
    if result is not None:
        return result
    return _longest_prefix_match(_REGISTRY, model_id)


def list_models(include_custom: bool = True) -> list[str]:
    """Return all registered model IDs in sorted order.

    Args:
        include_custom: When True (default), includes user-defined models.

    Examples:
        >>> models = list_models()
        >>> isinstance(models, list)
        True
        >>> "gpt-4o" in models
        True
    """
    all_ids = set(_REGISTRY.keys())
    if include_custom:
        all_ids |= set(_USER_REGISTRY.keys())
    return sorted(all_ids)


def register_model(model_id: str, caps: ModelCapabilities) -> None:
    """Add or override a model in the user registry and persist to disk.

    Writes to ``~/.promptgate/models.yaml``. Changes take effect immediately
    in the current process and on the next startup for other processes.

    Args:
        model_id: Unique model identifier (used as registry key).
        caps: Capability profile for the model.

    Examples:
        >>> from promptgate.models_registry import ModelCapabilities
        >>> caps = ModelCapabilities(family="custom", context_window=8_000)
        >>> isinstance(caps, ModelCapabilities)
        True
    """
    _USER_REGISTRY[model_id] = caps
    _save_user_models()


def unregister_model(model_id: str) -> bool:
    """Remove a model from the user registry and persist.

    Cannot remove built-in models — only user-defined entries.

    Args:
        model_id: Model identifier to remove.

    Returns:
        True if the model was in the user registry and removed, False otherwise.

    Examples:
        >>> unregister_model("nonexistent-model-xyz")
        False
    """
    if model_id not in _USER_REGISTRY:
        return False
    del _USER_REGISTRY[model_id]
    _save_user_models()
    return True


def _save_user_models() -> None:
    """Persist _USER_REGISTRY to ~/.promptgate/models.yaml."""
    _USER_MODELS_PATH.parent.mkdir(parents=True, exist_ok=True)
    data: dict = {
        "models": {
            mid: caps.model_dump()
            for mid, caps in _USER_REGISTRY.items()
        }
    }
    _USER_MODELS_PATH.write_text(
        yaml.dump(data, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )


def _load_user_models() -> None:
    """Load user model overrides from ~/.promptgate/models.yaml into _USER_REGISTRY.

    Called once at module import. Silently skips missing or malformed entries
    so a bad user config never prevents the built-in registry from working.

    Examples:
        >>> _load_user_models()  # no-op when file absent
    """
    if not _USER_MODELS_PATH.exists():
        return
    try:
        data = yaml.safe_load(_USER_MODELS_PATH.read_text(encoding="utf-8")) or {}
        for mid, caps_data in (data.get("models") or {}).items():
            try:
                _USER_REGISTRY[mid] = ModelCapabilities(**caps_data)
            except Exception as exc:
                warnings.warn(
                    f"promptgate: skipping malformed model '{mid}' in {_USER_MODELS_PATH}: {exc}",
                    stacklevel=2,
                )
    except Exception as exc:
        warnings.warn(
            f"promptgate: could not load {_USER_MODELS_PATH}: {exc}",
            stacklevel=2,
        )


_load_user_models()
