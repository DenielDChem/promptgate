"""Tests for promptgate.profiles — named profile management."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest


def _patch_profiles_path(tmp_path: Path):
    profiles_path = tmp_path / "profiles.yaml"
    return patch("promptgate.profiles._PROFILES_PATH", profiles_path)


def test_get_profile_default_when_no_file(tmp_path: Path) -> None:
    with _patch_profiles_path(tmp_path):
        from promptgate.profiles import get_profile
        p = get_profile()
    assert "db_path" in p
    assert "default_model" in p


def test_save_and_get_profile(tmp_path: Path) -> None:
    with _patch_profiles_path(tmp_path):
        from promptgate.profiles import get_profile, save_profile
        save_profile("dev", {"db_path": "/tmp/dev.sqlite", "default_model": "gpt-4o-mini"})
        p = get_profile("dev")
    assert p["db_path"] == "/tmp/dev.sqlite"
    assert p["default_model"] == "gpt-4o-mini"


def test_get_missing_profile_raises(tmp_path: Path) -> None:
    with _patch_profiles_path(tmp_path):
        from promptgate.profiles import get_profile
        with pytest.raises(KeyError, match="ghost"):
            get_profile("ghost")


def test_set_default_profile(tmp_path: Path) -> None:
    with _patch_profiles_path(tmp_path):
        from promptgate.profiles import get_profile, list_profiles, save_profile, set_default_profile
        save_profile("staging", {"db_path": "/tmp/staging.sqlite"})
        set_default_profile("staging")
        profiles = list_profiles()
    default = next(name for name, is_default in profiles if is_default)
    assert default == "staging"


def test_set_default_missing_raises(tmp_path: Path) -> None:
    with _patch_profiles_path(tmp_path):
        from promptgate.profiles import set_default_profile
        with pytest.raises(KeyError):
            set_default_profile("nope")


def test_list_profiles_sorted(tmp_path: Path) -> None:
    with _patch_profiles_path(tmp_path):
        from promptgate.profiles import list_profiles, save_profile
        save_profile("prod", {})
        save_profile("dev", {})
        profiles = list_profiles()
    names = [n for n, _ in profiles]
    assert names == sorted(names)


def test_profile_defaults_filled(tmp_path: Path) -> None:
    with _patch_profiles_path(tmp_path):
        from promptgate.profiles import get_profile, save_profile
        save_profile("minimal", {"default_model": "gpt-4o"})
        p = get_profile("minimal")
    assert "db_path" in p
    assert "cache_dir" in p
    assert p["default_model"] == "gpt-4o"
