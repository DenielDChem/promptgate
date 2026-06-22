"""Roles and the RBAC permission matrix.

Mirrors docs/PLATFORM_ARCHITECTURE.md §12. Permissions are coarse strings;
:func:`can` is the single source of truth for "may this role do X?".
"""
from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    admin = "admin"
    prompter = "prompter"      # Промтолог
    validator = "validator"
    guest = "guest"


# permission -> set of roles that hold it
_MATRIX: dict[str, set[Role]] = {
    "prompt.view_own":   {Role.admin, Role.prompter, Role.validator, Role.guest},
    "prompt.view_all":   {Role.admin},
    "prompt.create":     {Role.admin, Role.prompter},
    "prompt.edit_own":   {Role.admin, Role.prompter},
    "prompt.edit_all":   {Role.admin},
    "prompt.delete_own": {Role.admin, Role.prompter},
    "prompt.publish":    {Role.admin, Role.prompter},
    "validate.run":      {Role.admin, Role.prompter, Role.validator},
    "template.manage":   {Role.admin, Role.prompter},
    "model.select":      {Role.admin, Role.prompter, Role.validator},
    "stats.view_own":    {Role.admin, Role.prompter},
    "admin.users":       {Role.admin},
    "admin.models":      {Role.admin},
    "admin.storage":     {Role.admin},
    "admin.env":         {Role.admin},
    "admin.queue":       {Role.admin},
    "admin.logs":        {Role.admin},
    "admin.invite":      {Role.admin},
}


def can(role: "Role | str", permission: str) -> bool:
    """Return True if ``role`` holds ``permission``.

    Unknown roles or permissions return False (deny by default).

    Examples:
        >>> can(Role.admin, "admin.users")
        True
        >>> can("guest", "prompt.create")
        False
        >>> can("nope", "prompt.view_own")
        False
    """
    try:
        role = Role(role)
    except ValueError:
        return False
    allowed = _MATRIX.get(permission)
    return bool(allowed and role in allowed)
