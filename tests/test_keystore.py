"""Tests for Fernet-encrypted keystore."""
import pytest
from pathlib import Path
from promptgate.keystore import delete_key, get_key, list_keys, set_key


@pytest.fixture()
def store(tmp_path: Path):
    """Return (key_file, store_file) pair in tmp_path."""
    return tmp_path / "k", tmp_path / "s"


def test_set_and_get(store):
    kf, sf = store
    set_key("openai", "sk-test", key_file=kf, store_file=sf)
    assert get_key("openai", key_file=kf, store_file=sf) == "sk-test"


def test_get_missing_returns_none(store):
    kf, sf = store
    assert get_key("missing", key_file=kf, store_file=sf) is None


def test_set_overwrite(store):
    kf, sf = store
    set_key("k", "v1", key_file=kf, store_file=sf)
    set_key("k", "v2", key_file=kf, store_file=sf)
    assert get_key("k", key_file=kf, store_file=sf) == "v2"


def test_list_keys(store):
    kf, sf = store
    set_key("b", "2", key_file=kf, store_file=sf)
    set_key("a", "1", key_file=kf, store_file=sf)
    assert list_keys(key_file=kf, store_file=sf) == ["a", "b"]


def test_list_empty(store):
    kf, sf = store
    assert list_keys(key_file=kf, store_file=sf) == []


def test_delete_existing(store):
    kf, sf = store
    set_key("x", "val", key_file=kf, store_file=sf)
    assert delete_key("x", key_file=kf, store_file=sf) is True
    assert get_key("x", key_file=kf, store_file=sf) is None


def test_delete_missing(store):
    kf, sf = store
    assert delete_key("nonexistent", key_file=kf, store_file=sf) is False


def test_store_file_encrypted(store):
    kf, sf = store
    set_key("secret", "password123", key_file=kf, store_file=sf)
    raw = sf.read_bytes()
    assert b"password123" not in raw


def test_multiple_keys_independent(store):
    kf, sf = store
    set_key("a", "alpha", key_file=kf, store_file=sf)
    set_key("b", "beta", key_file=kf, store_file=sf)
    assert get_key("a", key_file=kf, store_file=sf) == "alpha"
    assert get_key("b", key_file=kf, store_file=sf) == "beta"
