"""FastAPI REST server for pgate."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from promptgate.models_registry import list_models
from promptgate.profiles import get_profile, list_profiles
from promptgate.chains import (
    ChainConfig,
    delete_chain, get_chain, list_chains,
    run_chain, upsert_chain,
)
from promptgate.file_api import _DEFAULT_DB_PATH, get_or_compile
from promptgate.models import PromptConfig
from promptgate.router import search as pg_search
from promptgate.storage import SQLiteBackend
from promptgate.validator import validate_output
from promptgate.auth import build_auth_router
from promptgate.auth.deps import make_auth_deps
from promptgate.migrations import run_migrations


def _cors_origins() -> list[str]:
    """Allowed CORS origins. Override with PROMPTGATE_CORS_ORIGINS (comma-separated).

    Defaults to the local Vite dev server. The production UI is served
    same-origin by this app, so it needs no CORS entry.
    """
    raw = os.environ.get("PROMPTGATE_CORS_ORIGINS")
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    return ["http://localhost:5173", "http://127.0.0.1:5173"]


# ── request body models (module-level so FastAPI schema inspection works) ─────

class _CompileIn(BaseModel):
    prompt_id: str
    payload: dict = {}
    model_id: str | None = None


class _RunIn(BaseModel):
    prompt_id: str
    payload: dict = {}
    model_id: str
    max_retries: int = 3
    user_message: str | None = None


class _ValidateIn(BaseModel):
    llm_output: str
    prompt_id: str
    payload: dict = {}
    model_id: str | None = None


class _ChainRunIn(BaseModel):
    payload: dict = {}
    max_retries_per_step: int = 3


class _KeyIn(BaseModel):
    name: str
    value: str


def make_app(db_path: str | Path = _DEFAULT_DB_PATH) -> FastAPI:
    """Create and return a configured FastAPI application.

    Args:
        db_path: Path to SQLite database. Injected into all route handlers.

    Returns:
        FastAPI app with CRUD, search, compile, run, and chain endpoints.

    Examples:
        >>> app = make_app(":memory:")
        >>> app.title
        'PGate API'
    """
    app = FastAPI(title="PGate API", version="0.3.0", description="Prompt ORM REST API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    db = Path(db_path)

    # Platform schema (users, invites, audit…) — idempotent, runs on app creation.
    run_migrations(db)
    app.include_router(build_auth_router(db))

    # Auth dependencies for the data API. `_auth` = any logged-in user;
    # `_admin_env` = admin-only (key vault). Fine-grained ownership lands in P2.
    get_current_user, require_permission = make_auth_deps(db)
    _auth = [Depends(get_current_user)]
    _admin_env = [Depends(require_permission("admin.env"))]

    def _backend() -> SQLiteBackend:
        b = SQLiteBackend(db)
        b.init()
        return b

    # ── prompts ───────────────────────────────────────────────────────────────

    @app.get("/api/prompts", dependencies=_auth)
    def list_prompts() -> list[dict]:
        """List all stored prompts."""
        return [p.model_dump(by_alias=True) for p in _backend().list_all()]

    @app.get("/api/prompts/{prompt_id}", dependencies=_auth)
    def get_prompt(prompt_id: str) -> dict:
        """Get a single prompt by ID."""
        p = _backend().get(prompt_id)
        if p is None:
            raise HTTPException(404, f"Prompt '{prompt_id}' not found")
        return p.model_dump(by_alias=True)

    @app.post("/api/prompts", status_code=201, dependencies=_auth)
    def create_prompt(body: dict) -> dict:
        """Add or update a prompt from a dict (YAML-equivalent fields)."""
        prompt = PromptConfig.model_validate(body)
        _backend().upsert(prompt)
        return {"ok": True, "id": prompt.id}

    @app.delete("/api/prompts/{prompt_id}", dependencies=_auth)
    def delete_prompt(prompt_id: str) -> dict:
        """Delete a prompt by ID."""
        if not _backend().delete(prompt_id):
            raise HTTPException(404, f"Prompt '{prompt_id}' not found")
        return {"ok": True}

    @app.get("/api/search", dependencies=_auth)
    def search(q: str, limit: int = 5) -> list[dict]:
        """Full-text search over prompts."""
        results = pg_search(q, db_path=db, limit=limit)
        return [{"prompt_id": pid, "score": score} for pid, score in results]

    # ── compile ───────────────────────────────────────────────────────────────

    @app.post("/api/compile", dependencies=_auth)
    def compile_prompt_endpoint(body: _CompileIn) -> dict:
        """Compile a prompt contract (cached)."""
        try:
            contract = get_or_compile(body.prompt_id, body.payload, db_path=db, model_id=body.model_id)
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc
        return contract.model_dump()

    # ── run ───────────────────────────────────────────────────────────────────

    @app.post("/api/run", dependencies=_auth)
    def run_prompt(body: _RunIn) -> dict:
        """Compile, call LLM, validate, retry — return result."""
        import os
        try:
            from promptgate.runner import run as pg_run
        except ImportError as exc:
            raise HTTPException(501, "litellm not installed: pip install pgate[litellm]") from exc
        try:
            from promptgate.keystore import get_key, list_keys
            for name in list_keys():
                env_name = name.upper()
                if env_name not in os.environ:
                    val = get_key(name)
                    if val:
                        os.environ[env_name] = val
        except Exception:
            pass
        try:
            result = pg_run(
                body.prompt_id, body.payload, body.model_id,
                db_path=db, max_retries=body.max_retries, user_message=body.user_message,
            )
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc
        except Exception as exc:
            raise HTTPException(422, f"LLM error: {exc}") from exc
        return {"ok": result.ok, "data": result.data, "raw_output": result.raw_output, "attempts": result.attempts}

    # ── validate ──────────────────────────────────────────────────────────────

    @app.post("/api/validate", dependencies=_auth)
    def validate_endpoint(body: _ValidateIn) -> dict:
        """Validate raw LLM output against a prompt's schema."""
        try:
            contract = get_or_compile(body.prompt_id, body.payload, db_path=db, model_id=body.model_id)
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc
        prompt = _backend().get(body.prompt_id)
        result = validate_output(body.llm_output, contract, prompt.schema_)
        return {"ok": result.ok, "data": result.data, "retry_instruction": result.retry_instruction}

    # ── chains ────────────────────────────────────────────────────────────────

    @app.get("/api/chains", dependencies=_auth)
    def list_chains_endpoint() -> list[dict]:
        """List all stored chains."""
        return [c.model_dump() for c in list_chains(db)]

    @app.get("/api/chains/{chain_id}", dependencies=_auth)
    def get_chain_endpoint(chain_id: str) -> dict:
        """Get a chain by ID."""
        c = get_chain(chain_id, db)
        if c is None:
            raise HTTPException(404, f"Chain '{chain_id}' not found")
        return c.model_dump()

    @app.post("/api/chains", status_code=201, dependencies=_auth)
    def create_chain(body: dict) -> dict:
        """Add or update a chain."""
        chain = ChainConfig.model_validate(body)
        upsert_chain(chain, db)
        return {"ok": True, "id": chain.id}

    @app.delete("/api/chains/{chain_id}", dependencies=_auth)
    def delete_chain_endpoint(chain_id: str) -> dict:
        """Delete a chain by ID."""
        if not delete_chain(chain_id, db):
            raise HTTPException(404, f"Chain '{chain_id}' not found")
        return {"ok": True}

    @app.post("/api/chains/{chain_id}/run", dependencies=_auth)
    def run_chain_endpoint(chain_id: str, body: _ChainRunIn) -> dict:
        """Run a chain with an initial payload."""
        try:
            result = run_chain(chain_id, body.payload, db_path=db, max_retries_per_step=body.max_retries_per_step)
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc
        except ImportError as exc:
            raise HTTPException(501, str(exc)) from exc
        return {"ok": result.ok, "context": result.context, "failed_step": result.failed_step, "steps_run": result.steps_run}

    # ── models + profile ──────────────────────────────────────────────────────

    @app.get("/api/models", dependencies=_auth)
    def list_models_endpoint() -> list[str]:
        """List all available model IDs (built-in + user-defined)."""
        return list_models(include_custom=True)

    @app.get("/api/profile", dependencies=_auth)
    def get_active_profile_endpoint() -> dict:
        """Return the active profile config."""
        try:
            profiles = list_profiles()
            active_name = next((name for name, is_def in profiles if is_def), "default")
            profile = get_profile(active_name)
            return {
                "name": active_name,
                "default_model": profile.get("default_model", ""),
                "api_base": profile.get("litellm_api_base", ""),
            }
        except Exception:
            return {"name": "default", "default_model": "", "api_base": ""}

    # ── keys ──────────────────────────────────────────────────────────────────

    @app.get("/api/keys", dependencies=_admin_env)
    def list_keys_endpoint() -> list[str]:
        """List stored API key names (values are never returned)."""
        try:
            from promptgate.keystore import list_keys
            return list_keys()
        except Exception:
            return []

    @app.post("/api/keys", status_code=201, dependencies=_admin_env)
    def set_key_endpoint(body: _KeyIn) -> dict:
        """Store or update an API key (encrypted on disk)."""
        try:
            from promptgate.keystore import set_key
        except ImportError as exc:
            raise HTTPException(501, "cryptography not installed: pip install pgate[crypto]") from exc
        if not body.name or not body.value:
            raise HTTPException(422, "name and value required")
        set_key(body.name, body.value)
        return {"ok": True, "name": body.name}

    @app.delete("/api/keys/{name}", dependencies=_admin_env)
    def delete_key_endpoint(name: str) -> dict:
        """Delete a stored API key."""
        try:
            from promptgate.keystore import delete_key
        except ImportError as exc:
            raise HTTPException(501, "cryptography not installed: pip install pgate[crypto]") from exc
        if not delete_key(name):
            raise HTTPException(404, f"Key '{name}' not found")
        return {"ok": True}

    # ── static UI ─────────────────────────────────────────────────────────────

    @app.get("/")
    def root_redirect() -> RedirectResponse:
        """Redirect root to the web UI."""
        return RedirectResponse("/ui/")

    _ui_dir = Path(__file__).parent / "ui"
    if _ui_dir.is_dir():
        app.mount("/ui", StaticFiles(directory=_ui_dir, html=True), name="ui")

    return app
