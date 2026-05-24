"""Tests for CLI commands."""
from __future__ import annotations

import json
import pytest
from click.testing import CliRunner

from promptgate.cli import main
from promptgate.models import PromptConfig
from promptgate.storage import SQLiteBackend


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "cli_test.db")


@pytest.fixture
def seeded_db(db_path):
    backend = SQLiteBackend(db_path)
    backend.init()
    p = PromptConfig(
        id="sales_v1",
        name="Sales Report",
        tags=["sales"],
        **{"schema": {
            "type": "object",
            "properties": {"period": {"type": "string"}},
            "required": ["period"],
        }},
        template="Sales for {{ period }}.",
        description="Monthly sales report",
    )
    backend.upsert(p)
    return db_path


def test_init_command(runner, db_path):
    result = runner.invoke(main, ["--db", db_path, "init"])
    assert result.exit_code == 0
    assert "Initialized" in result.output


def test_add_from_file(runner, db_path, tmp_path):
    yaml_file = tmp_path / "prompt.yaml"
    yaml_file.write_text(
        "id: test_prompt\nname: Test\nschema: {}\ntemplate: hello\n",
        encoding="utf-8",
    )
    result = runner.invoke(main, ["--db", db_path, "add", "--file", str(yaml_file)])
    assert result.exit_code == 0
    assert "test_prompt" in result.output


def test_add_requires_file_or_url(runner, db_path):
    result = runner.invoke(main, ["--db", db_path, "add"])
    assert result.exit_code != 0


def test_search_finds_result(runner, seeded_db):
    result = runner.invoke(main, ["--db", seeded_db, "search", "sales"])
    assert result.exit_code == 0
    assert "sales_v1" in result.output


def test_search_no_match(runner, seeded_db):
    result = runner.invoke(main, ["--db", seeded_db, "search", "zxqwerty_impossible"])
    assert result.exit_code == 0
    assert "No results" in result.output


def test_compile_with_payload(runner, seeded_db):
    result = runner.invoke(
        main,
        ["--db", seeded_db, "compile", "sales_v1", "--payload", '{"period": "2024-01"}'],
    )
    assert result.exit_code == 0
    assert "2024-01" in result.output


def test_compile_missing_prompt(runner, db_path):
    backend = SQLiteBackend(db_path)
    backend.init()
    result = runner.invoke(main, ["--db", db_path, "compile", "nonexistent"])
    assert result.exit_code != 0


def test_compile_interactive(runner, seeded_db):
    result = runner.invoke(
        main,
        ["--db", seeded_db, "compile", "sales_v1", "--interactive"],
        input="2024-03\n",
    )
    assert result.exit_code == 0
    assert "2024-03" in result.output


def test_purge_command(runner, db_path):
    result = runner.invoke(main, ["--db", db_path, "purge", "--days", "0"])
    assert result.exit_code == 0
    assert "Deleted" in result.output


def test_help(runner):
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "PromptGate" in result.output
