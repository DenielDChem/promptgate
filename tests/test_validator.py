"""Tests for validator.py."""
from __future__ import annotations

import pytest

from promptgate.models import CompiledContract
from promptgate.validator import extract_json, validate_output


@pytest.fixture
def contract():
    return CompiledContract(
        prompt_id="t",
        schema_hash="abc12345",
        compiled_at=0,
        system_prompt="",
        payload={},
    )


@pytest.fixture
def schema():
    return {
        "type": "object",
        "properties": {
            "result": {"type": "string"},
            "score": {"type": "number"},
        },
        "required": ["result"],
    }


# --- extract_json ---

def test_extract_json_simple():
    assert extract_json('{"key": "value"}') == {"key": "value"}


def test_extract_json_with_prose():
    assert extract_json('Sure! Here: {"answer": 42}') == {"answer": 42}


def test_extract_json_takes_rightmost():
    text = '{"first": 1} some text {"second": 2}'
    assert extract_json(text) == {"second": 2}


def test_extract_json_no_json_returns_none():
    assert extract_json("no json here at all") is None


def test_extract_json_empty_string():
    assert extract_json("") is None


def test_extract_json_nested():
    assert extract_json('{"a": {"b": 1}}') == {"a": {"b": 1}}


# --- validate_output ---

def test_validate_ok(contract, schema):
    result = validate_output('{"result": "hello", "score": 0.9}', contract, schema)
    assert result.ok is True
    assert result.data == {"result": "hello", "score": 0.9}
    assert result.retry_instruction is None


def test_validate_no_json(contract, schema):
    result = validate_output("I cannot produce JSON", contract, schema)
    assert result.ok is False
    assert result.retry_instruction is not None
    assert "No valid JSON" in result.retry_instruction


def test_validate_missing_required(contract, schema):
    result = validate_output('{"score": 0.5}', contract, schema)
    assert result.ok is False
    assert result.retry_instruction is not None
    assert "result" in result.retry_instruction


def test_validate_wrong_type(contract, schema):
    result = validate_output('{"result": 123}', contract, schema)
    assert result.ok is False
    assert result.retry_instruction is not None


def test_validate_extra_fields_allowed(contract, schema):
    result = validate_output('{"result": "ok", "extra": "fine"}', contract, schema)
    assert result.ok is True


def test_validate_uses_retry_template(contract, schema):
    custom = CompiledContract(
        prompt_id="t",
        schema_hash="x",
        compiled_at=0,
        system_prompt="",
        payload={},
        retry_template="FIX: '{field}' → {error}",
    )
    result = validate_output('{"score": 1}', custom, schema)
    assert result.retry_instruction.startswith("FIX:")


def test_validate_with_prose_before_json(contract, schema):
    output = 'Here is my answer: {"result": "great work", "score": 1.0}'
    result = validate_output(output, contract, schema)
    assert result.ok is True
    assert result.data["result"] == "great work"


# --- rich format validation ---

@pytest.fixture
def email_schema():
    return {
        "type": "object",
        "properties": {"email": {"type": "string", "format": "email"}},
        "required": ["email"],
    }


@pytest.fixture
def uri_schema():
    return {
        "type": "object",
        "properties": {"url": {"type": "string", "format": "url"}},
        "required": ["url"],
    }


@pytest.fixture
def date_schema():
    return {
        "type": "object",
        "properties": {"date": {"type": "string", "format": "date"}},
        "required": ["date"],
    }


def test_format_email_valid(contract, email_schema):
    """Valid email passes format check."""
    result = validate_output('{"email": "user@example.com"}', contract, email_schema)
    assert result.ok is True


def test_format_email_invalid(contract, email_schema):
    """Invalid email fails format check and returns retry_instruction."""
    result = validate_output('{"email": "not-an-email"}', contract, email_schema)
    assert result.ok is False
    assert result.retry_instruction is not None


def test_format_uri_valid(contract, uri_schema):
    """Valid URI passes format check."""
    result = validate_output('{"url": "https://example.com/path"}', contract, uri_schema)
    assert result.ok is True


def test_format_uri_invalid(contract, uri_schema):
    """Invalid URI fails format check."""
    result = validate_output('{"url": "not a url"}', contract, uri_schema)
    assert result.ok is False


def test_format_date_valid(contract, date_schema):
    """Valid ISO date passes format check."""
    result = validate_output('{"date": "2024-01-15"}', contract, date_schema)
    assert result.ok is True


def test_format_date_invalid(contract, date_schema):
    """Invalid date string fails format check."""
    result = validate_output('{"date": "15/01/2024"}', contract, date_schema)
    assert result.ok is False


def test_enum_validation(contract):
    """Enum constraint enforced without FormatChecker."""
    schema = {
        "type": "object",
        "properties": {"color": {"type": "string", "enum": ["red", "green", "blue"]}},
        "required": ["color"],
    }
    assert validate_output('{"color": "red"}', contract, schema).ok is True
    assert validate_output('{"color": "purple"}', contract, schema).ok is False


def test_pattern_validation(contract):
    """Regex pattern constraint enforced."""
    schema = {
        "type": "object",
        "properties": {"code": {"type": "string", "pattern": "^[A-Z]{3}-\\d{4}$"}},
        "required": ["code"],
    }
    assert validate_output('{"code": "ABC-1234"}', contract, schema).ok is True
    assert validate_output('{"code": "abc-1234"}', contract, schema).ok is False
