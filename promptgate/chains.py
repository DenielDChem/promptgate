"""Prompt chains: pipe output of one prompt into the next."""
from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

import yaml
from loguru import logger
from pydantic import BaseModel, Field

from promptgate.storage import _DEFAULT_DB_PATH


class ChainStep(BaseModel):
    """Single step in a prompt chain.

    Attributes:
        prompt_id: ID of the prompt to run.
        model: LiteLLM model string for this step.
        input_map: Maps accumulated-context keys → this step's payload keys.
            Empty dict means pass full context as payload.
        output_as: Key under which this step's output is stored in context.
            None merges output directly into context root.
    """

    prompt_id: str
    model: str
    input_map: dict[str, str] = Field(default_factory=dict)
    output_as: str | None = None


class ChainConfig(BaseModel):
    """Full chain definition.

    Attributes:
        id: Unique chain identifier.
        name: Human-readable name.
        steps: Ordered list of ChainStep.
        description: Optional description.
    """

    id: str
    name: str
    steps: list[ChainStep]
    description: str = ""


@dataclass
class ChainResult:
    """Result of a full chain run.

    Attributes:
        ok: True if all steps completed and validated.
        context: Accumulated data from all steps plus initial payload.
        failed_step: 0-based index of first failed step, or None.
        steps_run: Count of steps executed (including failed).
    """

    ok: bool
    context: dict
    failed_step: int | None
    steps_run: int


def _ensure_chains_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS chains (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            steps_json  TEXT NOT NULL DEFAULT '[]',
            description TEXT NOT NULL DEFAULT '',
            created_at  INTEGER NOT NULL,
            updated_at  INTEGER NOT NULL
        )
        """
    )


def upsert_chain(chain: ChainConfig, db_path: str | Path = _DEFAULT_DB_PATH) -> None:
    """Store or update a chain definition.

    Args:
        chain: ChainConfig to store.
        db_path: Path to SQLite database.

    Examples:
        >>> # Requires DB — see tests/test_chains.py
    """
    now = int(time.time())
    with sqlite3.connect(db_path) as conn:
        _ensure_chains_table(conn)
        existing = conn.execute("SELECT created_at FROM chains WHERE id=?", (chain.id,)).fetchone()
        created_at = existing[0] if existing else now
        conn.execute(
            """
            INSERT INTO chains (id, name, steps_json, description, created_at, updated_at)
            VALUES (?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name, steps_json=excluded.steps_json,
                description=excluded.description, updated_at=excluded.updated_at
            """,
            (chain.id, chain.name,
             json.dumps([s.model_dump() for s in chain.steps]),
             chain.description, created_at, now),
        )
    logger.debug("Upserted chain '{}'", chain.id)


def get_chain(chain_id: str, db_path: str | Path = _DEFAULT_DB_PATH) -> ChainConfig | None:
    """Fetch a chain by ID.

    Args:
        chain_id: Unique chain identifier.
        db_path: Path to SQLite database.

    Returns:
        ChainConfig if found, None otherwise.

    Examples:
        >>> # Requires DB
    """
    with sqlite3.connect(db_path) as conn:
        _ensure_chains_table(conn)
        row = conn.execute(
            "SELECT id,name,steps_json,description FROM chains WHERE id=?", (chain_id,)
        ).fetchone()
    if not row:
        return None
    return ChainConfig(
        id=row[0], name=row[1],
        steps=[ChainStep.model_validate(s) for s in json.loads(row[2])],
        description=row[3],
    )


def delete_chain(chain_id: str, db_path: str | Path = _DEFAULT_DB_PATH) -> bool:
    """Delete a chain by ID.

    Args:
        chain_id: Unique chain identifier.
        db_path: Path to SQLite database.

    Returns:
        True if deleted, False if not found.

    Examples:
        >>> # Requires DB
    """
    with sqlite3.connect(db_path) as conn:
        _ensure_chains_table(conn)
        cur = conn.execute("DELETE FROM chains WHERE id=?", (chain_id,))
    return cur.rowcount > 0


def list_chains(db_path: str | Path = _DEFAULT_DB_PATH) -> list[ChainConfig]:
    """List all stored chains ordered by updated_at DESC.

    Args:
        db_path: Path to SQLite database.

    Returns:
        List of ChainConfig objects.

    Examples:
        >>> # Requires DB
    """
    with sqlite3.connect(db_path) as conn:
        _ensure_chains_table(conn)
        rows = conn.execute(
            "SELECT id,name,steps_json,description FROM chains ORDER BY updated_at DESC"
        ).fetchall()
    return [
        ChainConfig(
            id=r[0], name=r[1],
            steps=[ChainStep.model_validate(s) for s in json.loads(r[2])],
            description=r[3],
        )
        for r in rows
    ]


def load_chain_from_yaml(path: str | Path) -> ChainConfig:
    """Parse a ChainConfig from a YAML file.

    Args:
        path: Path to ``.yaml`` chain definition file.

    Returns:
        Parsed ChainConfig.

    Examples:
        >>> # Requires a valid YAML file
    """
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return ChainConfig.model_validate(data)


def run_chain(
    chain_id: str,
    initial_payload: dict,
    *,
    db_path: str | Path = _DEFAULT_DB_PATH,
    max_retries_per_step: int = 3,
    litellm_kwargs: dict | None = None,
) -> ChainResult:
    """Execute a chain, piping each step's output into the next.

    Context starts as ``initial_payload``. After each step:
    - If ``output_as`` is set: result stored under ``context[output_as]``.
    - Otherwise: result dict merged directly into context root.
    Each step's payload is built by applying ``input_map`` over current context.
    Empty ``input_map`` → full context passed as payload.

    Args:
        chain_id: ID of the chain to run.
        initial_payload: Seed data for the first step.
        db_path: Path to SQLite database.
        max_retries_per_step: LLM retry budget per step.
        litellm_kwargs: Extra kwargs forwarded to all litellm calls.

    Returns:
        ChainResult with accumulated context and success flag.

    Raises:
        KeyError: If chain_id or a step's prompt_id is not found.
        ImportError: If litellm is not installed.

    Examples:
        >>> # Requires live LLM — not suitable for doctest
    """
    from promptgate.runner import run as pg_run

    chain = get_chain(chain_id, db_path)
    if chain is None:
        raise KeyError(f"Chain '{chain_id}' not found")

    context: dict = dict(initial_payload)

    for idx, step in enumerate(chain.steps):
        if step.input_map:
            payload = {tgt: context[src] for tgt, src in step.input_map.items() if src in context}
        else:
            payload = dict(context)

        logger.info(
            "Chain '{}' step {}/{}: prompt={} model={}",
            chain_id, idx + 1, len(chain.steps), step.prompt_id, step.model,
        )
        result = pg_run(
            step.prompt_id, payload, step.model,
            db_path=db_path, max_retries=max_retries_per_step,
            litellm_kwargs=litellm_kwargs,
        )

        if not result.ok:
            logger.error("Chain '{}' failed at step {} (prompt={})", chain_id, idx, step.prompt_id)
            return ChainResult(ok=False, context=context, failed_step=idx, steps_run=idx + 1)

        if step.output_as:
            context[step.output_as] = result.data
        else:
            context.update(result.data or {})

    return ChainResult(ok=True, context=context, failed_step=None, steps_run=len(chain.steps))
