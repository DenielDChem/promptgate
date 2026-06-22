"""Password hashing (bcrypt) and JWT (HS256) helpers.

Uses the ``bcrypt`` library directly (not passlib, which is incompatible with
bcrypt >= 4.1). The signing secret comes from ``PROMPTGATE_JWT_SECRET`` if set,
otherwise a random secret is generated once and persisted to
``~/.promptgate/.jwt_secret`` (chmod 600) so tokens survive restarts.
"""
from __future__ import annotations

import os
import secrets
import time
from pathlib import Path

import bcrypt
import jwt
from loguru import logger

_SECRET_FILE = Path.home() / ".promptgate" / ".jwt_secret"
_ALGO = "HS256"
_BCRYPT_MAX_BYTES = 72  # bcrypt silently ignores bytes past 72; truncate explicitly


def _pw_bytes(password: str) -> bytes:
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    """Return a bcrypt hash (utf-8 str) for ``password``."""
    return bcrypt.hashpw(_pw_bytes(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, pw_hash: str) -> bool:
    """Constant-time check of ``password`` against a stored bcrypt hash."""
    try:
        return bcrypt.checkpw(_pw_bytes(password), pw_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# Fixed dummy hash so login can spend the same bcrypt cost whether or not the
# username exists — defeats user-enumeration via response timing.
_DUMMY_HASH = bcrypt.hashpw(b"pgate-timing-equalizer", bcrypt.gensalt()).decode("utf-8")


def dummy_verify(password: str) -> None:
    """Run a throwaway bcrypt comparison to equalize timing on the no-user path."""
    verify_password(password, _DUMMY_HASH)


def get_secret() -> str:
    """Return the JWT signing secret, creating & persisting one on first use."""
    env = os.environ.get("PROMPTGATE_JWT_SECRET")
    if env:
        return env
    if _SECRET_FILE.exists():
        existing = _SECRET_FILE.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    secret = secrets.token_urlsafe(48)
    _SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        _SECRET_FILE.parent.chmod(0o700)
    except OSError:
        logger.warning("Could not chmod 700 {} — check directory permissions", _SECRET_FILE.parent)
    _SECRET_FILE.write_text(secret, encoding="utf-8")
    try:
        _SECRET_FILE.chmod(0o600)
    except OSError:
        logger.warning("Could not chmod 600 {} — JWT secret may be world-readable. "
                       "Set PROMPTGATE_JWT_SECRET in production.", _SECRET_FILE)
    return secret


def create_access_token(sub: str, role: str, expires_hours: int = 24) -> str:
    """Mint a signed JWT carrying the user id (``sub``) and ``role``."""
    now = int(time.time())
    payload = {"sub": str(sub), "role": role, "iat": now, "exp": now + expires_hours * 3600}
    return jwt.encode(payload, get_secret(), algorithm=_ALGO)


def decode_token(token: str) -> dict:
    """Decode & verify a JWT. Raises ``jwt.PyJWTError`` on invalid/expired token."""
    return jwt.decode(token, get_secret(), algorithms=[_ALGO])
