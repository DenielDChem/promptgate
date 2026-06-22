"""FastAPI dependencies for authentication & RBAC.

Dependencies are built per-app via :func:`make_auth_deps` so the database path
captured in ``make_app`` is closed over (no global state).
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from promptgate.auth.db import AuthDB
from promptgate.auth.roles import can
from promptgate.auth.security import decode_token

_bearer = HTTPBearer(auto_error=False)


def make_auth_deps(db_path: str | Path):
    """Return ``(get_current_user, require_permission)`` bound to ``db_path``."""

    def get_current_user(
        creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    ) -> dict:
        if creds is None or not creds.credentials:
            raise HTTPException(status_code=401, detail="Not authenticated")
        try:
            payload = decode_token(creds.credentials)
        except jwt.PyJWTError:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        sub = payload.get("sub")
        user = AuthDB(db_path).get_user_by_id(int(sub)) if sub else None
        if not user or user.get("status") != "active":
            raise HTTPException(status_code=401, detail="User not found or inactive")
        return user

    def require_permission(permission: str) -> Callable[..., dict]:
        def _dep(user: dict = Depends(get_current_user)) -> dict:
            if not can(user["role"], permission):
                raise HTTPException(status_code=403, detail=f"Forbidden: requires '{permission}'")
            return user
        return _dep

    return get_current_user, require_permission
