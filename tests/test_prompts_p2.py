"""P2 API tests: prompt ownership scoping, versioning, rollback, publish, lint."""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi", reason="fastapi not installed")
pytest.importorskip("jwt", reason="PyJWT not installed")

from fastapi.testclient import TestClient

from promptgate.api import make_app
from promptgate.auth.db import AuthDB
from promptgate.auth.security import create_access_token


def _prompt(pid="greet_v1", template="Hello {{ name }}. Answer as JSON."):
    return {
        "id": pid, "name": pid, "template": template,
        "schema": {"type": "object", "properties": {"greeting": {"type": "string"}}},
    }


@pytest.fixture()
def app_db(tmp_path):
    return tmp_path / "app.sqlite"


@pytest.fixture()
def app(app_db):
    return make_app(app_db)


def _user_client(app, app_db, username, role):
    c = TestClient(app)
    u = AuthDB(app_db).create_user(username, f"{username}@x.io", "passpass1", role)
    c.headers.update({"Authorization": f"Bearer {create_access_token(sub=u['id'], role=role)}"})
    return c, u


# ── versioning ────────────────────────────────────────────────────────────────
def test_create_records_v1_then_bumps(app, app_db):
    c, _ = _user_client(app, app_db, "alex", "prompter")
    r1 = c.post("/api/prompts", json={**_prompt(), "message": "init"})
    assert r1.status_code == 201 and r1.json()["version"] == 1
    r2 = c.post("/api/prompts", json={**_prompt(template="Hi {{ name }}. JSON."), "message": "tweak"})
    assert r2.json()["version"] == 2

    versions = c.get("/api/prompts/greet_v1/versions").json()
    assert [v["version_no"] for v in versions] == [2, 1]
    assert versions[0]["message"] == "tweak"


def test_rollback_creates_new_version_with_old_body(app, app_db):
    c, _ = _user_client(app, app_db, "alex", "prompter")
    c.post("/api/prompts", json={**_prompt(template="ONE {{ name }}. JSON."), "message": "v1"})
    c.post("/api/prompts", json={**_prompt(template="TWO {{ name }}. JSON."), "message": "v2"})
    rb = c.post("/api/prompts/greet_v1/rollback", json={"version_no": 1})
    assert rb.status_code == 200 and rb.json()["version"] == 3
    current = c.get("/api/prompts/greet_v1").json()
    assert current["template"].startswith("ONE")
    assert current["current_version"] == 3


def test_publish_sets_status(app, app_db):
    c, _ = _user_client(app, app_db, "alex", "prompter")
    c.post("/api/prompts", json=_prompt())
    assert c.post("/api/prompts/greet_v1/publish").json()["status"] == "published"
    assert c.get("/api/prompts/greet_v1").json()["status"] == "published"


# ── ownership ───────────────────────────────────────────────────────────────────
def test_prompts_scoped_to_owner(app, app_db):
    alex, _ = _user_client(app, app_db, "alex", "prompter")
    maria, _ = _user_client(app, app_db, "maria", "prompter")
    alex.post("/api/prompts", json=_prompt("alex_p"))
    maria.post("/api/prompts", json=_prompt("maria_p"))

    alex_ids = {p["id"] for p in alex.get("/api/prompts").json()}
    assert alex_ids == {"alex_p"}                      # maria's prompt is hidden
    assert maria.get("/api/prompts/alex_p").status_code == 403


def test_admin_sees_all(app, app_db):
    alex, _ = _user_client(app, app_db, "alex", "prompter")
    admin, _ = _user_client(app, app_db, "boss", "admin")
    alex.post("/api/prompts", json=_prompt("alex_p"))
    ids = {p["id"] for p in admin.get("/api/prompts").json()}
    assert "alex_p" in ids
    assert admin.get("/api/prompts/alex_p").status_code == 200


def test_validator_cannot_create(app, app_db):
    val, _ = _user_client(app, app_db, "val", "validator")
    assert val.post("/api/prompts", json=_prompt()).status_code == 403


def test_cannot_compile_others_prompt(app, app_db):
    """IDOR: compile/run/validate enforce read access by prompt_id."""
    alex, _ = _user_client(app, app_db, "alex", "prompter")
    maria, _ = _user_client(app, app_db, "maria", "prompter")
    alex.post("/api/prompts", json=_prompt("secret_p"))
    r = maria.post("/api/compile", json={"prompt_id": "secret_p", "payload": {}})
    assert r.status_code == 403


# ── lint endpoint ─────────────────────────────────────────────────────────────────
def test_lint_endpoint(app, app_db):
    c, _ = _user_client(app, app_db, "alex", "prompter")
    r = c.post("/api/lint", json={"template": "Cite the latest stats. Maybe just summarize."})
    assert r.status_code == 200
    types = {f["type"] for f in r.json()["findings"]}
    assert "hallucination" in types and "determinism" in types


def test_lint_requires_auth(app):
    assert TestClient(app).post("/api/lint", json={"template": "x"}).status_code == 401
