"""Tests for promptgate.runner — LiteLLM execution with retry."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from promptgate.models import PromptConfig
from promptgate.storage import SQLiteBackend


def _seed_db(db_path: Path) -> None:
    backend = SQLiteBackend(db_path)
    backend.init()
    prompt = PromptConfig.model_validate({
        "id": "greet_v1",
        "name": "Greeting",
        "template": "Greet {{ name }}.",
        "schema": {
            "type": "object",
            "properties": {"greeting": {"type": "string"}},
            "required": ["greeting"],
        },
    })
    backend.upsert(prompt)


def _make_response(content: str) -> SimpleNamespace:
    msg = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=msg)
    return SimpleNamespace(choices=[choice])


def test_run_ok_first_attempt(tmp_path: Path) -> None:
    _seed_db(tmp_path / "db.sqlite")
    good_output = json.dumps({"greeting": "Hello, Alice!"})

    with patch("litellm.completion", return_value=_make_response(good_output)):
        from promptgate.runner import run
        result = run("greet_v1", {"name": "Alice"}, "gpt-4o", db_path=tmp_path / "db.sqlite")

    assert result.ok
    assert result.data == {"greeting": "Hello, Alice!"}
    assert result.attempts == 1


def test_run_retries_then_succeeds(tmp_path: Path) -> None:
    _seed_db(tmp_path / "db.sqlite")
    bad = "not json at all"
    good = json.dumps({"greeting": "Hi!"})

    side_effects = [_make_response(bad), _make_response(bad), _make_response(good)]
    with patch("litellm.completion", side_effect=side_effects):
        from promptgate.runner import run
        result = run("greet_v1", {}, "gpt-4o", db_path=tmp_path / "db.sqlite", max_retries=3)

    assert result.ok
    assert result.attempts == 3


def test_run_exhausts_retries(tmp_path: Path) -> None:
    _seed_db(tmp_path / "db.sqlite")

    with patch("litellm.completion", return_value=_make_response("bad output")):
        from promptgate.runner import run
        result = run("greet_v1", {}, "gpt-4o", db_path=tmp_path / "db.sqlite", max_retries=2)

    assert not result.ok
    assert result.attempts == 2
    assert result.data is None


def test_run_raises_key_error_for_missing_prompt(tmp_path: Path) -> None:
    backend = SQLiteBackend(tmp_path / "db.sqlite")
    backend.init()

    with patch("litellm.completion"):
        from promptgate.runner import run
        with pytest.raises(KeyError, match="missing_prompt"):
            run("missing_prompt", {}, "gpt-4o", db_path=tmp_path / "db.sqlite")


def test_run_result_fields(tmp_path: Path) -> None:
    _seed_db(tmp_path / "db.sqlite")
    good = json.dumps({"greeting": "Hey!"})

    with patch("litellm.completion", return_value=_make_response(good)):
        from promptgate.runner import run
        result = run("greet_v1", {"name": "Bob"}, "gpt-4o-mini", db_path=tmp_path / "db.sqlite")

    assert result.prompt_id == "greet_v1"
    assert result.model_id == "gpt-4o-mini"
    assert result.raw_output == good
