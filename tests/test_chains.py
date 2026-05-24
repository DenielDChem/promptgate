"""Tests for promptgate.chains — chain CRUD and execution."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from promptgate.chains import (
    ChainConfig,
    ChainStep,
    delete_chain,
    get_chain,
    list_chains,
    upsert_chain,
)
from promptgate.models import PromptConfig
from promptgate.storage import SQLiteBackend


def _seed_prompt(db_path: Path, prompt_id: str = "step_v1") -> None:
    backend = SQLiteBackend(db_path)
    backend.init()
    backend.upsert(PromptConfig.model_validate({
        "id": prompt_id,
        "name": "Step",
        "template": "Process {{ input }}.",
        "schema": {
            "type": "object",
            "properties": {"output": {"type": "string"}},
            "required": ["output"],
        },
    }))


def _make_chain(chain_id: str = "pipe_v1") -> ChainConfig:
    return ChainConfig(
        id=chain_id,
        name="Test Pipeline",
        steps=[
            ChainStep(prompt_id="step_v1", model="gpt-4o"),
            ChainStep(prompt_id="step_v1", model="gpt-4o", output_as="result"),
        ],
    )


def _make_response(content: str) -> SimpleNamespace:
    msg = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=msg)
    return SimpleNamespace(choices=[choice])


# ── CRUD ──────────────────────────────────────────────────────────────────────

def test_upsert_and_get(tmp_path: Path) -> None:
    db = tmp_path / "db.sqlite"
    chain = _make_chain()
    upsert_chain(chain, db)
    fetched = get_chain("pipe_v1", db)
    assert fetched is not None
    assert fetched.id == "pipe_v1"
    assert len(fetched.steps) == 2


def test_get_missing_returns_none(tmp_path: Path) -> None:
    db = tmp_path / "db.sqlite"
    assert get_chain("nope", db) is None


def test_upsert_overwrites(tmp_path: Path) -> None:
    db = tmp_path / "db.sqlite"
    chain = _make_chain()
    upsert_chain(chain, db)
    chain2 = ChainConfig(id="pipe_v1", name="Updated", steps=[ChainStep(prompt_id="step_v1", model="gpt-4o")])
    upsert_chain(chain2, db)
    fetched = get_chain("pipe_v1", db)
    assert fetched.name == "Updated"
    assert len(fetched.steps) == 1


def test_list_chains(tmp_path: Path) -> None:
    db = tmp_path / "db.sqlite"
    upsert_chain(_make_chain("a"), db)
    upsert_chain(_make_chain("b"), db)
    chains = list_chains(db)
    assert len(chains) == 2
    ids = {c.id for c in chains}
    assert ids == {"a", "b"}


def test_delete_chain(tmp_path: Path) -> None:
    db = tmp_path / "db.sqlite"
    upsert_chain(_make_chain(), db)
    assert delete_chain("pipe_v1", db)
    assert get_chain("pipe_v1", db) is None


def test_delete_missing_returns_false(tmp_path: Path) -> None:
    db = tmp_path / "db.sqlite"
    assert not delete_chain("ghost", db)


# ── run_chain ─────────────────────────────────────────────────────────────────

def test_run_chain_ok(tmp_path: Path) -> None:
    db = tmp_path / "db.sqlite"
    _seed_prompt(db)
    chain = ChainConfig(
        id="pipe_v1",
        name="Pipeline",
        steps=[ChainStep(prompt_id="step_v1", model="gpt-4o", output_as="out")],
    )
    upsert_chain(chain, db)

    good = json.dumps({"output": "done"})
    with patch("litellm.completion", return_value=_make_response(good)):
        from promptgate.chains import run_chain
        result = run_chain("pipe_v1", {"input": "hello"}, db_path=db)

    assert result.ok
    assert result.steps_run == 1
    assert result.context["out"] == {"output": "done"}
    assert result.failed_step is None


def test_run_chain_fail_propagates(tmp_path: Path) -> None:
    db = tmp_path / "db.sqlite"
    _seed_prompt(db)
    chain = ChainConfig(
        id="pipe_v1",
        name="Pipeline",
        steps=[ChainStep(prompt_id="step_v1", model="gpt-4o")],
    )
    upsert_chain(chain, db)

    with patch("litellm.completion", return_value=_make_response("not json")):
        from promptgate.chains import run_chain
        result = run_chain("pipe_v1", {}, db_path=db, max_retries_per_step=1)

    assert not result.ok
    assert result.failed_step == 0
    assert result.steps_run == 1


def test_run_chain_missing_chain_raises(tmp_path: Path) -> None:
    db = tmp_path / "db.sqlite"
    from promptgate.chains import run_chain
    with pytest.raises(KeyError, match="ghost"):
        run_chain("ghost", {}, db_path=db)


def test_run_chain_input_map(tmp_path: Path) -> None:
    db = tmp_path / "db.sqlite"
    _seed_prompt(db)
    chain = ChainConfig(
        id="pipe_v1",
        name="Pipeline",
        steps=[ChainStep(
            prompt_id="step_v1",
            model="gpt-4o",
            input_map={"input": "raw"},
            output_as="step1",
        )],
    )
    upsert_chain(chain, db)

    good = json.dumps({"output": "mapped"})
    with patch("litellm.completion", return_value=_make_response(good)):
        from promptgate.chains import run_chain
        result = run_chain("pipe_v1", {"raw": "source_data"}, db_path=db)

    assert result.ok
    assert "step1" in result.context
