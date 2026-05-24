"""Tests for promptgate.api — FastAPI REST server."""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

pytest.importorskip("fastapi", reason="fastapi not installed")

from fastapi.testclient import TestClient

from promptgate.api import make_app


@pytest.fixture()
def client(tmp_path) -> TestClient:
    db = tmp_path / "test.sqlite"
    app = make_app(db)
    return TestClient(app)


def _sample_prompt() -> dict:
    return {
        "id": "greet_v1",
        "name": "Greeting",
        "template": "Hello {{ name }}.",
        "schema": {
            "type": "object",
            "properties": {"greeting": {"type": "string"}},
            "required": ["greeting"],
        },
    }


def _sample_chain() -> dict:
    return {
        "id": "pipe_v1",
        "name": "Test Chain",
        "steps": [{"prompt_id": "greet_v1", "model": "gpt-4o"}],
    }


# ── prompts ───────────────────────────────────────────────────────────────────

def test_list_prompts_empty(client: TestClient) -> None:
    r = client.get("/api/prompts")
    assert r.status_code == 200
    assert r.json() == []


def test_create_and_get_prompt(client: TestClient) -> None:
    r = client.post("/api/prompts", json=_sample_prompt())
    assert r.status_code == 201
    assert r.json()["id"] == "greet_v1"

    r2 = client.get("/api/prompts/greet_v1")
    assert r2.status_code == 200
    assert r2.json()["id"] == "greet_v1"


def test_get_missing_prompt_404(client: TestClient) -> None:
    r = client.get("/api/prompts/nope")
    assert r.status_code == 404


def test_delete_prompt(client: TestClient) -> None:
    client.post("/api/prompts", json=_sample_prompt())
    r = client.delete("/api/prompts/greet_v1")
    assert r.status_code == 200
    assert client.get("/api/prompts/greet_v1").status_code == 404


def test_delete_missing_prompt_404(client: TestClient) -> None:
    r = client.delete("/api/prompts/ghost")
    assert r.status_code == 404


def test_list_prompts_after_create(client: TestClient) -> None:
    client.post("/api/prompts", json=_sample_prompt())
    r = client.get("/api/prompts")
    assert len(r.json()) == 1


# ── search ────────────────────────────────────────────────────────────────────

def test_search_returns_results(client: TestClient) -> None:
    client.post("/api/prompts", json=_sample_prompt())
    r = client.get("/api/search", params={"q": "greeting"})
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# ── compile ───────────────────────────────────────────────────────────────────

def test_compile_ok(client: TestClient) -> None:
    client.post("/api/prompts", json=_sample_prompt())
    r = client.post("/api/compile", json={"prompt_id": "greet_v1", "payload": {"name": "Alice"}})
    assert r.status_code == 200
    body = r.json()
    assert "system_prompt" in body


def test_compile_missing_prompt_404(client: TestClient) -> None:
    r = client.post("/api/compile", json={"prompt_id": "ghost", "payload": {}})
    assert r.status_code == 404


# ── validate ──────────────────────────────────────────────────────────────────

def test_validate_ok(client: TestClient) -> None:
    client.post("/api/prompts", json=_sample_prompt())
    r = client.post("/api/validate", json={
        "prompt_id": "greet_v1",
        "payload": {},
        "llm_output": json.dumps({"greeting": "Hi!"}),
    })
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_validate_bad_output(client: TestClient) -> None:
    client.post("/api/prompts", json=_sample_prompt())
    r = client.post("/api/validate", json={
        "prompt_id": "greet_v1",
        "payload": {},
        "llm_output": "not json",
    })
    assert r.status_code == 200
    assert r.json()["ok"] is False


# ── chains ────────────────────────────────────────────────────────────────────

def test_list_chains_empty(client: TestClient) -> None:
    r = client.get("/api/chains")
    assert r.status_code == 200
    assert r.json() == []


def test_create_and_get_chain(client: TestClient) -> None:
    client.post("/api/prompts", json=_sample_prompt())
    r = client.post("/api/chains", json=_sample_chain())
    assert r.status_code == 201
    assert r.json()["id"] == "pipe_v1"

    r2 = client.get("/api/chains/pipe_v1")
    assert r2.status_code == 200


def test_get_missing_chain_404(client: TestClient) -> None:
    r = client.get("/api/chains/ghost")
    assert r.status_code == 404


def test_delete_chain(client: TestClient) -> None:
    client.post("/api/prompts", json=_sample_prompt())
    client.post("/api/chains", json=_sample_chain())
    r = client.delete("/api/chains/pipe_v1")
    assert r.status_code == 200
    assert client.get("/api/chains/pipe_v1").status_code == 404


# ── run ───────────────────────────────────────────────────────────────────────

def test_run_endpoint_ok(client: TestClient) -> None:
    client.post("/api/prompts", json=_sample_prompt())
    good = json.dumps({"greeting": "Hello!"})

    def _make_response(content: str) -> SimpleNamespace:
        msg = SimpleNamespace(content=content)
        choice = SimpleNamespace(message=msg)
        return SimpleNamespace(choices=[choice])

    with patch("litellm.completion", return_value=_make_response(good)):
        r = client.post("/api/run", json={
            "prompt_id": "greet_v1",
            "payload": {"name": "Alice"},
            "model_id": "gpt-4o",
        })

    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["data"] == {"greeting": "Hello!"}
