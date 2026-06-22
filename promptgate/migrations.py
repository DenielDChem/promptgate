"""Lightweight forward-only SQL migration runner (SQLite).

Migrations are ``(id, sql)`` pairs applied in order and recorded in a
``schema_migrations`` table so each runs exactly once. Forward-only: there
are no down-migrations by design (snapshot the DB before destructive change).
"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from loguru import logger

# Ordered, append-only. NEVER edit a shipped migration's SQL — add a new one.
_MIGRATIONS: list[tuple[str, str]] = [
    (
        "0001_auth",
        """
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            username    TEXT    NOT NULL UNIQUE,
            email       TEXT    NOT NULL UNIQUE,
            pw_hash     TEXT    NOT NULL,
            role        TEXT    NOT NULL DEFAULT 'guest',
            totp_secret TEXT,
            status      TEXT    NOT NULL DEFAULT 'active',   -- active|disabled
            created_at  INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS invites (
            token       TEXT    PRIMARY KEY,
            role        TEXT    NOT NULL,
            expires_at  INTEGER,                              -- NULL = never expires
            one_time    INTEGER NOT NULL DEFAULT 1,
            used_by     INTEGER REFERENCES users(id),
            used_at     INTEGER,
            created_by  INTEGER REFERENCES users(id),
            created_at  INTEGER NOT NULL,
            status      TEXT    NOT NULL DEFAULT 'active'      -- active|used|revoked
        );

        CREATE TABLE IF NOT EXISTS registration_requests (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            email       TEXT    NOT NULL,
            reason      TEXT    NOT NULL DEFAULT '',
            status      TEXT    NOT NULL DEFAULT 'pending',    -- pending|approved|rejected
            created_at  INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ts          INTEGER NOT NULL,
            event       TEXT    NOT NULL,
            user_id     INTEGER,
            ip          TEXT,
            detail      TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_audit_ts        ON audit_log(ts);
        CREATE INDEX IF NOT EXISTS idx_regreq_status   ON registration_requests(status);
        CREATE INDEX IF NOT EXISTS idx_invites_status  ON invites(status);
        """,
    ),
    (
        "0002_prompt_meta_versions",
        # Ownership + versioning live in side tables keyed by prompt_id, so the
        # prompts/FTS schema owned by storage.SQLiteBackend is left untouched.
        """
        CREATE TABLE IF NOT EXISTS prompt_meta (
            prompt_id       TEXT    PRIMARY KEY,
            owner_id        INTEGER,                          -- NULL = legacy/shared
            status          TEXT    NOT NULL DEFAULT 'draft',  -- draft|published
            current_version INTEGER NOT NULL DEFAULT 1,
            created_at      INTEGER NOT NULL,
            updated_at      INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS prompt_versions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            prompt_id   TEXT    NOT NULL,
            version_no  INTEGER NOT NULL,
            body_json   TEXT    NOT NULL,                      -- full PromptConfig snapshot
            author_id   INTEGER,
            message     TEXT    NOT NULL DEFAULT '',
            created_at  INTEGER NOT NULL,
            UNIQUE (prompt_id, version_no)
        );

        CREATE INDEX IF NOT EXISTS idx_pv_prompt ON prompt_versions(prompt_id);
        CREATE INDEX IF NOT EXISTS idx_pm_owner  ON prompt_meta(owner_id);
        """,
    ),
    (
        "0003_validation_quality",
        # P3: deep (LLM-backed) validation runs + per-case detail + a latest-
        # quality rollup per prompt. Metrics: determinism 0-100, comprehension
        # 0-10 (higher better), hallucination 0-10 (lower better), latency ms.
        """
        CREATE TABLE IF NOT EXISTS validation_runs (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            prompt_id     TEXT    NOT NULL,
            version_no    INTEGER,
            model_id      TEXT    NOT NULL,
            determinism   REAL,
            comprehension REAL,
            hallucination REAL,
            latency_ms    INTEGER,
            n_cases       INTEGER NOT NULL DEFAULT 0,
            color         TEXT,
            created_by    INTEGER,
            created_at    INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS validation_cases (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id        INTEGER NOT NULL REFERENCES validation_runs(id) ON DELETE CASCADE,
            question      TEXT    NOT NULL,
            answer        TEXT,
            score         REAL,
            hallucination REAL,
            flagged_block TEXT
        );

        CREATE TABLE IF NOT EXISTS quality_scores (
            prompt_id      TEXT    PRIMARY KEY,
            version_no     INTEGER,
            avg_score      REAL,
            comprehension  REAL,
            determinism    REAL,
            hallucination  REAL,
            n_validations  INTEGER NOT NULL DEFAULT 0,
            color          TEXT,
            updated_at     INTEGER NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_vr_prompt ON validation_runs(prompt_id);
        CREATE INDEX IF NOT EXISTS idx_vc_run    ON validation_cases(run_id);
        """,
    ),
]


def run_migrations(db_path: str | Path) -> list[str]:
    """Apply any pending migrations to ``db_path``. Returns the ids applied.

    Idempotent: already-applied migrations are skipped.

    Examples:
        >>> import tempfile, os
        >>> p = os.path.join(tempfile.mkdtemp(), "m.sqlite")
        >>> run_migrations(p)
        ['0001_auth']
        >>> run_migrations(p)   # second run is a no-op
        []
    """
    path = Path(db_path)
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)

    applied: list[str] = []
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(id TEXT PRIMARY KEY, applied_at INTEGER NOT NULL)"
        )
        done = {row[0] for row in conn.execute("SELECT id FROM schema_migrations")}
        for mid, sql in _MIGRATIONS:
            if mid in done:
                continue
            conn.executescript(sql)
            conn.execute(
                "INSERT INTO schema_migrations (id, applied_at) VALUES (?, ?)",
                (mid, int(time.time())),
            )
            conn.commit()
            applied.append(mid)
            logger.info("Applied migration {}", mid)
    finally:
        conn.close()
    return applied
