"""Fernet-encrypted API key store at ~/.promptgate/keys.enc."""
from __future__ import annotations

import json
from pathlib import Path

from cryptography.fernet import Fernet
from loguru import logger


_PROMPTGATE_DIR = Path.home() / ".promptgate"
_KEY_FILE = _PROMPTGATE_DIR / ".keystore_key"
_STORE_FILE = _PROMPTGATE_DIR / "keys.enc"


def _get_or_create_key() -> bytes:
    _PROMPTGATE_DIR.mkdir(parents=True, exist_ok=True)
    if _KEY_FILE.exists():
        return _KEY_FILE.read_bytes().strip()
    key = Fernet.generate_key()
    _KEY_FILE.write_bytes(key)
    _KEY_FILE.chmod(0o600)
    logger.debug("Generated Fernet key at {}", _KEY_FILE)
    return key


def _fernet(key_file: Path | None = None) -> Fernet:
    if key_file is not None:
        if key_file.exists():
            return Fernet(key_file.read_bytes().strip())
        key = Fernet.generate_key()
        key_file.parent.mkdir(parents=True, exist_ok=True)
        key_file.write_bytes(key)
        key_file.chmod(0o600)
        return Fernet(key)
    return Fernet(_get_or_create_key())


def _load_store(key_file: Path | None = None, store_file: Path | None = None) -> dict[str, str]:
    sf = store_file or _STORE_FILE
    if not sf.exists():
        return {}
    try:
        data = _fernet(key_file).decrypt(sf.read_bytes())
        return json.loads(data)
    except Exception:
        return {}


def _save_store(
    store: dict[str, str],
    key_file: Path | None = None,
    store_file: Path | None = None,
) -> None:
    sf = store_file or _STORE_FILE
    sf.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(store, ensure_ascii=False).encode()
    sf.write_bytes(_fernet(key_file).encrypt(data))
    sf.chmod(0o600)


def set_key(name: str, value: str, *, key_file: Path | None = None, store_file: Path | None = None) -> None:
    """Encrypt and store an API key.

    Args:
        name: Key name (e.g. ``"openai"``).
        value: Secret to store.
        key_file: Override Fernet key path (for testing).
        store_file: Override encrypted store path (for testing).

    Examples:
        >>> import tempfile; from pathlib import Path
        >>> d = Path(tempfile.mkdtemp())
        >>> set_key("test", "secret", key_file=d/"k", store_file=d/"s")
        >>> get_key("test", key_file=d/"k", store_file=d/"s")
        'secret'
    """
    store = _load_store(key_file, store_file)
    store[name] = value
    _save_store(store, key_file, store_file)
    logger.debug("Stored key '{}'", name)


def get_key(name: str, *, key_file: Path | None = None, store_file: Path | None = None) -> str | None:
    """Retrieve a decrypted API key.

    Args:
        name: Key name to retrieve.
        key_file: Override Fernet key path (for testing).
        store_file: Override encrypted store path (for testing).

    Returns:
        Decrypted value, or None if not found.

    Examples:
        >>> get_key("nonexistent") is None
        True
    """
    return _load_store(key_file, store_file).get(name)


def delete_key(name: str, *, key_file: Path | None = None, store_file: Path | None = None) -> bool:
    """Delete a stored API key.

    Args:
        name: Key name to delete.
        key_file: Override Fernet key path (for testing).
        store_file: Override encrypted store path (for testing).

    Returns:
        True if deleted, False if not found.

    Examples:
        >>> delete_key("nonexistent")
        False
    """
    store = _load_store(key_file, store_file)
    if name not in store:
        return False
    del store[name]
    _save_store(store, key_file, store_file)
    return True


def list_keys(*, key_file: Path | None = None, store_file: Path | None = None) -> list[str]:
    """List stored key names (not values).

    Args:
        key_file: Override Fernet key path (for testing).
        store_file: Override encrypted store path (for testing).

    Returns:
        Sorted list of key names.

    Examples:
        >>> import tempfile; from pathlib import Path
        >>> d = Path(tempfile.mkdtemp())
        >>> list_keys(key_file=d/"k", store_file=d/"s")
        []
    """
    return sorted(_load_store(key_file, store_file).keys())
