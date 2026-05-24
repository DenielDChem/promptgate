"""SQLite + FTS5 storage backend."""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from loguru import logger

from promptgate.backends.base import StorageBackend
from promptgate.models import PromptConfig


_DEFAULT_DB_PATH = Path.home() / ".promptgate" / "db.sqlite"


def _row_to_prompt(row: sqlite3.Row) -> PromptConfig:
    return PromptConfig.model_validate(
        {
            "id": row["id"],
            "name": row["name"],
            "tags": json.loads(row["tags"]),
            "schema": json.loads(row["schema_json"]),
            "template": row["template"],
            "description": row["description"],
        }
    )


class SQLiteBackend:
    """SQLite + FTS5 implementation of StorageBackend.

    Args:
        db_path: Path to the SQLite database file. Defaults to
            ``~/.promptgate/db.sqlite``.

    Examples:
        >>> backend = SQLiteBackend()
        >>> backend.init()
        >>> prompt = PromptConfig(id="test", name="Test", schema={}, template="hi")
        >>> backend.upsert(prompt)
        >>> backend.get("test").id
        'test'
    """

    def __init__(self, db_path: Path | str = _DEFAULT_DB_PATH) -> None:
        self._path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def init(self) -> None:
        """Create tables, FTS index, and sync triggers if they don't exist.

        Examples:
            >>> backend = SQLiteBackend(":memory:")
            >>> backend.init()  # idempotent
            >>> backend.init()  # second call is safe
        """
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS prompts (
                    id          TEXT PRIMARY KEY,
                    name        TEXT NOT NULL,
                    tags        TEXT NOT NULL DEFAULT '[]',
                    schema_json TEXT NOT NULL DEFAULT '{}',
                    template    TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '',
                    created_at  INTEGER NOT NULL,
                    updated_at  INTEGER NOT NULL
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS prompts_fts USING fts5(
                    id UNINDEXED,
                    name,
                    tags,
                    description,
                    template,
                    content='prompts',
                    content_rowid='rowid'
                );

                CREATE TRIGGER IF NOT EXISTS prompts_ai AFTER INSERT ON prompts BEGIN
                    INSERT INTO prompts_fts(rowid, id, name, tags, description, template)
                    VALUES (new.rowid, new.id, new.name, new.tags, new.description, new.template);
                END;

                CREATE TRIGGER IF NOT EXISTS prompts_ad AFTER DELETE ON prompts BEGIN
                    INSERT INTO prompts_fts(prompts_fts, rowid, id, name, tags, description, template)
                    VALUES ('delete', old.rowid, old.id, old.name, old.tags, old.description, old.template);
                END;

                CREATE TRIGGER IF NOT EXISTS prompts_au AFTER UPDATE ON prompts BEGIN
                    INSERT INTO prompts_fts(prompts_fts, rowid, id, name, tags, description, template)
                    VALUES ('delete', old.rowid, old.id, old.name, old.tags, old.description, old.template);
                    INSERT INTO prompts_fts(rowid, id, name, tags, description, template)
                    VALUES (new.rowid, new.id, new.name, new.tags, new.description, new.template);
                END;
                """
            )
        logger.debug("SQLiteBackend initialized at {}", self._path)

    def upsert(self, prompt: PromptConfig) -> None:
        """Insert or replace a prompt.

        Args:
            prompt: The prompt configuration to store.

        Examples:
            >>> backend = SQLiteBackend(":memory:")
            >>> backend.init()
            >>> p = PromptConfig(id="x", name="X", schema={}, template="t")
            >>> backend.upsert(p)
        """
        now = int(time.time())
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT created_at FROM prompts WHERE id = ?", (prompt.id,)
            ).fetchone()
            created_at = existing["created_at"] if existing else now

            conn.execute(
                """
                INSERT INTO prompts (id, name, tags, schema_json, template, description, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name        = excluded.name,
                    tags        = excluded.tags,
                    schema_json = excluded.schema_json,
                    template    = excluded.template,
                    description = excluded.description,
                    updated_at  = excluded.updated_at
                """,
                (
                    prompt.id,
                    prompt.name,
                    json.dumps(prompt.tags),
                    json.dumps(prompt.schema_),
                    prompt.template,
                    prompt.description,
                    created_at,
                    now,
                ),
            )
        logger.debug("Upserted prompt '{}'", prompt.id)

    def get(self, prompt_id: str) -> PromptConfig | None:
        """Fetch a single prompt by ID.

        Args:
            prompt_id: The unique prompt identifier.

        Returns:
            PromptConfig if found, None otherwise.

        Examples:
            >>> backend = SQLiteBackend(":memory:")
            >>> backend.init()
            >>> backend.get("missing") is None
            True
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM prompts WHERE id = ?", (prompt_id,)
            ).fetchone()
        return _row_to_prompt(row) if row else None

    def delete(self, prompt_id: str) -> bool:
        """Delete a prompt by ID.

        Args:
            prompt_id: The unique prompt identifier.

        Returns:
            True if a row was deleted, False if not found.

        Examples:
            >>> backend = SQLiteBackend(":memory:")
            >>> backend.init()
            >>> backend.delete("missing")
            False
        """
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM prompts WHERE id = ?", (prompt_id,))
        deleted = cur.rowcount > 0
        if deleted:
            logger.debug("Deleted prompt '{}'", prompt_id)
        return deleted

    def list_all(self) -> list[PromptConfig]:
        """Return all stored prompts ordered by updated_at DESC.

        Returns:
            List of all PromptConfig objects.

        Examples:
            >>> backend = SQLiteBackend(":memory:")
            >>> backend.init()
            >>> backend.list_all()
            []
        """
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM prompts ORDER BY updated_at DESC"
            ).fetchall()
        return [_row_to_prompt(r) for r in rows]

    def search_fts(self, query: str, limit: int = 5) -> list[tuple[str, float]]:
        """Full-text search using FTS5 BM25 ranking.

        Args:
            query: FTS5 query string (supports boolean operators and phrases).
            limit: Maximum results to return.

        Returns:
            List of (prompt_id, score) tuples ordered by relevance.
            Score is negated BM25 rank (higher = more relevant).

        Examples:
            >>> backend = SQLiteBackend(":memory:")
            >>> backend.init()
            >>> backend.search_fts("sales")
            []
        """
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, rank
                FROM prompts_fts
                WHERE prompts_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (query, limit),
            ).fetchall()
        return [(r["id"], -r["rank"]) for r in rows]


assert isinstance(SQLiteBackend(), StorageBackend), "SQLiteBackend must satisfy StorageBackend protocol"
