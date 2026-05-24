"""Pydantic TypeAdapter + Jinja2 -> CompiledContract."""
from __future__ import annotations

import hashlib
import json
import time

import jinja2.nodes
from jinja2 import ChainableUndefined, Environment, StrictUndefined, UndefinedError
from pydantic import TypeAdapter, ValidationError

from promptgate.models import CompiledContract, ModelHints, PromptConfig


_jinja_env = Environment(undefined=StrictUndefined, autoescape=False)
_jinja_env_lenient = Environment(undefined=ChainableUndefined, autoescape=False)
_jinja_env_parse = Environment(autoescape=False)  # AST analysis only — no rendering

# Chain-of-thought injection templates by strategy.
# Applied automatically when model.reasoning_mode == "chain_of_thought" and
# the template does not already reference the `reasoning_mode` variable.
_COT_TEMPLATES: dict[str, str] = {
    # Kojima et al. 2022 — reliable for most instruction-tuned models
    "zero_shot": "Think step by step before giving your final answer.\n\n",
    # Numbered analysis — better for analytical / long-form tasks
    "structured": (
        "Work through this task step by step:\n"
        "1. Understand exactly what is being asked\n"
        "2. Identify all relevant information\n"
        "3. Reason through the solution carefully\n"
        "4. Formulate and verify your final answer\n\n"
    ),
    # Yao et al. ReAct — best for tool-use and agentic tasks
    "react": (
        "Use the following format for each reasoning step:\n"
        "Thought: [your reasoning about the current step]\n"
        "Action: [what you determine or decide]\n"
        "Observation: [what you learn from that action]\n"
        "... (repeat Thought/Action/Observation as needed)\n"
        "Final Answer: [your conclusion]\n\n"
    ),
}


def _schema_hash(schema: dict) -> str:
    raw = json.dumps(schema, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()[:8]


def _find_missing(schema: dict, payload: dict) -> list[str]:
    required = schema.get("required", [])
    return [f for f in required if f not in payload]


def _template_references_var(template_str: str, var_name: str) -> bool:
    """Return True if the Jinja2 template AST contains a reference to var_name.

    Parses without rendering — checks Name nodes in the AST so both
    ``{{ var_name }}`` and ``{% if var_name %}`` are detected correctly.

    Args:
        template_str: Raw Jinja2 template string.
        var_name: Variable name to search for.

    Returns:
        True if the variable is referenced anywhere in the template.

    Examples:
        >>> _template_references_var("Hello {{ reasoning_mode }}", "reasoning_mode")
        True
        >>> _template_references_var("Hello world", "reasoning_mode")
        False
    """
    ast = _jinja_env_parse.parse(template_str)
    return any(node.name == var_name for node in ast.find_all(jinja2.nodes.Name))


def compile_prompt(prompt: PromptConfig, payload: dict, model_id: str | None = None) -> CompiledContract:
    """Validate payload against schema and render the Jinja2 template.

    When ``model_id`` is provided, model capability vars are injected into the
    Jinja2 context (``reasoning_mode``, ``model_family``, ``context_window``,
    ``json_native``, ``model_id``).  If the model requires chain-of-thought
    reasoning and the template does not reference ``reasoning_mode``, the
    appropriate CoT algorithm prefix is prepended automatically.

    Args:
        prompt: The prompt configuration containing schema and template.
        payload: Key-value data to fill into the template.
        model_id: Optional LLM model identifier. Enables model-aware compilation
            and CoT auto-injection for ``chain_of_thought`` models.

    Returns:
        CompiledContract with rendered system_prompt, schema_hash,
        model_hints (if model_id provided), and any missing required fields.

    Raises:
        ValueError: If the Jinja2 template references an undefined variable
            that is not in the payload and not in missing_fields.

    Examples:
        >>> from promptgate.models import PromptConfig
        >>> p = PromptConfig(
        ...     id="t", name="T",
        ...     **{"schema": {"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"]}},
        ...     template="Hello {{ x }}",
        ... )
        >>> contract = compile_prompt(p, {"x": "world"})
        >>> contract.system_prompt
        'Hello world'
        >>> contract = compile_prompt(p, {"x": "world"}, model_id="gpt-4o")
        >>> contract.model_hints.family
        'openai'
    """
    from promptgate.models_registry import resolve_model

    schema = prompt.schema_
    sh = _schema_hash(schema)
    missing = _find_missing(schema, payload)

    # Resolve model capabilities (None if model_id unknown or not given)
    caps = resolve_model(model_id) if model_id else None

    # Coerce payload fields declared in schema using Pydantic TypeAdapter
    coerced: dict = {}
    props = schema.get("properties", {})
    for key, value in payload.items():
        if key in props:
            try:
                ta = TypeAdapter(type(value))
                coerced[key] = ta.validate_python(value)
            except (ValidationError, Exception):
                coerced[key] = value
        else:
            coerced[key] = value

    ctx = {
        **coerced,
        "payload_json": json.dumps(coerced, ensure_ascii=False, indent=2),
        "output_schema": json.dumps(schema, ensure_ascii=False),
        "missing_fields": missing,
        # Model context vars — safe defaults when no model specified
        "model_id": model_id or "",
        "model_family": caps.family if caps else "",
        "reasoning_mode": caps.reasoning_mode if caps else "none",
        "context_window": caps.context_window if caps else 0,
        "json_native": caps.json_native if caps else False,
    }

    try:
        if missing:
            # Missing required fields — use lenient rendering so contract is still created
            tmpl = _jinja_env_lenient.from_string(prompt.template)
            rendered = tmpl.render(**ctx)
        else:
            tmpl = _jinja_env.from_string(prompt.template)
            rendered = tmpl.render(**ctx)
    except UndefinedError as exc:
        raise ValueError(f"Template variable error: {exc}") from exc

    # Auto-inject CoT prefix when:
    # 1. Model needs chain_of_thought reasoning
    # 2. Template does not already reference reasoning_mode (user controls manually)
    if (
        caps is not None
        and caps.reasoning_mode == "chain_of_thought"
        and not _template_references_var(prompt.template, "reasoning_mode")
    ):
        cot_prefix = _COT_TEMPLATES.get(caps.cot_strategy, _COT_TEMPLATES["zero_shot"])
        rendered = cot_prefix + rendered

    model_hints: ModelHints | None = None
    if caps is not None:
        model_hints = ModelHints(
            model_id=model_id,  # type: ignore[arg-type]
            family=caps.family,
            reasoning_mode=caps.reasoning_mode,
            cot_strategy=caps.cot_strategy,
            context_window=caps.context_window,
            max_output_tokens=caps.max_output_tokens,
            json_native=caps.json_native,
            supports_system_prompt=caps.supports_system_prompt,
            reasoning_budget_tokens=caps.reasoning_budget_tokens,
        )

    return CompiledContract(
        prompt_id=prompt.id,
        schema_hash=sh,
        compiled_at=int(time.time()),
        system_prompt=rendered,
        payload=coerced,
        missing_fields=missing,
        model_id=model_id,
        model_hints=model_hints,
    )
