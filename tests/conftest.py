"""Shared pytest fixtures."""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _reset_rate_limiters():
    """Isolate the per-process auth rate limiters between tests.

    They are module-level singletons, so without this an earlier test's
    attempts would bleed into a later one. No-op if auth deps aren't installed.
    """
    try:
        from promptgate.auth import router as _r
    except Exception:
        yield
        return
    _r._login_limiter.clear()
    _r._invite_req_limiter.clear()
    yield
