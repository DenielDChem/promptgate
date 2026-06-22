"""Data access for users, invites, registration requests, and the audit log.

Plain sqlite3 over the same database file the rest of pgate uses. Tables are
created by :mod:`promptgate.migrations` (migration ``0001_auth``).
"""
from __future__ import annotations

import secrets
import sqlite3
import time
from pathlib import Path
from typing import Any

from promptgate.auth.roles import Role
from promptgate.auth.security import hash_password


def _connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _public(row: sqlite3.Row) -> dict[str, Any]:
    """User dict without the password hash / totp secret."""
    return {
        "id": row["id"],
        "username": row["username"],
        "email": row["email"],
        "role": row["role"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


class AuthError(ValueError):
    """Raised for expected auth-data conflicts (duplicate user, bad invite…)."""


class AuthDB:
    """Thin repository over the auth tables. One instance per request is fine."""

    def __init__(self, db_path: str | Path) -> None:
        self._path = db_path

    # ── users ────────────────────────────────────────────────────────────────
    def count_users(self) -> int:
        with _connect(self._path) as c:
            return int(c.execute("SELECT COUNT(*) FROM users").fetchone()[0])

    def get_user_by_username(self, username: str) -> dict | None:
        with _connect(self._path) as c:
            row = c.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            return dict(row) if row else None

    def get_user_by_id(self, user_id: int) -> dict | None:
        with _connect(self._path) as c:
            row = c.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            return dict(row) if row else None

    def create_user(self, username: str, email: str, password: str, role: "Role | str") -> dict:
        role = Role(role).value
        now = int(time.time())
        try:
            with _connect(self._path) as c:
                cur = c.execute(
                    "INSERT INTO users (username, email, pw_hash, role, status, created_at) "
                    "VALUES (?, ?, ?, ?, 'active', ?)",
                    (username, email, hash_password(password), role, now),
                )
                row = c.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()
        except sqlite3.IntegrityError as exc:
            raise AuthError("Username or email already taken") from exc
        return _public(row)

    # ── invites ──────────────────────────────────────────────────────────────
    def create_invite(
        self, role: "Role | str", created_by: int | None,
        expires_hours: int | None = 720, one_time: bool = True,
    ) -> dict:
        role = Role(role).value
        token = secrets.token_urlsafe(24)
        now = int(time.time())
        expires_at = now + expires_hours * 3600 if expires_hours else None
        with _connect(self._path) as c:
            c.execute(
                "INSERT INTO invites (token, role, expires_at, one_time, created_by, created_at, status) "
                "VALUES (?, ?, ?, ?, ?, ?, 'active')",
                (token, role, expires_at, 1 if one_time else 0, created_by, now),
            )
        return {"token": token, "role": role, "expires_at": expires_at, "one_time": one_time}

    def get_invite(self, token: str) -> dict | None:
        with _connect(self._path) as c:
            row = c.execute("SELECT * FROM invites WHERE token = ?", (token,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def invite_is_valid(invite: dict | None) -> bool:
        if not invite or invite["status"] != "active":
            return False
        if invite["expires_at"] is not None and invite["expires_at"] < int(time.time()):
            return False
        return True

    def claim_invite(self, token: str) -> dict | None:
        """Atomically reserve an invite for registration.

        For a one-time invite, transitions ``active -> used`` in a single
        conditional UPDATE and returns the invite only if THIS call won the
        race (prevents two concurrent registrations minting two accounts from
        one invite). For a multi-use invite, returns it if still valid.
        Returns ``None`` if invalid/expired/already used.

        On success the caller must follow up with :meth:`set_invite_used_by`
        once the user exists, or :meth:`restore_invite` if creation fails.
        """
        now = int(time.time())
        with _connect(self._path) as c:
            row = c.execute("SELECT * FROM invites WHERE token = ?", (token,)).fetchone()
            invite = dict(row) if row else None
            if not self.invite_is_valid(invite):
                return None
            if invite["one_time"]:
                cur = c.execute(
                    "UPDATE invites SET status='used', used_at=? "
                    "WHERE token=? AND status='active'",
                    (now, token),
                )
                if cur.rowcount != 1:
                    return None  # lost the race
            return invite

    def set_invite_used_by(self, token: str, user_id: int) -> None:
        with _connect(self._path) as c:
            c.execute("UPDATE invites SET used_by=? WHERE token=?", (user_id, token))

    def restore_invite(self, token: str) -> None:
        """Undo a one-time claim if registration failed before a user was linked."""
        with _connect(self._path) as c:
            c.execute(
                "UPDATE invites SET status='active', used_at=NULL "
                "WHERE token=? AND status='used' AND used_by IS NULL",
                (token,),
            )

    def list_invites(self) -> list[dict]:
        with _connect(self._path) as c:
            return [dict(r) for r in c.execute("SELECT * FROM invites ORDER BY created_at DESC")]

    def revoke_invite(self, token: str) -> None:
        with _connect(self._path) as c:
            c.execute("UPDATE invites SET status='revoked' WHERE token=? AND status='active'", (token,))

    # ── registration requests ─────────────────────────────────────────────────
    def create_registration_request(self, email: str, reason: str) -> dict:
        """Insert a pending request, deduping by email (one pending per email).

        Returns the existing row if a pending request already exists, so the
        caller can respond identically and not leak whether the email is known.
        """
        now = int(time.time())
        with _connect(self._path) as c:
            existing = c.execute(
                "SELECT * FROM registration_requests WHERE email=? AND status='pending'",
                (email,),
            ).fetchone()
            if existing:
                return dict(existing)
            cur = c.execute(
                "INSERT INTO registration_requests (email, reason, status, created_at) "
                "VALUES (?, ?, 'pending', ?)",
                (email, reason, now),
            )
            row = c.execute(
                "SELECT * FROM registration_requests WHERE id = ?", (cur.lastrowid,)
            ).fetchone()
        return dict(row)

    def list_registration_requests(self, status: str | None = None) -> list[dict]:
        with _connect(self._path) as c:
            if status:
                rows = c.execute(
                    "SELECT * FROM registration_requests WHERE status=? ORDER BY created_at DESC",
                    (status,),
                )
            else:
                rows = c.execute(
                    "SELECT * FROM registration_requests ORDER BY created_at DESC"
                )
            return [dict(r) for r in rows]

    def resolve_request_if_pending(self, request_id: int, status: str) -> bool:
        """Transition a request pending -> status atomically.

        Returns True only if THIS call moved it (guards against replay that
        would otherwise mint a fresh invite on every approve call).
        """
        with _connect(self._path) as c:
            cur = c.execute(
                "UPDATE registration_requests SET status=? WHERE id=? AND status='pending'",
                (status, request_id),
            )
            return cur.rowcount == 1

    # ── user administration ─────────────────────────────────────────────────────
    def list_users(self) -> list[dict]:
        with _connect(self._path) as c:
            return [_public(r) for r in c.execute("SELECT * FROM users ORDER BY created_at")]

    def set_user_status(self, user_id: int, status: str) -> bool:
        """Enable/disable a user. A disabled user's tokens stop working on their
        next request (get_current_user rejects status != 'active')."""
        if status not in ("active", "disabled"):
            raise AuthError("status must be 'active' or 'disabled'")
        with _connect(self._path) as c:
            cur = c.execute("UPDATE users SET status=? WHERE id=?", (status, user_id))
            return cur.rowcount == 1

    # ── audit ──────────────────────────────────────────────────────────────────
    def audit(self, event: str, user_id: int | None = None,
              ip: str | None = None, detail: str | None = None) -> None:
        with _connect(self._path) as c:
            c.execute(
                "INSERT INTO audit_log (ts, event, user_id, ip, detail) VALUES (?, ?, ?, ?, ?)",
                (int(time.time()), event, user_id, ip, detail),
            )
