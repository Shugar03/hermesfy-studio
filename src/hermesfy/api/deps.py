"""FastAPI dependency injection for Hermesfy V5.

Provides: get_settings, get_db, require_auth.
"""

from __future__ import annotations

from typing import AsyncGenerator
import hmac

import aiosqlite
from fastapi import Depends, Header

from hermesfy.api.errors import AuthError
from hermesfy.api.settings import Settings, get_settings


async def get_db(
    settings: Settings = Depends(get_settings),
) -> AsyncGenerator[aiosqlite.Connection, None]:
    """Yield an aiosqlite connection using the configured DB path with WAL mode.

    The connection is opened on each request and closed afterwards — this is
    safe for WAL mode SQLite with concurrent short-lived connections.
    """
    db_path = settings.resolved_db_path
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    try:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA busy_timeout=5000")
        await db.execute("PRAGMA foreign_keys=ON")
        yield db
    finally:
        await db.close()


async def maybe_auth(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> str | None:
    """Return the auth token string if one is configured and the request provides it.

    If settings.auth_token is None, authentication is skipped (dev mode).
    If auth_token is set, the request must include a matching Bearer token.
    """
    if settings.auth_token is None:
        return None  # auth disabled

    if authorization is None or not authorization.startswith("Bearer "):
        raise AuthError("Missing or invalid Authorization header")

    token = authorization.removeprefix("Bearer ").strip()
    if not hmac.compare_digest(token, settings.auth_token):
        raise AuthError("Invalid auth token")

    return token


def require_auth(auth: str | None = Depends(maybe_auth)) -> None:
    """Dependency that enforces authentication (raises AuthError if not authed)."""
    # The maybe_auth dependency already raises AuthError if auth is required
    # but missing/invalid. This is a no-op dependency marker for routes.
    return None
