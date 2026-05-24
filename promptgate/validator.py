"""LLM output validation + retry_instruction generation."""
from __future__ import annotations

import json
import urllib.parse

import jsonschema
from jsonschema import FormatChecker, ValidationError
from jsonschema.exceptions import FormatError

_FORMAT_CHECKER = FormatChecker()


@_FORMAT_CHECKER.checks("url", raises=ValueError)
def _check_url(value: str) -> bool:
    parsed = urllib.parse.urlparse(value)
    if not (parsed.scheme and parsed.netloc):
        raise ValueError(f"{value!r} is not a valid URL")
    return True


from promptgate.models import CompiledContract, ValidationResult


def extract_json(text: str) -> dict | None:
    """Extract the rightmost JSON object from LLM output text.

    Uses bracket matching to correctly handle nested objects. Takes the
    rightmost top-level ``{...}`` block — LLM prose typically precedes JSON.

    Args:
        text: Raw LLM output string.

    Returns:
        Parsed dict if a valid JSON object is found, None otherwise.

    Examples:
        >>> extract_json('Sure! Here you go: {"key": "value"}')
        {'key': 'value'}
        >>> extract_json('Text {"a": {"b": 1}}')
        {'a': {'b': 1}}
        >>> extract_json("No JSON here") is None
        True
    """
    candidates: list[str] = []
    i = 0
    while i < len(text):
        if text[i] != "{":
            i += 1
            continue
        depth = 0
        for j in range(i, len(text)):
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
                if depth == 0:
                    candidates.append(text[i : j + 1])
                    i = j + 1  # skip past this top-level block, ignore nested
                    break
        else:
            i += 1
    for candidate in reversed(candidates):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


def validate_output(llm_output: str, contract: CompiledContract, schema: dict) -> ValidationResult:
    """Validate LLM output against the contract's JSON schema.

    Extracts JSON from raw LLM text, then validates against the schema.
    On failure, generates a natural-language retry_instruction using the
    contract's retry_template.

    Args:
        llm_output: Raw string returned by the LLM.
        contract: The compiled contract that produced this request.
        schema: JSON schema dict to validate against.

    Returns:
        ValidationResult with ok=True and parsed data on success,
        or ok=False and retry_instruction on failure.

    Examples:
        >>> from promptgate.models import CompiledContract
        >>> contract = CompiledContract(
        ...     prompt_id="t", schema_hash="abc", compiled_at=0,
        ...     system_prompt="", payload={},
        ... )
        >>> schema = {"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"]}
        >>> result = validate_output('{"x": "hello"}', contract, schema)
        >>> result.ok
        True
    """
    data = extract_json(llm_output)
    if data is None:
        return ValidationResult(
            ok=False,
            retry_instruction=(
                contract.retry_template.format(
                    field="<response>",
                    error="No valid JSON object found in output",
                )
            ),
        )

    try:
        jsonschema.validate(instance=data, schema=schema, format_checker=_FORMAT_CHECKER)
        return ValidationResult(ok=True, data=data)
    except FormatError as exc:
        retry = contract.retry_template.format(field="<format>", error=str(exc))
        return ValidationResult(ok=False, retry_instruction=retry)
    except ValidationError as exc:
        field = ".".join(str(p) for p in exc.absolute_path) or exc.validator_value
        retry = contract.retry_template.format(field=field, error=exc.message)
        return ValidationResult(ok=False, retry_instruction=retry)
