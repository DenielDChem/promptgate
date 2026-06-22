"""Pydantic request/response models for the auth API."""
from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

from promptgate.auth.roles import Role

_USERNAME = r"^[A-Za-z0-9_.-]{3,32}$"


class LoginIn(BaseModel):
    username: str
    password: str


class RegisterIn(BaseModel):
    invite_token: str
    username: str = Field(pattern=_USERNAME)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class RequestInviteIn(BaseModel):
    email: EmailStr
    reason: str = Field(default="", max_length=500)


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    role: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# expiry capped at 1 year; None = never-expiring (discouraged for privileged roles)
_EXPIRES = Field(default=720, ge=1, le=8760)


class InviteCreateIn(BaseModel):
    role: Role = Role.prompter
    expires_hours: int | None = _EXPIRES   # 30 days default
    one_time: bool = True


class ApproveRequestIn(BaseModel):
    role: Role = Role.prompter
    expires_hours: int | None = _EXPIRES


class UserStatusIn(BaseModel):
    status: str = Field(pattern=r"^(active|disabled)$")
