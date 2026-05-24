from __future__ import annotations

from pydantic import BaseModel, Field


class PromptConfig(BaseModel):
    id: str
    name: str
    tags: list[str] = Field(default_factory=list)
    schema_: dict = Field(alias="schema")
    template: str
    description: str = ""

    model_config = {"populate_by_name": True}


class ModelHints(BaseModel):
    """Model-specific hints embedded in a CompiledContract.

    Derived from ModelCapabilities at compile time. Lets downstream code
    inspect what the target model supports without importing models_registry.

    Args:
        model_id: Canonical model identifier used during compilation.
        family: Provider family (openai, anthropic, deepseek, google, mistral, meta, qwen).
        reasoning_mode: How reasoning is handled — none, chain_of_thought, or native.
        context_window: Maximum input tokens for this model.
        max_output_tokens: Maximum tokens the model can generate.
        json_native: Whether the model supports native JSON output mode.
        supports_system_prompt: Whether a separate system message is accepted.
        cot_strategy: CoT algorithm applied — zero_shot, structured, or react.
        reasoning_budget_tokens: Suggested budget for native reasoning models.

    Examples:
        >>> hints = ModelHints(
        ...     model_id="gpt-4o",
        ...     family="openai",
        ...     reasoning_mode="none",
        ...     cot_strategy="zero_shot",
        ...     context_window=128_000,
        ...     max_output_tokens=4096,
        ...     json_native=True,
        ...     supports_system_prompt=True,
        ... )
        >>> hints.json_native
        True
    """

    model_id: str
    family: str
    reasoning_mode: str
    cot_strategy: str
    context_window: int
    max_output_tokens: int
    json_native: bool
    supports_system_prompt: bool
    reasoning_budget_tokens: int | None = None


class CompiledContract(BaseModel):
    prompt_id: str
    schema_hash: str
    compiled_at: int
    system_prompt: str
    payload: dict
    missing_fields: list[str] = Field(default_factory=list)
    retry_template: str = "Field '{field}' error: {error}. Fix according to schema."
    model_id: str | None = None
    model_hints: ModelHints | None = None


class ValidationResult(BaseModel):
    ok: bool
    data: dict | None = None
    retry_instruction: str | None = None
