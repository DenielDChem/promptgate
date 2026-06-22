"""Job persistence + atomic claim for the task queue (P4)."""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

_PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}
_ACTIVE = ("queued", "running")


def _connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _summary(row: sqlite3.Row) -> dict:
    """Job fields safe/cheap for list views (no params/result blobs)."""
    return {
        "id": row["id"], "type": row["type"], "status": row["status"],
        "priority": row["priority"], "prompt_id": row["prompt_id"],
        "model_id": row["model_id"], "progress": row["progress"], "total": row["total"],
        "created_at": row["created_at"], "updated_at": row["updated_at"],
    }


class JobStore:
    def __init__(self, db_path: str | Path) -> None:
        self._path = db_path

    def create(self, job_type: str, prompt_id: str | None = None, model_id: str | None = None,
               params: dict | None = None, priority: str = "medium",
               created_by: int | None = None) -> dict:
        now = int(time.time())
        with _connect(self._path) as c:
            cur = c.execute(
                "INSERT INTO jobs (type, status, priority, prompt_id, model_id, params_json, "
                "created_by, created_at, updated_at) VALUES (?, 'queued', ?, ?, ?, ?, ?, ?, ?)",
                (job_type, priority, prompt_id, model_id,
                 json.dumps(params or {}), created_by, now, now),
            )
            row = c.execute("SELECT * FROM jobs WHERE id=?", (cur.lastrowid,)).fetchone()
        return _summary(row)

    def claim_next(self) -> dict | None:
        """Atomically move the highest-priority oldest queued job to running."""
        now = int(time.time())
        with _connect(self._path) as c:
            row = c.execute(
                "SELECT id FROM jobs WHERE status='queued' "
                "ORDER BY CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, id "
                "LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            cur = c.execute(
                "UPDATE jobs SET status='running', updated_at=? WHERE id=? AND status='queued'",
                (now, row["id"]),
            )
            if cur.rowcount != 1:
                return None  # lost race to another worker
            claimed = c.execute("SELECT * FROM jobs WHERE id=?", (row["id"],)).fetchone()
        return self.get(claimed["id"])

    def update_progress(self, job_id: int, progress: int, total: int | None = None) -> None:
        with _connect(self._path) as c:
            if total is None:
                c.execute("UPDATE jobs SET progress=?, updated_at=? WHERE id=?",
                          (progress, int(time.time()), job_id))
            else:
                c.execute("UPDATE jobs SET progress=?, total=?, updated_at=? WHERE id=?",
                          (progress, total, int(time.time()), job_id))

    def complete(self, job_id: int, result: dict) -> None:
        with _connect(self._path) as c:
            c.execute(
                "UPDATE jobs SET status='completed', result_json=?, updated_at=? WHERE id=?",
                (json.dumps(result or {}), int(time.time()), job_id),
            )

    def fail(self, job_id: int, error: str) -> None:
        with _connect(self._path) as c:
            c.execute("UPDATE jobs SET status='failed', error=?, updated_at=? WHERE id=?",
                      (error[:2000], int(time.time()), job_id))

    def finalize_cancelled(self, job_id: int) -> None:
        with _connect(self._path) as c:
            c.execute("UPDATE jobs SET status='cancelled', updated_at=? WHERE id=?",
                      (int(time.time()), job_id))

    def request_cancel(self, job_id: int) -> str | None:
        """Cancel a queued job immediately; flag a running job for cooperative stop.

        Returns the resulting status, or None if the job is missing / already done.
        """
        now = int(time.time())
        with _connect(self._path) as c:
            row = c.execute("SELECT status FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row is None:
                return None
            status = row["status"]
            if status == "queued":
                c.execute("UPDATE jobs SET status='cancelled', updated_at=? WHERE id=?", (now, job_id))
                return "cancelled"
            if status == "running":
                c.execute("UPDATE jobs SET cancel_requested=1, updated_at=? WHERE id=?", (now, job_id))
                return "running"  # handler will stop and finalize as cancelled
            return None  # completed/failed/cancelled — nothing to do

    def is_cancel_requested(self, job_id: int) -> bool:
        with _connect(self._path) as c:
            row = c.execute("SELECT cancel_requested FROM jobs WHERE id=?", (job_id,)).fetchone()
            return bool(row and row["cancel_requested"])

    def get(self, job_id: int) -> dict | None:
        with _connect(self._path) as c:
            row = c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            return None
        d = _summary(row)
        d["created_by"] = row["created_by"]
        d["params"] = json.loads(row["params_json"] or "{}")
        d["result"] = json.loads(row["result_json"]) if row["result_json"] else None
        d["error"] = row["error"]
        return d

    def list(self, status: str | None = None) -> list[dict]:
        with _connect(self._path) as c:
            if status:
                rows = c.execute("SELECT * FROM jobs WHERE status=? ORDER BY id DESC", (status,))
            else:
                rows = c.execute("SELECT * FROM jobs ORDER BY id DESC")
            return [_summary(r) for r in rows]

    def summary(self) -> dict:
        out = {"queued": 0, "running": 0, "completed": 0, "failed": 0, "cancelled": 0, "total": 0}
        with _connect(self._path) as c:
            for status, n in c.execute("SELECT status, COUNT(*) FROM jobs GROUP BY status"):
                out[status] = n
                out["total"] += n
        return out
