"""Tests for the platform auth layer (P1): migrations, RBAC, and the auth API."""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi", reason="fastapi not installed")
pytest.importorskip("jwt", reason="PyJWT not installed")
pytest.importorskip("bcrypt", reason="bcrypt not installed")

from fastapi.testclient import TestClient

from promptgate.api import make_app
from promptgate.auth.db import AuthDB
from promptgate.auth.roles import Role, can
from promptgate.migrations import run_migrations


@pytest.fixture()
def db(tmp_path):
    p = tmp_path / "auth.sqlite"
    run_migrations(p)
    return p


@pytest.fixture()
def client(tmp_path):
    return TestClient(make_app(tmp_path / "app.sqlite"))


# ── migrations ────────────────────────────────────────────────────────────────
def test_migrations_idempotent(tmp_path):
    p = tmp_path / "m.sqlite"
    applied = run_migrations(p)
    assert applied[:2] == ["0001_auth", "0002_prompt_meta_versions"]
    assert "0003_validation_quality" in applied
    assert run_migrations(p) == []   # second run is a no-op


# ── rbac ──────────────────────────────────────────────────────────────────────
def test_rbac_matrix():
    assert can(Role.admin, "admin.users")
    assert can("prompter", "prompt.create")
    assert not can("validator", "prompt.create")
    assert can("validator", "validate.run")
    assert not can("guest", "validate.run")
    assert not can("bogus", "prompt.view_own")


# ── password hashing ────────────────────────────────────────────────────────────
def test_password_roundtrip():
    from promptgate.auth.security import hash_password, verify_password
    h = hash_password("s3cret-pass")
    assert verify_password("s3cret-pass", h)
    assert not verify_password("wrong", h)


# ── invite → register → login → me ──────────────────────────────────────────────
def test_full_auth_flow(client, tmp_path):
    # bootstrap an admin directly, then mint an invite via the admin API
    adb = AuthDB(tmp_path / "app.sqlite")
    admin = adb.create_user("admin", "admin@x.io", "adminpass1", "admin")
    login = client.post("/api/auth/login", json={"username": "admin", "password": "adminpass1"})
    assert login.status_code == 200, login.text
    admin_token = login.json()["access_token"]
    assert login.json()["user"]["role"] == "admin"

    h = {"Authorization": f"Bearer {admin_token}"}
    inv = client.post("/api/auth/invites", json={"role": "prompter"}, headers=h)
    assert inv.status_code == 201, inv.text
    token = inv.json()["token"]

    reg = client.post("/api/auth/register", json={
        "invite_token": token, "username": "alice",
        "email": "alice@x.io", "password": "alicepass1",
    })
    assert reg.status_code == 201, reg.text
    alice_token = reg.json()["access_token"]
    assert reg.json()["user"]["role"] == "prompter"

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {alice_token}"})
    assert me.status_code == 200
    assert me.json()["username"] == "alice"


def test_login_rejects_bad_password(client, tmp_path):
    AuthDB(tmp_path / "app.sqlite").create_user("bob", "bob@x.io", "bobpass12", "prompter")
    r = client.post("/api/auth/login", json={"username": "bob", "password": "nope"})
    assert r.status_code == 401


def test_register_rejects_bad_invite(client):
    r = client.post("/api/auth/register", json={
        "invite_token": "does-not-exist", "username": "eve",
        "email": "eve@x.io", "password": "evepass123",
    })
    assert r.status_code == 400


def test_me_requires_token(client):
    assert client.get("/api/auth/me").status_code == 401


def test_invite_endpoint_requires_admin(client, tmp_path):
    # prompter cannot mint invites
    AuthDB(tmp_path / "app.sqlite").create_user("pp", "pp@x.io", "pppass123", "prompter")
    tok = client.post("/api/auth/login", json={"username": "pp", "password": "pppass123"}).json()["access_token"]
    r = client.post("/api/auth/invites", json={"role": "guest"},
                    headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 403


def test_request_invite_creates_pending(client, tmp_path):
    r = client.post("/api/auth/request-invite", json={"email": "new@x.io", "reason": "AI eng"})
    assert r.status_code == 202
    assert r.json()["status"] == "pending"
    pending = AuthDB(tmp_path / "app.sqlite").list_registration_requests("pending")
    assert any(x["email"] == "new@x.io" for x in pending)


# ── security-fix regression tests ────────────────────────────────────────────
def _token(db_path, username, role):
    from promptgate.auth.security import create_access_token
    u = AuthDB(db_path).create_user(username, f"{username}@x.io", "passpass1", role)
    return u, {"Authorization": f"Bearer {create_access_token(sub=u['id'], role=role)}"}


def test_data_endpoints_require_auth(tmp_path):
    """C1: unauthenticated access to the data API is rejected."""
    c = TestClient(make_app(tmp_path / "d.sqlite"))
    assert c.get("/api/prompts").status_code == 401
    assert c.get("/api/keys").status_code == 401
    assert c.post("/api/prompts", json={}).status_code == 401


def test_keys_require_admin(tmp_path):
    """C1: key vault is admin-only, not just any logged-in user."""
    c = TestClient(make_app(tmp_path / "d.sqlite"))
    _, h = _token(tmp_path / "d.sqlite", "pp", "prompter")
    assert c.get("/api/keys", headers=h).status_code == 403


def test_one_time_invite_single_use(db):
    """M1: a one-time invite can be claimed exactly once."""
    adb = AuthDB(db)
    inv = adb.create_invite("prompter", created_by=None)
    assert adb.claim_invite(inv["token"]) is not None
    assert adb.claim_invite(inv["token"]) is None


def test_disabled_user_token_rejected(client, tmp_path):
    """H3: disabling a user invalidates their existing token on next request."""
    dbp = tmp_path / "app.sqlite"
    u, h = _token(dbp, "zoe", "prompter")
    assert client.get("/api/auth/me", headers=h).status_code == 200
    assert AuthDB(dbp).set_user_status(u["id"], "disabled") is True
    assert client.get("/api/auth/me", headers=h).status_code == 401


def test_approve_request_idempotent(client, tmp_path):
    """M4: replaying approve does not mint a second invite."""
    dbp = tmp_path / "app.sqlite"
    _, h = _token(dbp, "adm", "admin")
    req = AuthDB(dbp).create_registration_request("cand@x.io", "reason")
    r1 = client.post(f"/api/auth/requests/{req['id']}/approve", json={"role": "guest"}, headers=h)
    assert r1.status_code == 200
    r2 = client.post(f"/api/auth/requests/{req['id']}/approve", json={"role": "guest"}, headers=h)
    assert r2.status_code == 409


def test_login_rate_limited(client, tmp_path):
    """M3: login throttles after the per-(ip,user) budget is exhausted."""
    AuthDB(tmp_path / "app.sqlite").create_user("rl", "rl@x.io", "rlpass123", "guest")
    codes = [
        client.post("/api/auth/login", json={"username": "rl", "password": "wrong"}).status_code
        for _ in range(9)
    ]
    assert codes[:8] == [401] * 8
    assert codes[8] == 429
