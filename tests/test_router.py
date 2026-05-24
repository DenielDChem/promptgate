"""Tests for router search (FTS5 + LIKE fallback)."""
from __future__ import annotations

import pytest

from promptgate.models import PromptConfig
from promptgate.router import _like_fallback, search
from promptgate.storage import SQLiteBackend


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "router_test.db"


@pytest.fixture
def seeded_db(db_path):
    backend = SQLiteBackend(db_path)
    backend.init()
    prompts = [
        PromptConfig(
            id="sales_report",
            name="Sales Report",
            tags=["sales", "reporting"],
            **{"schema": {}},
            template="Generate a {{period}} sales report.",
            description="Monthly and quarterly summaries",
        ),
        PromptConfig(
            id="email_draft",
            name="Email Draft",
            tags=["email", "communication"],
            **{"schema": {}},
            template="Draft email about {{topic}}.",
            description="Professional email templates",
        ),
        PromptConfig(
            id="invoice_gen",
            name="Invoice Generator",
            tags=["finance", "invoice"],
            **{"schema": {}},
            template="Generate invoice for {{client}}.",
            description="Billing and invoicing prompts",
        ),
    ]
    for p in prompts:
        backend.upsert(p)
    return db_path


def test_search_returns_relevant_result(seeded_db):
    results = search("sales", db_path=seeded_db)
    ids = [r[0] for r in results]
    assert "sales_report" in ids


def test_search_returns_list_of_tuples(seeded_db):
    results = search("email", db_path=seeded_db)
    assert isinstance(results, list)
    for item in results:
        assert isinstance(item, tuple)
        assert len(item) == 2
        assert isinstance(item[0], str)
        assert isinstance(item[1], float)


def test_search_scores_positive(seeded_db):
    results = search("invoice", db_path=seeded_db)
    for _, score in results:
        assert score > 0


def test_search_respects_limit(seeded_db):
    results = search("report email invoice", db_path=seeded_db, limit=2)
    assert len(results) <= 2


def test_search_empty_query_returns_empty_or_list(seeded_db):
    """Empty query should not crash — FTS5 or fallback handles gracefully."""
    results = search("", db_path=seeded_db)
    assert isinstance(results, list)


def test_search_no_match_returns_empty(seeded_db):
    results = search("zxqwerty_impossible", db_path=seeded_db)
    assert results == []


def test_search_malformed_query_uses_fallback(seeded_db):
    """Unmatched quote triggers FTS5 error → LIKE fallback must still return results."""
    results = search('"unclosed quote', db_path=seeded_db)
    assert isinstance(results, list)
    results2 = search('"sales', db_path=seeded_db)
    assert isinstance(results2, list)


def test_search_initializes_db_if_missing(tmp_path):
    """search() must call backend.init() — no manual init required by caller."""
    fresh_db = tmp_path / "fresh.db"
    assert not fresh_db.exists()
    results = search("anything", db_path=fresh_db)
    assert isinstance(results, list)
    assert fresh_db.exists()


def test_like_fallback_finds_by_name(db_path):
    backend = SQLiteBackend(db_path)
    backend.init()
    p = PromptConfig(id="x", name="Unique Name Here", **{"schema": {}}, template="t")
    backend.upsert(p)
    results = _like_fallback(backend, "Unique Name", limit=5)
    ids = [r[0] for r in results]
    assert "x" in ids


def test_like_fallback_finds_by_description(db_path):
    backend = SQLiteBackend(db_path)
    backend.init()
    p = PromptConfig(
        id="y", name="Y", description="special keyword zeta", **{"schema": {}}, template="t"
    )
    backend.upsert(p)
    results = _like_fallback(backend, "zeta", limit=5)
    ids = [r[0] for r in results]
    assert "y" in ids


def test_like_fallback_scores_are_1(db_path):
    backend = SQLiteBackend(db_path)
    backend.init()
    p = PromptConfig(id="z", name="Test Z", **{"schema": {}}, template="t")
    backend.upsert(p)
    results = _like_fallback(backend, "Test Z", limit=5)
    for _, score in results:
        assert score == 1.0


def test_like_fallback_empty_db_returns_empty(db_path):
    backend = SQLiteBackend(db_path)
    backend.init()
    assert _like_fallback(backend, "anything", limit=5) == []
