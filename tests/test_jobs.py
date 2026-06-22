"""P4 task-queue tests: JobStore, worker (run_one/drain), and the admin API."""
from __future__ import annotations

import pytest

from promptgate.jobs.store import JobStore
from promptgate.jobs.worker import JobCancelled, drain, run_one
from promptgate.migrations import run_migrations


@pytest.fixture()
def store(tmp_path):
    db = tmp_path / "jobs.sqlite"
    run_migrations(db)
    return JobStore(db)


# ── JobStore ──────────────────────────────────────────────────────────────────
def test_create_and_get(store):
    job = store.create("validation", prompt_id="p1", model_id="m", params={"cases": [1]})
    assert job["status"] == "queued" and job["type"] == "validation"
    full = store.get(job["id"])
    assert full["params"] == {"cases": [1]} and full["result"] is None


def test_claim_orders_by_priority_then_age(store):
    low = store.create("validation", priority="low")
    high = store.create("validation", priority="high")
    med = store.create("validation", priority="medium")
    assert store.claim_next()["id"] == high["id"]
    assert store.claim_next()["id"] == med["id"]
    assert store.claim_next()["id"] == low["id"]
    assert store.claim_next() is None


def test_claim_marks_running_once(store):
    j = store.create("validation")
    claimed = store.claim_next()
    assert claimed["id"] == j["id"] and claimed["status"] == "running"
    assert store.claim_next() is None  # not re-claimable


def test_progress_complete_fail(store):
    j = store.create("validation")
    store.claim_next()
    store.update_progress(j["id"], 3, 5)
    assert store.get(j["id"])["progress"] == 3
    store.complete(j["id"], {"ok": True})
    assert store.get(j["id"])["status"] == "completed"
    assert store.get(j["id"])["result"] == {"ok": True}

    k = store.create("validation")
    store.claim_next()
    store.fail(k["id"], "boom")
    assert store.get(k["id"])["status"] == "failed"
    assert store.get(k["id"])["error"] == "boom"


def test_cancel_queued_vs_running(store):
    q = store.create("validation")
    assert store.request_cancel(q["id"]) == "cancelled"
    assert store.get(q["id"])["status"] == "cancelled"

    r = store.create("validation")
    store.claim_next()
    assert store.request_cancel(r["id"]) == "running"
    assert store.is_cancel_requested(r["id"]) is True

    assert store.request_cancel(99999) is None


def test_summary(store):
    store.create("validation")
    store.create("validation")
    store.claim_next()
    s = store.summary()
    assert s["queued"] == 1 and s["running"] == 1 and s["total"] == 2


# ── worker ────────────────────────────────────────────────────────────────────
def _ok_handlers():
    def h(job, st):
        st.update_progress(job["id"], 1, 1)
        return {"did": job["type"]}
    return {"validation": h, "mass_test": h}


def test_drain_runs_queued_jobs(store):
    store.create("validation")
    store.create("mass_test")
    assert drain(store, _ok_handlers()) == 2
    assert store.summary()["completed"] == 2


def test_handler_exception_fails_job(store):
    def boom(job, st):
        raise RuntimeError("nope")
    j = store.create("validation")
    assert drain(store, {"validation": boom}) == 1
    assert store.get(j["id"])["status"] == "failed"
    assert "nope" in store.get(j["id"])["error"]


def test_missing_handler_fails_job(store):
    j = store.create("unknown_type")
    drain(store, _ok_handlers())
    assert store.get(j["id"])["status"] == "failed"


def test_cooperative_cancel_in_handler(store):
    def cancellable(job, st):
        if st.is_cancel_requested(job["id"]):
            raise JobCancelled
        return {}
    j = store.create("validation")
    claimed = store.claim_next()
    store.request_cancel(j["id"])          # flag while running
    run_one(store, {"validation": cancellable}, claimed)
    assert store.get(j["id"])["status"] == "cancelled"


# ── API ───────────────────────────────────────────────────────────────────────
fastapi = pytest.importorskip("fastapi", reason="fastapi not installed")
pytest.importorskip("jwt", reason="PyJWT not installed")
from fastapi.testclient import TestClient  # noqa: E402

from promptgate.api import make_app  # noqa: E402
from promptgate.auth.db import AuthDB  # noqa: E402
from promptgate.auth.security import create_access_token  # noqa: E402


def _client(app, db, username, role):
    c = TestClient(app)
    u = AuthDB(db).create_user(username, f"{username}@x.io", "passpass1", role)
    c.headers.update({"Authorization": f"Bearer {create_access_token(sub=u['id'], role=role)}"})
    return c


def test_queue_api_admin_flow(tmp_path):
    db = tmp_path / "app.sqlite"
    app = make_app(db)
    admin = _client(app, db, "boss", "admin")
    r = admin.post("/api/jobs", json={"type": "validation", "prompt_id": "p1",
                                      "model_id": "m", "priority": "high"})
    assert r.status_code == 201
    job_id = r.json()["id"]
    assert admin.get("/api/jobs/summary").json()["queued"] == 1
    assert any(j["id"] == job_id for j in admin.get("/api/jobs").json())

    # process synchronously with a fake handler against the same DB
    drain(JobStore(db), _ok_handlers())
    assert admin.get(f"/api/jobs/{job_id}").json()["status"] == "completed"


def test_queue_api_admin_only(tmp_path):
    db = tmp_path / "app.sqlite"
    app = make_app(db)
    prompter = _client(app, db, "alex", "prompter")
    assert prompter.post("/api/jobs", json={"type": "validation"}).status_code == 403
    assert prompter.get("/api/jobs").status_code == 403


def test_queue_api_cancel(tmp_path):
    db = tmp_path / "app.sqlite"
    app = make_app(db)
    admin = _client(app, db, "boss", "admin")
    jid = admin.post("/api/jobs", json={"type": "validation"}).json()["id"]
    assert admin.post(f"/api/jobs/{jid}/cancel").json()["status"] == "cancelled"


def test_queue_api_rejects_bad_type(tmp_path):
    db = tmp_path / "app.sqlite"
    app = make_app(db)
    admin = _client(app, db, "boss", "admin")
    assert admin.post("/api/jobs", json={"type": "nope"}).status_code == 422
