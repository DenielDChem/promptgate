"""Ownership + versioning for prompts (P2).

Lives in side tables (``prompt_meta``, ``prompt_versions`` from migration 0002)
keyed by ``prompt_id``, so the prompts/FTS schema owned by
:class:`promptgate.storage.SQLiteBackend` is untouched. Endpoints coordinate:
this module records versions and authorizes access; the backend stores the
actual prompt content.

Ownership rules:
- admin: full access to every prompt.
- otherwise: a prompt is readable/writable if its owner is the caller, or it has
  no owner yet (legacy/unclaimed). A prompt with no meta row at all is treated
  as legacy (readable; first save through the new path claims it).
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path


def _connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _is_admin(user: dict) -> bool:
    return user.get("role") == "admin"


class PromptMetaStore:
    """Owner + version bookkeeping for prompts."""

    def __init__(self, db_path: str | Path) -> None:
        self._path = db_path

    # ── meta ────────────────────────────────────────────────────────────────
    def get_meta(self, prompt_id: str) -> dict | None:
        with _connect(self._path) as c:
            row = c.execute("SELECT * FROM prompt_meta WHERE prompt_id=?", (prompt_id,)).fetchone()
            return dict(row) if row else None

    def can_read(self, prompt_id: str, user: dict) -> bool:
        if _is_admin(user):
            return True
        meta = self.get_meta(prompt_id)
        if meta is None:
            return True  # legacy/unclaimed
        return meta["owner_id"] in (None, user["id"])

    def can_write(self, prompt_id: str, user: dict) -> bool:
        if _is_admin(user):
            return True
        meta = self.get_meta(prompt_id)
        if meta is None:
            return True  # creating new or claiming an unclaimed prompt
        return meta["owner_id"] in (None, user["id"])

    def set_status(self, prompt_id: str, status: str) -> None:
        with _connect(self._path) as c:
            c.execute(
                "UPDATE prompt_meta SET status=?, updated_at=? WHERE prompt_id=?",
                (status, int(time.time()), prompt_id),
            )

    # ── versions ──────────────────────────────────────────────────────────────
    def record_version(self, prompt_id: str, body: dict, author_id: int | None,
                        message: str = "") -> int:
        """Append a version snapshot, creating/bumping meta. Returns version_no."""
        now = int(time.time())
        body_json = json.dumps(body, ensure_ascii=False, sort_keys=True)
        with _connect(self._path) as c:
            meta = c.execute(
                "SELECT * FROM prompt_meta WHERE prompt_id=?", (prompt_id,)
            ).fetchone()
            if meta is None:
                version_no = 1
                c.execute(
                    "INSERT INTO prompt_meta "
                    "(prompt_id, owner_id, status, current_version, created_at, updated_at) "
                    "VALUES (?, ?, 'draft', 1, ?, ?)",
                    (prompt_id, author_id, now, now),
                )
            else:
                # Bump the version only — NEVER silently reassign ownership on
                # update. Auto-claiming would let any writer permanently hijack an
                # unclaimed/legacy prompt. Ownership is set once, at creation.
                version_no = meta["current_version"] + 1
                c.execute(
                    "UPDATE prompt_meta SET current_version=?, updated_at=? WHERE prompt_id=?",
                    (version_no, now, prompt_id),
                )
            c.execute(
                "INSERT INTO prompt_versions "
                "(prompt_id, version_no, body_json, author_id, message, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (prompt_id, version_no, body_json, author_id, message, now),
            )
        return version_no

    def list_versions(self, prompt_id: str) -> list[dict]:
        with _connect(self._path) as c:
            rows = c.execute(
                "SELECT version_no, author_id, message, created_at "
                "FROM prompt_versions WHERE prompt_id=? ORDER BY version_no DESC",
                (prompt_id,),
            )
            return [dict(r) for r in rows]

    def get_version(self, prompt_id: str, version_no: int) -> dict | None:
        with _connect(self._path) as c:
            row = c.execute(
                "SELECT * FROM prompt_versions WHERE prompt_id=? AND version_no=?",
                (prompt_id, version_no),
            ).fetchone()
        if row is None:
            return None
        return {
            "version_no": row["version_no"],
            "author_id": row["author_id"],
            "message": row["message"],
            "created_at": row["created_at"],
            "body": json.loads(row["body_json"]),
        }

    def delete_all(self, prompt_id: str) -> None:
        """Drop meta + versions when a prompt is deleted."""
        with _connect(self._path) as c:
            c.execute("DELETE FROM prompt_versions WHERE prompt_id=?", (prompt_id,))
            c.execute("DELETE FROM prompt_meta WHERE prompt_id=?", (prompt_id,))
