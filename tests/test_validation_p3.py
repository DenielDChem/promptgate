"""P3 API tests: deep validation run + quality rollup + dashboard scoping.

Scorers are monkeypatched so no litellm/model calls happen.
"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi", reason="fastapi not installed")
pytest.importorskip("jwt", reason="PyJWT not installed")

from fastapi.testclient import TestClient

from promptgate.api import make_app
from promptgate.auth.db import AuthDB
from promptgate.auth.security import create_access_token


@pytest.fixture(autouse=True)
def _fake_scorers(monkeypatch):
    """Replace the litellm-backed scorers with deterministic fakes."""
    def fake_generate(prompt_id, model_id, db_path):
        return lambda case: (f"ANSWER:{case['question']}", 12)

    def fake_judge(model_id):
        return lambda q, a: (9.0, 0.5)  # → green

    monkeypatch.setattr("promptgate.quality.scorers.build_generate_fn", fake_generate)
    monkeypatch.setattr("promptgate.quality.scorers.build_judge_fn", fake_judge)


@pytest.fixture()
def app_db(tmp_path):
    return tmp_path / "app.sqlite"


@pytest.fixture()
def app(app_db):
    return make_app(app_db)


def _client(app, app_db, username, role):
    c = TestClient(app)
    u = AuthDB(app_db).create_user(username, f"{username}@x.io", "passpass1", role)
    c.headers.update({"Authorization": f"Bearer {create_access_token(sub=u['id'], role=role)}"})
    return c, u


def _make_prompt(c, pid="p1"):
    c.post("/api/prompts", json={"id": pid, "name": pid,
                                 "template": "Answer {{ q }} as JSON.", "schema": {}})


def test_validate_run_persists_and_scores(app, app_db):
    c, _ = _client(app, app_db, "alex", "prompter")
    _make_prompt(c)
    r = c.post("/api/prompts/p1/validate", json={
        "model_id": "openai/gpt-4o-mini",
        "cases": [{"question": "q1"}, {"question": "q2"}], "repeats": 3,
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["determinism"] == 100.0 and body["color"] == "green"
    assert body["n_cases"] == 2 and len(body["cases"]) == 2
    assert "run_id" in body

    # rollup
    q = c.get("/api/prompts/p1/quality").json()
    assert q["n_validations"] == 1 and q["color"] == "green"
    # history
    runs = c.get("/api/prompts/p1/validations").json()
    assert len(runs) == 1 and runs[0]["run_id"] == body["run_id"]
    # detail
    detail = c.get(f"/api/validations/{body['run_id']}").json()
    assert len(detail["cases"]) == 2


def test_rollup_running_mean(app, app_db):
    c, _ = _client(app, app_db, "alex", "prompter")
    _make_prompt(c)
    payload = {"model_id": "m", "cases": [{"question": "q"}], "repeats": 1}
    c.post("/api/prompts/p1/validate", json=payload)
    c.post("/api/prompts/p1/validate", json=payload)
    q = c.get("/api/prompts/p1/quality").json()
    assert q["n_validations"] == 2


def test_guest_cannot_validate(app, app_db):
    c, _ = _client(app, app_db, "g", "guest")
    # guest can't create either, so seed as admin first
    admin, _ = _client(app, app_db, "boss", "admin")
    _make_prompt(admin)
    r = c.post("/api/prompts/p1/validate", json={"model_id": "m", "cases": [{"question": "q"}]})
    assert r.status_code == 403


def test_validate_requires_read_access(app, app_db):
    alex, _ = _client(app, app_db, "alex", "prompter")
    maria, _ = _client(app, app_db, "maria", "prompter")
    _make_prompt(alex, "secret")
    r = maria.post("/api/prompts/secret/validate", json={"model_id": "m", "cases": [{"question": "q"}]})
    assert r.status_code == 403


def test_dashboard_scoped_by_owner(app, app_db):
    alex, _ = _client(app, app_db, "alex", "prompter")
    maria, _ = _client(app, app_db, "maria", "prompter")
    _make_prompt(alex, "ap")
    _make_prompt(maria, "mp")
    alex.post("/api/prompts/ap/validate", json={"model_id": "m", "cases": [{"question": "q"}]})
    maria.post("/api/prompts/mp/validate", json={"model_id": "m", "cases": [{"question": "q"}]})
    alex_dash = {row["prompt_id"] for row in alex.get("/api/quality").json()}
    assert alex_dash == {"ap"}


def test_validate_empty_cases_422(app, app_db):
    c, _ = _client(app, app_db, "alex", "prompter")
    _make_prompt(c)
    r = c.post("/api/prompts/p1/validate", json={"model_id": "m", "cases": []})
    assert r.status_code == 422


def test_quality_404_when_never_validated(app, app_db):
    c, _ = _client(app, app_db, "alex", "prompter")
    _make_prompt(c)
    assert c.get("/api/prompts/p1/quality").status_code == 404
