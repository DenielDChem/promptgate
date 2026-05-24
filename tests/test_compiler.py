"""Tests for compiler.py."""
from __future__ import annotations

import pytest

from promptgate.compiler import compile_prompt, _schema_hash
from promptgate.models import CompiledContract, PromptConfig


@pytest.fixture
def simple_prompt():
    return PromptConfig(
        id="test_prompt",
        name="Test",
        **{"schema": {
            "type": "object",
            "properties": {"period": {"type": "string"}, "name": {"type": "string"}},
            "required": ["period"],
        }},
        template="Report for {{ period }}. Name: {{ name | default('unknown') }}.",
    )


def test_compile_renders_template(simple_prompt):
    contract = compile_prompt(simple_prompt, {"period": "2024-01", "name": "Alice"})
    assert contract.system_prompt == "Report for 2024-01. Name: Alice."


def test_compile_returns_compiled_contract(simple_prompt):
    contract = compile_prompt(simple_prompt, {"period": "2024-01"})
    assert isinstance(contract, CompiledContract)
    assert contract.prompt_id == "test_prompt"


def test_compile_schema_hash_is_deterministic(simple_prompt):
    c1 = compile_prompt(simple_prompt, {"period": "2024-01"})
    c2 = compile_prompt(simple_prompt, {"period": "2024-02"})
    assert c1.schema_hash == c2.schema_hash


def test_schema_hash_ignores_key_order():
    h1 = _schema_hash({"a": 1, "b": 2})
    h2 = _schema_hash({"b": 2, "a": 1})
    assert h1 == h2


def test_compile_detects_missing_required(simple_prompt):
    contract = compile_prompt(simple_prompt, {})
    assert "period" in contract.missing_fields


def test_compile_no_missing_when_all_provided(simple_prompt):
    contract = compile_prompt(simple_prompt, {"period": "2024-01"})
    assert contract.missing_fields == []


def test_compile_payload_json_in_context():
    p = PromptConfig(
        id="p", name="P",
        **{"schema": {}},
        template="{{ payload_json }}",
    )
    contract = compile_prompt(p, {"x": 1})
    assert '"x"' in contract.system_prompt


def test_compile_output_schema_in_context():
    schema = {"type": "object"}
    p = PromptConfig(id="p", name="P", **{"schema": schema}, template="{{ output_schema }}")
    contract = compile_prompt(p, {})
    assert "object" in contract.system_prompt


def test_compile_undefined_variable_raises():
    p = PromptConfig(
        id="p", name="P",
        **{"schema": {}},
        template="{{ nonexistent_var }}",
    )
    with pytest.raises(ValueError, match="Template variable error"):
        compile_prompt(p, {})


def test_compile_compiled_at_is_timestamp(simple_prompt):
    import time
    before = int(time.time())
    contract = compile_prompt(simple_prompt, {"period": "2024-01"})
    after = int(time.time())
    assert before <= contract.compiled_at <= after


def test_compile_stores_coerced_payload(simple_prompt):
    contract = compile_prompt(simple_prompt, {"period": "2024-01", "extra": "x"})
    assert "period" in contract.payload


# ── Model-aware compilation ────────────────────────────────────────────────


def test_compile_with_known_model_sets_model_id(simple_prompt):
    """model_id is stored on the contract when provided."""
    contract = compile_prompt(simple_prompt, {"period": "2024-01"}, model_id="gpt-4o")
    assert contract.model_id == "gpt-4o"


def test_compile_with_known_model_sets_model_hints(simple_prompt):
    """model_hints is populated with resolved capabilities."""
    contract = compile_prompt(simple_prompt, {"period": "2024-01"}, model_id="gpt-4o")
    assert contract.model_hints is not None
    assert contract.model_hints.family == "openai"
    assert contract.model_hints.context_window == 128_000


def test_compile_without_model_id_has_no_hints(simple_prompt):
    """model_hints is None when no model_id provided."""
    contract = compile_prompt(simple_prompt, {"period": "2024-01"})
    assert contract.model_id is None
    assert contract.model_hints is None


def test_compile_unknown_model_id_still_compiles(simple_prompt):
    """Unknown model_id does not crash — model_hints is None."""
    contract = compile_prompt(simple_prompt, {"period": "2024-01"}, model_id="my-custom-model")
    assert contract.model_id == "my-custom-model"
    assert contract.model_hints is None


def test_compile_model_vars_injected_into_template():
    """Model context vars (reasoning_mode, model_family, json_native) available in template."""
    p = PromptConfig(
        id="p", name="P",
        **{"schema": {}},
        template="{{ model_family }}/{{ reasoning_mode }}/{{ json_native }}",
    )
    contract = compile_prompt(p, {}, model_id="gpt-4o")
    assert contract.system_prompt == "openai/none/True"


def test_compile_model_vars_default_when_no_model():
    """Model context vars default to empty/zero when model_id is None."""
    p = PromptConfig(
        id="p", name="P",
        **{"schema": {}},
        template="{{ model_family }}/{{ reasoning_mode }}/{{ context_window }}",
    )
    contract = compile_prompt(p, {})
    assert contract.system_prompt == "/none/0"


def test_compile_cot_auto_injects_for_chain_of_thought_model(simple_prompt):
    """CoT prefix auto-injected when model is chain_of_thought and template is plain."""
    contract = compile_prompt(simple_prompt, {"period": "2024-01"}, model_id="llama-3.1-8b")
    # structured CoT strategy for llama-3.1-8b
    assert "Work through this task step by step" in contract.system_prompt
    assert contract.system_prompt.startswith("Work through")


def test_compile_cot_no_inject_when_template_uses_reasoning_mode():
    """CoT prefix NOT auto-injected when template already references reasoning_mode."""
    p = PromptConfig(
        id="p", name="P",
        **{"schema": {}},
        template="{% if reasoning_mode == 'chain_of_thought' %}Custom CoT{% endif %} Task.",
    )
    contract = compile_prompt(p, {}, model_id="llama-3.1-8b")
    assert "Work through" not in contract.system_prompt
    assert "Custom CoT" in contract.system_prompt


def test_compile_native_model_no_cot_inject(simple_prompt):
    """Native reasoning models do NOT get CoT prefix auto-injected."""
    contract = compile_prompt(simple_prompt, {"period": "2024-01"}, model_id="o1")
    assert "Think step by step" not in contract.system_prompt
    assert "Work through" not in contract.system_prompt


def test_compile_cot_hints_stored_on_contract():
    """model_hints contains cot_strategy for chain_of_thought model."""
    p = PromptConfig(id="p", name="P", **{"schema": {}}, template="Task.")
    contract = compile_prompt(p, {}, model_id="llama-3.1-8b")
    assert contract.model_hints is not None
    assert contract.model_hints.reasoning_mode == "chain_of_thought"
    assert contract.model_hints.cot_strategy == "structured"
