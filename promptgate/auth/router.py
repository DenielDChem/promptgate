"""Auth API router: login, register-by-invite, request-invite, me, logout,
plus admin-only invite & registration-request management.

Built via :func:`build_auth_router(db_path)` and mounted in ``make_app``.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request

from promptgate.auth.db import AuthDB, AuthError
from promptgate.auth.deps import make_auth_deps
from promptgate.auth.ratelimit import RateLimiter
from promptgate.auth.schemas import (
    ApproveRequestIn,
    InviteCreateIn,
    LoginIn,
    RegisterIn,
    RequestInviteIn,
    TokenOut,
    UserOut,
    UserStatusIn,
)
from promptgate.auth.security import create_access_token, dummy_verify, verify_password

# Per-process throttles (see ratelimit.py note on multi-worker deployments).
_login_limiter = RateLimiter(max_events=8, window_seconds=900)        # 8 / 15 min
_invite_req_limiter = RateLimiter(max_events=5, window_seconds=3600)  # 5 / hour


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def build_auth_router(db_path: str | Path) -> APIRouter:
    router = APIRouter(prefix="/api/auth", tags=["auth"])
    db = AuthDB(db_path)
    get_current_user, require_permission = make_auth_deps(db_path)

    def _token_response(user: dict) -> TokenOut:
        token = create_access_token(sub=user["id"], role=user["role"])
        return TokenOut(access_token=token, user=UserOut(**{
            "id": user["id"], "username": user["username"],
            "email": user["email"], "role": user["role"],
        }))

    # ── public ─────────────────────────────────────────────────────────────────
    @router.post("/login", response_model=TokenOut)
    def login(body: LoginIn, request: Request) -> TokenOut:
        ip = _client_ip(request)
        rl_key = f"{ip}:{body.username}"
        if not _login_limiter.allow(rl_key):
            db.audit("login.throttled", ip=ip, detail=body.username)
            raise HTTPException(status_code=429, detail="Too many attempts. Try again later.")
        user = db.get_user_by_username(body.username)
        if not user:
            dummy_verify(body.password)   # equalize timing vs. real-user path (no enumeration)
            db.audit("login.failed", ip=ip, detail=body.username)
            raise HTTPException(status_code=401, detail="Invalid username or password")
        if not verify_password(body.password, user["pw_hash"]):
            db.audit("login.failed", ip=ip, detail=body.username)
            raise HTTPException(status_code=401, detail="Invalid username or password")
        if user["status"] != "active":
            raise HTTPException(status_code=403, detail="Account disabled")
        _login_limiter.reset(rl_key)
        db.audit("login.ok", user_id=user["id"], ip=ip)
        return _token_response(user)

    @router.post("/register", response_model=TokenOut, status_code=201)
    def register(body: RegisterIn, request: Request) -> TokenOut:
        # Atomically claim the invite BEFORE creating the user so a one-time
        # invite can't mint two accounts under concurrent requests.
        invite = db.claim_invite(body.invite_token)
        if invite is None:
            raise HTTPException(status_code=400, detail="Invalid or expired invite")
        try:
            user = db.create_user(body.username, body.email, body.password, invite["role"])
        except AuthError as exc:
            db.restore_invite(body.invite_token)   # release the claim on failure
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        db.set_invite_used_by(body.invite_token, user["id"])
        db.audit("register", user_id=user["id"], ip=_client_ip(request), detail=invite["role"])
        return _token_response(user)

    @router.post("/request-invite", status_code=202)
    def request_invite(body: RequestInviteIn, request: Request) -> dict:
        if not _invite_req_limiter.allow(_client_ip(request) or "unknown"):
            raise HTTPException(status_code=429, detail="Too many requests. Try again later.")
        # Deduped server-side; identical response whether or not the email is known.
        db.create_registration_request(body.email, body.reason)
        return {"status": "pending"}

    # ── authenticated ───────────────────────────────────────────────────────────
    @router.get("/me", response_model=UserOut)
    def me(user: dict = Depends(get_current_user)) -> UserOut:
        return UserOut(id=user["id"], username=user["username"],
                       email=user["email"], role=user["role"])

    @router.post("/logout")
    def logout(user: dict = Depends(get_current_user)) -> dict:
        # Stateless JWT: client discards the token. Recorded for the audit trail.
        db.audit("logout", user_id=user["id"])
        return {"ok": True}

    # ── admin: invites ────────────────────────────────────────────────────────
    @router.get("/invites")
    def list_invites(_: dict = Depends(require_permission("admin.invite"))) -> list[dict]:
        return db.list_invites()

    @router.post("/invites", status_code=201)
    def create_invite(
        body: InviteCreateIn, admin: dict = Depends(require_permission("admin.invite")),
    ) -> dict:
        invite = db.create_invite(
            role=body.role, created_by=admin["id"],
            expires_hours=body.expires_hours, one_time=body.one_time,
        )
        db.audit("invite.create", user_id=admin["id"], detail=body.role.value)
        return invite

    @router.delete("/invites/{token}")
    def revoke_invite(
        token: str, admin: dict = Depends(require_permission("admin.invite")),
    ) -> dict:
        db.revoke_invite(token)
        db.audit("invite.revoke", user_id=admin["id"], detail=token[:8])
        return {"ok": True}

    # ── admin: registration requests ─────────────────────────────────────────────
    @router.get("/requests")
    def list_requests(
        status: str | None = None, _: dict = Depends(require_permission("admin.users")),
    ) -> list[dict]:
        return db.list_registration_requests(status)

    @router.post("/requests/{request_id}/approve")
    def approve_request(
        request_id: int, body: ApproveRequestIn,
        admin: dict = Depends(require_permission("admin.users")),
    ) -> dict:
        # Flip pending->approved first; only mint an invite if we actually moved it
        # (so replaying approve can't generate a fresh invite each call).
        if not db.resolve_request_if_pending(request_id, "approved"):
            raise HTTPException(status_code=409, detail="Request is not pending")
        invite = db.create_invite(
            role=body.role, created_by=admin["id"], expires_hours=body.expires_hours,
        )
        db.audit("request.approve", user_id=admin["id"], detail=str(request_id))
        return {"status": "approved", "invite": invite}

    @router.post("/requests/{request_id}/reject")
    def reject_request(
        request_id: int, admin: dict = Depends(require_permission("admin.users")),
    ) -> dict:
        if not db.resolve_request_if_pending(request_id, "rejected"):
            raise HTTPException(status_code=409, detail="Request is not pending")
        db.audit("request.reject", user_id=admin["id"], detail=str(request_id))
        return {"status": "rejected"}

    # ── admin: users ──────────────────────────────────────────────────────────
    @router.get("/users")
    def list_users(_: dict = Depends(require_permission("admin.users"))) -> list[dict]:
        return db.list_users()

    @router.post("/users/{user_id}/status")
    def set_user_status(
        user_id: int, body: UserStatusIn,
        admin: dict = Depends(require_permission("admin.users")),
    ) -> dict:
        if user_id == admin["id"] and body.status == "disabled":
            raise HTTPException(status_code=400, detail="You cannot disable your own account")
        if not db.set_user_status(user_id, body.status):
            raise HTTPException(status_code=404, detail="User not found")
        db.audit("user.status", user_id=admin["id"], detail=f"{user_id}:{body.status}")
        return {"ok": True, "id": user_id, "status": body.status}

    return router
