"""Tests for file_api.py."""
from __future__ import annotations

import time
import pytest

from promptgate.file_api import get_or_compile, purge_stale, _mem_cache
from promptgate.models import PromptConfig
from promptgate.storage import SQLiteBackend


@pytest.fixture(autouse=True)
def clear_mem_cache():
    _mem_cache.clear()
    yield
    _mem_cache.clear()


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "api_test.db"


@pytest.fixture
def seeded_db(db_path):
    backend = SQLiteBackend(db_path)
    backend.init()
    p = PromptConfig(
        id="sales",
        name="Sales",
        **{"schema": {"type": "object", "properties": {"period": {"type": "string"}}, "required": ["period"]}},
        template="Sales for {{ period }}.",
    )
    backend.upsert(p)
    return db_path


def test_get_or_compile_returns_contract(seeded_db):
    contract = get_or_compile("sales", {"period": "2024-01"}, db_path=seeded_db)
    assert contract.prompt_id == "sales"
    assert "2024-01" in contract.system_prompt


def test_get_or_compile_missing_prompt_raises(db_path):
    backend = SQLiteBackend(db_path)
    backend.init()
    with pytest.raises(KeyError, match="nonexistent"):
        get_or_compile("nonexistent", {}, db_path=db_path)


def test_get_or_compile_uses_memory_cache(seeded_db):
    c1 = get_or_compile("sales", {"period": "2024-01"}, db_path=seeded_db)
    c2 = get_or_compile("sales", {"period": "2024-01"}, db_path=seeded_db)
    assert c1.compiled_at == c2.compiled_at


def test_get_or_compile_memory_cache_expires(seeded_db, monkeypatch):
    import promptgate.file_api as fa

    # Disable fs cache entirely so only memory TTL is tested
    monkeypatch.setattr(fa, "_load_latest_contract", lambda *a, **kw: None)
    monkeypatch.setattr(fa, "_save_contract", lambda *a, **kw: None)

    calls = []
    original = fa.compile_prompt

    def counting_compile(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(fa, "compile_prompt", counting_compile)

    # ttl_seconds=0 → memory expires immediately; fs disabled → both calls compile fresh
    get_or_compile("sales", {"period": "2024-01"}, db_path=seeded_db, ttl_seconds=0)
    get_or_compile("sales", {"period": "2024-01"}, db_path=seeded_db, ttl_seconds=0)
    assert len(calls) == 2


def test_purge_stale_removes_old_files(tmp_path):
    from promptgate.file_api import _CACHE_DIR, _save_contract
    from promptgate.models import CompiledContract

    old_contract = CompiledContract(
        prompt_id="old",
        schema_hash="abc",
        compiled_at=int(time.time()) - 9999,
        system_prompt="old",
        payload={},
    )
    path = _save_contract(old_contract)
    import os
    os.utime(path, (time.time() - 9999, time.time() - 9999))
    deleted = purge_stale(max_age_seconds=1)
    assert deleted >= 1
    assert not path.exists()


def test_purge_stale_no_cache_dir_returns_zero(monkeypatch):
    import promptgate.file_api as fa
    monkeypatch.setattr(fa, "_CACHE_DIR", fa.Path("/nonexistent_dir_xyz"))
    assert purge_stale() == 0
