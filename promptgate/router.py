"""FTS5 BM25 search with keyword LIKE fallback."""
from __future__ import annotations

from pathlib import Path

from loguru import logger

from promptgate.storage import SQLiteBackend, _DEFAULT_DB_PATH


def search(
    query: str,
    db_path: str | Path = _DEFAULT_DB_PATH,
    limit: int = 5,
) -> list[tuple[str, float]]:
    """Search prompts by relevance using FTS5 BM25, falling back to LIKE.

    Attempts FTS5 full-text search first. If the query contains characters
    that break FTS5 syntax (unmatched quotes, stray operators), falls back
    to a case-insensitive LIKE scan across name, description, and tags.

    Args:
        query: Search string. Supports FTS5 boolean operators when valid.
        db_path: Path to the SQLite database. Defaults to ``~/.promptgate/db.sqlite``.
        limit: Maximum number of results to return.

    Returns:
        List of ``(prompt_id, score)`` tuples ordered by relevance descending.
        FTS5 scores are BM25-derived (higher = more relevant).
        Fallback LIKE scores are ``1.0`` for all matches.

    Examples:
        >>> results = search("sales report")
        >>> isinstance(results, list)
        True
    """
    backend = SQLiteBackend(db_path)
    backend.init()

    try:
        results = backend.search_fts(query, limit=limit)
        logger.debug("FTS5 search '{}' → {} results", query, len(results))
        return results
    except Exception as exc:
        logger.warning("FTS5 failed for '{}': {}; falling back to LIKE", query, exc)
        return _like_fallback(backend, query, limit)


def _like_fallback(backend: SQLiteBackend, query: str, limit: int) -> list[tuple[str, float]]:
    """Case-insensitive substring scan when FTS5 query is malformed.

    Args:
        backend: Initialized SQLiteBackend instance.
        query: Raw search string (not interpreted as FTS5).
        limit: Maximum results.

    Returns:
        List of ``(prompt_id, 1.0)`` tuples for all matches.

    Examples:
        >>> backend = SQLiteBackend(":memory:")
        >>> backend.init()
        >>> _like_fallback(backend, "test", 5)
        []
    """
    pattern = f"%{query}%"
    with backend._connect() as conn:
        rows = conn.execute(
            """
            SELECT id FROM prompts
            WHERE name        LIKE ? COLLATE NOCASE
               OR description LIKE ? COLLATE NOCASE
               OR tags        LIKE ? COLLATE NOCASE
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (pattern, pattern, pattern, limit),
        ).fetchall()
    results = [(r["id"], 1.0) for r in rows]
    logger.debug("LIKE fallback '{}' → {} results", query, len(results))
    return results
