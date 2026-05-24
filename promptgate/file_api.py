"""Cache read/write, in-memory TTL dict, get_or_compile."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from loguru import logger

from promptgate.compiler import _schema_hash, compile_prompt
from promptgate.models import CompiledContract, PromptConfig
from promptgate.storage import SQLiteBackend, _DEFAULT_DB_PATH


_CACHE_DIR = Path.home() / ".promptgate" / "contracts"

# in-memory TTL cache: (prompt_id, schema_hash) -> (contract, expires_at)
_mem_cache: dict[tuple[str, str], tuple[CompiledContract, float]] = {}


def _model_seg(model_id: str | None) -> str:
    """Sanitize model_id for use in a filename segment."""
    if not model_id:
        return "base"
    return model_id.replace("/", "-").replace(".", "-")


def _contract_path(prompt_id: str, sh: str, compiled_at: int, model_id: str | None = None) -> Path:
    return _CACHE_DIR / f"contract_{prompt_id}_{sh}_{_model_seg(model_id)}_{compiled_at}.json"


def _save_contract(contract: CompiledContract) -> Path:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _contract_path(contract.prompt_id, contract.schema_hash, contract.compiled_at, contract.model_id)
    path.write_text(contract.model_dump_json(), encoding="utf-8")
    return path


def _load_latest_contract(prompt_id: str, sh: str, model_id: str | None = None) -> CompiledContract | None:
    """Load the most recent cached contract file matching prompt_id + schema_hash + model."""
    if not _CACHE_DIR.exists():
        return None
    pattern = f"contract_{prompt_id}_{sh}_{_model_seg(model_id)}_*.json"
    candidates = sorted(_CACHE_DIR.glob(pattern), reverse=True)
    for path in candidates:
        try:
            return CompiledContract.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:
            continue
    return None


def get_or_compile(
    prompt_id: str,
    payload: dict,
    db_path: str | Path = _DEFAULT_DB_PATH,
    ttl_seconds: int = 3600,
    model_id: str | None = None,
) -> CompiledContract:
    """Return a cached CompiledContract or compile a fresh one.

    Lookup order:
    1. In-memory TTL cache (keyed by prompt_id + schema_hash + model_id).
    2. Filesystem cache (``~/.promptgate/contracts/``).
    3. Fresh compile from storage.

    Args:
        prompt_id: ID of the stored prompt.
        payload: Data to fill into the prompt template.
        db_path: Path to SQLite database.
        ttl_seconds: In-memory cache TTL in seconds.
        model_id: Optional LLM model ID for model-aware compilation.

    Returns:
        CompiledContract ready to send to an LLM.

    Raises:
        KeyError: If prompt_id is not found in storage.

    Examples:
        >>> # Returns CompiledContract; actual DB needed for full test
        >>> isinstance(get_or_compile, object)
        True
    """
    backend = SQLiteBackend(db_path)
    backend.init()

    prompt = backend.get(prompt_id)
    if prompt is None:
        raise KeyError(f"Prompt '{prompt_id}' not found in storage")

    sh = _schema_hash(prompt.schema_)
    cache_key = (prompt_id, sh, model_id or "")
    now = time.time()

    # 1. memory cache
    if cache_key in _mem_cache:
        contract, expires_at = _mem_cache[cache_key]
        if now < expires_at:
            logger.debug("Memory cache hit: {}/{}/{}", prompt_id, sh, model_id or "base")
            return contract
        del _mem_cache[cache_key]

    # 2. filesystem cache
    cached = _load_latest_contract(prompt_id, sh, model_id)
    if cached is not None:
        _mem_cache[cache_key] = (cached, now + ttl_seconds)
        logger.debug("Filesystem cache hit: {}/{}/{}", prompt_id, sh, model_id or "base")
        return cached

    # 3. compile fresh
    contract = compile_prompt(prompt, payload, model_id=model_id)
    _save_contract(contract)
    _mem_cache[cache_key] = (contract, now + ttl_seconds)
    logger.debug("Compiled fresh contract: {}/{}/{}", prompt_id, sh, model_id or "base")
    return contract


def purge_stale(max_age_seconds: int = 86400 * 7) -> int:
    """Delete contract files older than max_age_seconds.

    Args:
        max_age_seconds: Age threshold in seconds. Default: 7 days.

    Returns:
        Number of files deleted.

    Examples:
        >>> purge_stale(0)  # purge everything
        0
    """
    if not _CACHE_DIR.exists():
        return 0
    cutoff = time.time() - max_age_seconds
    deleted = 0
    for path in _CACHE_DIR.glob("contract_*.json"):
        if path.stat().st_mtime < cutoff:
            path.unlink()
            deleted += 1
    _mem_cache.clear()
    logger.info("Purged {} stale contract files", deleted)
    return deleted
