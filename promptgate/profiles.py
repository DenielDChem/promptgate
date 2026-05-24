"""Named profile management for pgate environments (dev/staging/prod)."""
from __future__ import annotations

from pathlib import Path

import yaml
from loguru import logger

from promptgate.storage import _DEFAULT_DB_PATH


_PROFILES_PATH = Path.home() / ".promptgate" / "profiles.yaml"
_DEFAULT_CACHE_DIR = Path.home() / ".promptgate" / "contracts"


def _default_profile() -> dict:
    return {
        "db_path": str(_DEFAULT_DB_PATH),
        "cache_dir": str(_DEFAULT_CACHE_DIR),
        "default_model": None,
        "litellm_api_base": None,
    }


def load_profiles() -> dict:
    """Load profiles config from ~/.promptgate/profiles.yaml.

    Returns:
        Dict with keys ``default`` and ``profiles``.

    Examples:
        >>> isinstance(load_profiles(), dict)
        True
    """
    if not _PROFILES_PATH.exists():
        return {"default": "default", "profiles": {"default": _default_profile()}}
    data = yaml.safe_load(_PROFILES_PATH.read_text(encoding="utf-8")) or {}
    if "profiles" not in data:
        data["profiles"] = {"default": _default_profile()}
    if "default" not in data:
        data["default"] = "default"
    return data


def get_profile(name: str | None = None) -> dict:
    """Return resolved profile config, falling back to defaults for missing keys.

    Args:
        name: Profile name. Uses configured default when None.

    Returns:
        Profile dict with db_path, cache_dir, default_model, litellm_api_base.

    Raises:
        KeyError: If named profile does not exist.

    Examples:
        >>> p = get_profile()
        >>> "db_path" in p
        True
    """
    data = load_profiles()
    resolved = name or data.get("default", "default")
    profiles = data.get("profiles", {})
    if resolved not in profiles:
        raise KeyError(f"Profile '{resolved}' not found. Available: {list(profiles)}")
    base = _default_profile()
    base.update({k: v for k, v in profiles[resolved].items() if v is not None})
    logger.debug("Using profile '{}': db={}", resolved, base["db_path"])
    return base


def save_profile(name: str, config: dict) -> None:
    """Create or update a named profile.

    Args:
        name: Profile name.
        config: Partial or full profile dict (missing keys use defaults).

    Examples:
        >>> # save_profile writes to ~/.promptgate/profiles.yaml
    """
    _PROFILES_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = load_profiles()
    data["profiles"][name] = config
    _PROFILES_PATH.write_text(yaml.dump(data, default_flow_style=False, allow_unicode=True), encoding="utf-8")
    logger.debug("Saved profile '{}'", name)


def set_default_profile(name: str) -> None:
    """Set the default profile.

    Args:
        name: Profile name to use as default.

    Raises:
        KeyError: If profile does not exist.

    Examples:
        >>> # Requires ~/.promptgate/profiles.yaml to exist
    """
    data = load_profiles()
    if name not in data.get("profiles", {}):
        raise KeyError(f"Profile '{name}' not found")
    data["default"] = name
    _PROFILES_PATH.write_text(yaml.dump(data, default_flow_style=False, allow_unicode=True), encoding="utf-8")


def list_profiles() -> list[tuple[str, bool]]:
    """List all profiles with default flag.

    Returns:
        List of (name, is_default) tuples.

    Examples:
        >>> isinstance(list_profiles(), list)
        True
    """
    data = load_profiles()
    default = data.get("default", "default")
    return [(name, name == default) for name in sorted(data.get("profiles", {}))]
