"""In-process job worker.

``run_one`` executes a single claimed job against a handler registry and is the
unit of work for both the background thread (:class:`JobWorker`) and the
synchronous test helper (:func:`drain`). Handlers receive ``(job, store)`` and
should update progress via the store, poll ``store.is_cancel_requested(id)``,
and return a result dict (or raise :class:`JobCancelled`).
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable

from loguru import logger

from promptgate.jobs.store import JobStore

# handler(job: dict, store: JobStore) -> dict
Handler = Callable[[dict, JobStore], dict]
HandlerRegistry = "dict[str, Handler]"


class JobCancelled(Exception):
    """Raised by a handler when it observes a cancel request and stops."""


def run_one(store: JobStore, handlers: dict, job: dict) -> None:
    """Execute one already-claimed (running) job; record terminal state."""
    handler = handlers.get(job["type"])
    if handler is None:
        store.fail(job["id"], f"No handler registered for job type '{job['type']}'")
        return
    try:
        result = handler(job, store)
        if store.is_cancel_requested(job["id"]):
            store.finalize_cancelled(job["id"])
        else:
            store.complete(job["id"], result or {})
    except JobCancelled:
        store.finalize_cancelled(job["id"])
    except Exception as exc:  # noqa: BLE001 — any handler failure → failed job
        logger.exception("Job {} failed", job["id"])
        store.fail(job["id"], str(exc))


def drain(store: JobStore, handlers: dict, max_jobs: int = 1000) -> int:
    """Synchronously claim & run all currently-queued jobs. Returns count run.

    Used by tests and one-shot CLI processing — no thread involved.
    """
    n = 0
    while n < max_jobs:
        job = store.claim_next()
        if job is None:
            break
        run_one(store, handlers, job)
        n += 1
    return n


class JobWorker(threading.Thread):
    """Background daemon thread that polls for and runs queued jobs."""

    def __init__(self, db_path: str | Path, handlers: dict, poll_interval: float = 0.5) -> None:
        super().__init__(name="pgate-job-worker", daemon=True)
        self._db_path = db_path
        self._handlers = handlers
        self._poll = poll_interval
        self._stop = threading.Event()

    def run(self) -> None:
        store = JobStore(self._db_path)
        logger.info("Job worker started")
        while not self._stop.is_set():
            try:
                job = store.claim_next()
            except Exception:  # noqa: BLE001 — never let the loop die
                logger.exception("claim_next failed")
                job = None
            if job is None:
                self._stop.wait(self._poll)
                continue
            run_one(store, self._handlers, job)

    def stop(self) -> None:
        self._stop.set()
