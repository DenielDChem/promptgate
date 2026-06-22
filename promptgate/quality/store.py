"""Persistence for deep validation runs + the per-prompt quality rollup (P3)."""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from promptgate.quality.deep import RunResult, grade


def _connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


class QualityStore:
    """Stores validation runs/cases and maintains a running quality rollup."""

    def __init__(self, db_path: str | Path) -> None:
        self._path = db_path

    def save_run(self, prompt_id: str, version_no: int | None, model_id: str,
                 run: RunResult, created_by: int | None) -> int:
        now = int(time.time())
        with _connect(self._path) as c:
            cur = c.execute(
                "INSERT INTO validation_runs "
                "(prompt_id, version_no, model_id, determinism, comprehension, "
                " hallucination, latency_ms, n_cases, color, created_by, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (prompt_id, version_no, model_id, run.determinism, run.comprehension,
                 run.hallucination, run.latency_ms, run.n_cases, run.color, created_by, now),
            )
            run_id = cur.lastrowid
            c.executemany(
                "INSERT INTO validation_cases "
                "(run_id, question, answer, score, hallucination, flagged_block) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                [(run_id, cr.question, cr.answer, cr.score, cr.hallucination, cr.flagged_block)
                 for cr in run.cases],
            )
            self._rollup(c, prompt_id, version_no, run, now)
        return run_id

    @staticmethod
    def _rollup(c: sqlite3.Connection, prompt_id: str, version_no: int | None,
                run: RunResult, now: int) -> None:
        """Update quality_scores as a running mean across all runs."""
        prev = c.execute(
            "SELECT * FROM quality_scores WHERE prompt_id=?", (prompt_id,)
        ).fetchone()
        if prev is None:
            n = 1
            avg_score, comprehension = run.comprehension, run.comprehension
            determinism, hallucination = run.determinism, run.hallucination
        else:
            n = prev["n_validations"] + 1
            def mean(old, new):
                return (old * prev["n_validations"] + new) / n
            comprehension = mean(prev["comprehension"], run.comprehension)
            avg_score = comprehension
            determinism = mean(prev["determinism"], run.determinism)
            hallucination = mean(prev["hallucination"], run.hallucination)
        color = grade(comprehension, hallucination)
        c.execute(
            "INSERT INTO quality_scores "
            "(prompt_id, version_no, avg_score, comprehension, determinism, "
            " hallucination, n_validations, color, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(prompt_id) DO UPDATE SET "
            " version_no=excluded.version_no, avg_score=excluded.avg_score, "
            " comprehension=excluded.comprehension, determinism=excluded.determinism, "
            " hallucination=excluded.hallucination, n_validations=excluded.n_validations, "
            " color=excluded.color, updated_at=excluded.updated_at",
            (prompt_id, version_no, round(avg_score, 2), round(comprehension, 2),
             round(determinism, 1), round(hallucination, 2), n, color, now),
        )

    def get_quality(self, prompt_id: str) -> dict | None:
        with _connect(self._path) as c:
            row = c.execute(
                "SELECT * FROM quality_scores WHERE prompt_id=?", (prompt_id,)
            ).fetchone()
            return dict(row) if row else None

    def list_runs(self, prompt_id: str) -> list[dict]:
        with _connect(self._path) as c:
            rows = c.execute(
                "SELECT id AS run_id, model_id, determinism, comprehension, hallucination, "
                "latency_ms, n_cases, color, created_at "
                "FROM validation_runs WHERE prompt_id=? ORDER BY id DESC",
                (prompt_id,),
            )
            return [dict(r) for r in rows]

    def get_run(self, run_id: int) -> dict | None:
        with _connect(self._path) as c:
            run = c.execute("SELECT * FROM validation_runs WHERE id=?", (run_id,)).fetchone()
            if run is None:
                return None
            cases = c.execute(
                "SELECT question, answer, score, hallucination, flagged_block "
                "FROM validation_cases WHERE run_id=? ORDER BY id", (run_id,),
            )
            d = dict(run)
            d["run_id"] = d.pop("id")
            d["cases"] = [dict(r) for r in cases]
            return d

    def dashboard(self) -> list[dict]:
        with _connect(self._path) as c:
            rows = c.execute(
                "SELECT prompt_id, avg_score, comprehension, determinism, hallucination, "
                "n_validations, color, updated_at FROM quality_scores ORDER BY updated_at DESC"
            )
            return [dict(r) for r in rows]

    def run_owner_prompt(self, run_id: int) -> str | None:
        """The prompt_id a run belongs to (for authorizing run-detail access)."""
        with _connect(self._path) as c:
            row = c.execute("SELECT prompt_id FROM validation_runs WHERE id=?", (run_id,)).fetchone()
            return row["prompt_id"] if row else None
