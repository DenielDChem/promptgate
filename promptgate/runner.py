"""LiteLLM execution engine: compile → call LLM → validate → retry."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from promptgate.file_api import _DEFAULT_DB_PATH, get_or_compile
from promptgate.storage import SQLiteBackend
from promptgate.validator import validate_output


@dataclass
class RunResult:
    """Result of a prompt run.

    Attributes:
        ok: True if LLM output passed schema validation.
        data: Parsed and validated output dict (set when ok=True).
        raw_output: Last raw LLM response string.
        attempts: Number of LLM calls made.
        prompt_id: The prompt that was run.
        model_id: The model used.
    """

    ok: bool
    data: dict | None
    raw_output: str
    attempts: int
    prompt_id: str
    model_id: str


def run(
    prompt_id: str,
    payload: dict,
    model_id: str,
    *,
    db_path: str | Path = _DEFAULT_DB_PATH,
    max_retries: int = 3,
    user_message: str | None = None,
    litellm_kwargs: dict | None = None,
) -> RunResult:
    """Compile a prompt, call an LLM via LiteLLM, validate and retry on failure.

    Args:
        prompt_id: ID of the stored prompt to run.
        payload: Data to fill into the prompt template.
        model_id: LiteLLM model string (e.g. ``"gpt-4o"``, ``"claude-3-5-sonnet-20241022"``).
        db_path: Path to SQLite database.
        max_retries: Maximum LLM call attempts before giving up.
        user_message: Optional user turn appended after system prompt.
            Defaults to JSON-serialised payload.
        litellm_kwargs: Extra kwargs forwarded to ``litellm.completion()``.

    Returns:
        RunResult with ok=True and parsed data on success.

    Raises:
        KeyError: If prompt_id not found.
        ImportError: If litellm is not installed (``pip install pgate[litellm]``).

    Examples:
        >>> # Requires a live LLM — not suitable for doctest
        >>> isinstance(RunResult(ok=True, data={}, raw_output="", attempts=1, prompt_id="x", model_id="m"), RunResult)
        True
    """
    try:
        from litellm import completion
    except ImportError as exc:
        raise ImportError("Install litellm: pip install pgate[litellm]") from exc

    backend = SQLiteBackend(db_path)
    backend.init()
    prompt = backend.get(prompt_id)
    if prompt is None:
        raise KeyError(f"Prompt '{prompt_id}' not found")

    contract = get_or_compile(prompt_id, payload, db_path=db_path, model_id=model_id)
    schema = prompt.schema_

    user_msg = user_message or (json.dumps(payload, ensure_ascii=False) if payload else "Run the prompt.")
    messages: list[dict[str, str]] = [
        {"role": "system", "content": contract.system_prompt},
        {"role": "user", "content": user_msg},
    ]
    extra = litellm_kwargs or {}
    raw_output = ""

    for attempt in range(1, max_retries + 1):
        logger.debug("Run attempt {}/{}: model={} prompt={}", attempt, max_retries, model_id, prompt_id)
        response = completion(model=model_id, messages=messages, **extra)
        raw_output = response.choices[0].message.content or ""

        result = validate_output(raw_output, contract, schema)
        if result.ok:
            logger.info("Run ok after {} attempt(s): prompt={}", attempt, prompt_id)
            return RunResult(ok=True, data=result.data, raw_output=raw_output,
                             attempts=attempt, prompt_id=prompt_id, model_id=model_id)

        logger.warning("Attempt {} failed — retrying. hint={}", attempt, result.retry_instruction)
        messages.append({"role": "assistant", "content": raw_output})
        messages.append({"role": "user", "content": result.retry_instruction or "Fix the output format."})

    logger.error("Run failed after {} attempts: prompt={}", max_retries, prompt_id)
    return RunResult(ok=False, data=None, raw_output=raw_output,
                     attempts=max_retries, prompt_id=prompt_id, model_id=model_id)
