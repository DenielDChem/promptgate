"""Tests for SQLiteBackend storage implementation."""
from __future__ import annotations

import pytest

from promptgate.models import PromptConfig
from promptgate.storage import SQLiteBackend


@pytest.fixture
def backend(tmp_path):
    b = SQLiteBackend(tmp_path / "test.db")
    b.init()
    return b


@pytest.fixture
def sample_prompt():
    return PromptConfig(
        id="sales_report_v1",
        name="Sales Report",
        tags=["sales", "reporting"],
        **{"schema": {"type": "object", "properties": {"period": {"type": "string"}}}},
        template="Generate a {{period}} sales report.",
        description="Monthly and quarterly sales summaries",
    )


def test_upsert_and_get(backend, sample_prompt):
    backend.upsert(sample_prompt)
    result = backend.get("sales_report_v1")
    assert result is not None
    assert result.id == "sales_report_v1"
    assert result.name == "Sales Report"
    assert result.tags == ["sales", "reporting"]
    assert result.template == "Generate a {{period}} sales report."


def test_get_missing_returns_none(backend):
    assert backend.get("nonexistent") is None


def test_upsert_updates_existing(backend, sample_prompt):
    backend.upsert(sample_prompt)
    updated = sample_prompt.model_copy(update={"name": "Updated Sales Report"})
    backend.upsert(updated)
    result = backend.get("sales_report_v1")
    assert result.name == "Updated Sales Report"


def test_delete_existing(backend, sample_prompt):
    backend.upsert(sample_prompt)
    assert backend.delete("sales_report_v1") is True
    assert backend.get("sales_report_v1") is None


def test_delete_missing_returns_false(backend):
    assert backend.delete("nonexistent") is False


def test_list_all_empty(backend):
    assert backend.list_all() == []


def test_list_all_returns_all(backend, sample_prompt):
    backend.upsert(sample_prompt)
    second = PromptConfig(
        id="email_v1",
        name="Email Draft",
        tags=["email"],
        **{"schema": {}},
        template="Draft an email about {{topic}}.",
    )
    backend.upsert(second)
    results = backend.list_all()
    assert len(results) == 2
    ids = {p.id for p in results}
    assert ids == {"sales_report_v1", "email_v1"}


def test_search_fts_finds_prompt(backend, sample_prompt):
    """Critical: upsert → search must return the inserted prompt (catches missing trigger bug)."""
    backend.upsert(sample_prompt)
    results = backend.search_fts("sales")
    assert len(results) >= 1
    ids = [r[0] for r in results]
    assert "sales_report_v1" in ids


def test_search_fts_scores_are_positive(backend, sample_prompt):
    backend.upsert(sample_prompt)
    results = backend.search_fts("sales")
    for _, score in results:
        assert score > 0


def test_search_fts_no_match_returns_empty(backend, sample_prompt):
    backend.upsert(sample_prompt)
    results = backend.search_fts("zxqwerty_nonexistent")
    assert results == []


def test_search_fts_respects_limit(backend):
    for i in range(10):
        p = PromptConfig(
            id=f"report_{i}",
            name=f"Report {i}",
            tags=["report"],
            **{"schema": {}},
            template=f"Report number {i}.",
            description="report summary document",
        )
        backend.upsert(p)
    results = backend.search_fts("report", limit=3)
    assert len(results) <= 3


def test_fts_syncs_after_delete(backend, sample_prompt):
    """FTS index must stay consistent after DELETE (tests the delete trigger)."""
    backend.upsert(sample_prompt)
    backend.delete("sales_report_v1")
    results = backend.search_fts("sales")
    ids = [r[0] for r in results]
    assert "sales_report_v1" not in ids


def test_fts_syncs_after_update(backend, sample_prompt):
    """FTS index must reflect updated content (tests the update trigger)."""
    backend.upsert(sample_prompt)
    updated = sample_prompt.model_copy(
        update={"description": "Completely different topic about invoices"}
    )
    backend.upsert(updated)
    results = backend.search_fts("invoices")
    ids = [r[0] for r in results]
    assert "sales_report_v1" in ids


def test_init_is_idempotent(tmp_path):
    """Multiple init() calls must not raise or duplicate tables/triggers."""
    b = SQLiteBackend(tmp_path / "idempotent.db")
    b.init()
    b.init()
    b.init()


def test_schema_roundtrip(backend):
    """Complex JSON schema must survive storage without mutation."""
    schema = {
        "type": "object",
        "properties": {
            "period": {"type": "string", "enum": ["monthly", "quarterly"]},
            "metrics": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["period"],
    }
    p = PromptConfig(
        id="schema_test",
        name="Schema Test",
        **{"schema": schema},
        template="test",
    )
    backend.upsert(p)
    result = backend.get("schema_test")
    assert result.schema_ == schema
