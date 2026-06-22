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
from promptgate.prompts_service import PromptMetaStore
from promptgate.quality import lint_template
from promptgate.quality.store import QualityStore


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


class _LintIn(BaseModel):
    template: str


class _RollbackIn(BaseModel):
    version_no: int


class _ValidateCaseIn(BaseModel):
    question: str
    payload: dict = {}


class _ValidateRunIn(BaseModel):
    model_id: str
    cases: list[_ValidateCaseIn] = []
    repeats: int = 3


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
    require_create = require_permission("prompt.create")
    require_edit = require_permission("prompt.edit_own")
    require_delete = require_permission("prompt.delete_own")
    require_validate = require_permission("validate.run")
    meta = PromptMetaStore(db)
    quality_store = QualityStore(db)

    def _backend() -> SQLiteBackend:
        b = SQLiteBackend(db)
        b.init()
        return b

    def _prompt_dict(prompt: PromptConfig) -> dict:
        """PromptConfig + its ownership/version metadata."""
        d = prompt.model_dump(by_alias=True)
        m = meta.get_meta(prompt.id)
        d["status"] = m["status"] if m else "draft"
        d["current_version"] = m["current_version"] if m else 1
        d["owner_id"] = m["owner_id"] if m else None
        return d

    # ── prompts ───────────────────────────────────────────────────────────────

    @app.get("/api/prompts")
    def list_prompts(user: dict = Depends(get_current_user)) -> list[dict]:
        """List prompts the caller may see (admins see all)."""
        return [
            _prompt_dict(p) for p in _backend().list_all()
            if meta.can_read(p.id, user)
        ]

    @app.get("/api/prompts/{prompt_id}")
    def get_prompt(prompt_id: str, user: dict = Depends(get_current_user)) -> dict:
        """Get a single prompt by ID (must be readable by the caller)."""
        p = _backend().get(prompt_id)
        if p is None:
            raise HTTPException(404, f"Prompt '{prompt_id}' not found")
        if not meta.can_read(prompt_id, user):
            raise HTTPException(403, "You do not have access to this prompt")
        return _prompt_dict(p)

    @app.post("/api/prompts", status_code=201)
    def create_prompt(body: dict, user: dict = Depends(require_create)) -> dict:
        """Create or update a prompt; records a new version snapshot."""
        message = ""
        if isinstance(body, dict):
            message = str(body.pop("message", "") or "")
        prompt = PromptConfig.model_validate(body)
        if not meta.can_write(prompt.id, user):
            raise HTTPException(403, "You do not own this prompt")
        _backend().upsert(prompt)
        version = meta.record_version(
            prompt.id, prompt.model_dump(by_alias=True), author_id=user["id"], message=message,
        )
        return {"ok": True, "id": prompt.id, "version": version}

    @app.delete("/api/prompts/{prompt_id}")
    def delete_prompt(prompt_id: str, user: dict = Depends(require_delete)) -> dict:
        """Delete a prompt and its version history (must be owner/admin)."""
        if not meta.can_write(prompt_id, user):
            raise HTTPException(403, "You do not own this prompt")
        if not _backend().delete(prompt_id):
            raise HTTPException(404, f"Prompt '{prompt_id}' not found")
        meta.delete_all(prompt_id)
        return {"ok": True}

    # ── prompt versions + publish ───────────────────────────────────────────────

    @app.get("/api/prompts/{prompt_id}/versions")
    def list_prompt_versions(prompt_id: str, user: dict = Depends(get_current_user)) -> list[dict]:
        if not meta.can_read(prompt_id, user):
            raise HTTPException(403, "You do not have access to this prompt")
        return meta.list_versions(prompt_id)

    @app.get("/api/prompts/{prompt_id}/versions/{version_no}")
    def get_prompt_version(
        prompt_id: str, version_no: int, user: dict = Depends(get_current_user),
    ) -> dict:
        if not meta.can_read(prompt_id, user):
            raise HTTPException(403, "You do not have access to this prompt")
        v = meta.get_version(prompt_id, version_no)
        if v is None:
            raise HTTPException(404, f"Version {version_no} not found for '{prompt_id}'")
        return v

    @app.post("/api/prompts/{prompt_id}/rollback")
    def rollback_prompt(
        prompt_id: str, body: _RollbackIn, user: dict = Depends(require_edit),
    ) -> dict:
        """Restore a past version as a new current version."""
        if not meta.can_write(prompt_id, user):
            raise HTTPException(403, "You do not own this prompt")
        v = meta.get_version(prompt_id, body.version_no)
        if v is None:
            raise HTTPException(404, f"Version {body.version_no} not found")
        prompt = PromptConfig.model_validate(v["body"])
        _backend().upsert(prompt)
        version = meta.record_version(
            prompt_id, v["body"], author_id=user["id"],
            message=f"rollback to v{body.version_no}",
        )
        return {"ok": True, "version": version}

    @app.post("/api/prompts/{prompt_id}/publish")
    def publish_prompt(prompt_id: str, user: dict = Depends(require_edit)) -> dict:
        if not meta.can_write(prompt_id, user):
            raise HTTPException(403, "You do not own this prompt")
        if _backend().get(prompt_id) is None:
            raise HTTPException(404, f"Prompt '{prompt_id}' not found")
        meta.set_status(prompt_id, "published")
        return {"ok": True, "status": "published"}

    # ── live lint (static 3-type validation) ────────────────────────────────────

    @app.post("/api/lint")
    def lint_endpoint(body: _LintIn, _: dict = Depends(get_current_user)) -> dict:
        """Static, no-LLM prompt linting → stylistic/determinism/hallucination findings."""
        return {"findings": [f.to_dict() for f in lint_template(body.template)]}

    # ── deep validation + quality (P3) ──────────────────────────────────────────

    @app.post("/api/prompts/{prompt_id}/validate")
    def validate_run(
        prompt_id: str, body: _ValidateRunIn, user: dict = Depends(require_validate),
    ) -> dict:
        """Run a deep, LLM-backed validation over a test set; persist scores."""
        if not meta.can_read(prompt_id, user):
            raise HTTPException(403, "You do not have access to this prompt")
        if _backend().get(prompt_id) is None:
            raise HTTPException(404, f"Prompt '{prompt_id}' not found")
        from promptgate.quality import deep, scorers
        try:
            generate_fn = scorers.build_generate_fn(prompt_id, body.model_id, db)
            judge_fn = scorers.build_judge_fn(body.model_id)
        except ImportError as exc:
            raise HTTPException(501, "litellm not installed: pip install pgate[litellm]") from exc
        cases = [c.model_dump() for c in body.cases]
        try:
            result = deep.run_validation(cases, generate_fn, judge_fn, repeats=body.repeats)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except Exception as exc:  # noqa: BLE001 — surface LLM/runtime errors as 422
            raise HTTPException(422, f"Validation error: {exc}") from exc
        m = meta.get_meta(prompt_id)
        run_id = quality_store.save_run(
            prompt_id, m["current_version"] if m else None, body.model_id, result, user["id"],
        )
        out = result.to_dict()
        out.update({"run_id": run_id, "model_id": body.model_id})
        return out

    @app.get("/api/prompts/{prompt_id}/quality")
    def prompt_quality(prompt_id: str, user: dict = Depends(get_current_user)) -> dict:
        if not meta.can_read(prompt_id, user):
            raise HTTPException(403, "You do not have access to this prompt")
        q = quality_store.get_quality(prompt_id)
        if q is None:
            raise HTTPException(404, "No validation runs for this prompt yet")
        return q

    @app.get("/api/prompts/{prompt_id}/validations")
    def prompt_validations(prompt_id: str, user: dict = Depends(get_current_user)) -> list[dict]:
        if not meta.can_read(prompt_id, user):
            raise HTTPException(403, "You do not have access to this prompt")
        return quality_store.list_runs(prompt_id)

    @app.get("/api/validations/{run_id}")
    def validation_detail(run_id: int, user: dict = Depends(get_current_user)) -> dict:
        prompt_id = quality_store.run_owner_prompt(run_id)
        if prompt_id is None:
            raise HTTPException(404, f"Run {run_id} not found")
        if not meta.can_read(prompt_id, user):
            raise HTTPException(403, "You do not have access to this run")
        return quality_store.get_run(run_id)

    @app.get("/api/quality")
    def quality_dashboard(user: dict = Depends(get_current_user)) -> list[dict]:
        """Quality rollup for every prompt the caller may see (admins: all)."""
        names = {p.id: p.name for p in _backend().list_all()}
        out = []
        for row in quality_store.dashboard():
            pid = row["prompt_id"]
            if not meta.can_read(pid, user):
                continue
            row["name"] = names.get(pid, pid)
            out.append(row)
        return out

    @app.get("/api/search")
    def search(q: str, limit: int = 5, user: dict = Depends(get_current_user)) -> list[dict]:
        """Full-text search over prompts the caller may see."""
        # Over-fetch, then apply ownership filter, then slice — so the caller
        # still gets up to `limit` rows they're allowed to see.
        results = pg_search(q, db_path=db, limit=max(limit * 5, limit))
        allowed = [
            {"prompt_id": pid, "score": score}
            for pid, score in results
            if meta.can_read(pid, user)
        ]
        return allowed[:limit]

    # ── compile ───────────────────────────────────────────────────────────────

    @app.post("/api/compile")
    def compile_prompt_endpoint(body: _CompileIn, user: dict = Depends(get_current_user)) -> dict:
        """Compile a prompt contract (cached)."""
        if not meta.can_read(body.prompt_id, user):
            raise HTTPException(403, "You do not have access to this prompt")
        try:
            contract = get_or_compile(body.prompt_id, body.payload, db_path=db, model_id=body.model_id)
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc
        return contract.model_dump()

    # ── run ───────────────────────────────────────────────────────────────────

    @app.post("/api/run")
    def run_prompt(body: _RunIn, user: dict = Depends(get_current_user)) -> dict:
        """Compile, call LLM, validate, retry — return result."""
        import os
        if not meta.can_read(body.prompt_id, user):
            raise HTTPException(403, "You do not have access to this prompt")
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

    @app.post("/api/validate")
    def validate_endpoint(body: _ValidateIn, user: dict = Depends(get_current_user)) -> dict:
        """Validate raw LLM output against a prompt's schema."""
        if not meta.can_read(body.prompt_id, user):
            raise HTTPException(403, "You do not have access to this prompt")
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
