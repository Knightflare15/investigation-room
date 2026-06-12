from __future__ import annotations

from functools import lru_cache

import time

from fastapi import Cookie, Header, HTTPException

from .auth import token_hash
from .config import settings
from .models import SessionPrincipal
from .services.accounts import AuthService
from .services.authoring import AuthoringService
from .services.game import GameService


@lru_cache(maxsize=1)
def get_game_service() -> GameService:
    return GameService(settings)


@lru_cache(maxsize=1)
def get_authoring_service() -> AuthoringService:
    return AuthoringService(settings.cases_path)


@lru_cache(maxsize=1)
def get_auth_service() -> AuthService:
    return AuthService(settings)


def get_player(
    authorization: str | None = Header(default=None),
    investigation_session: str | None = Cookie(default=None),
) -> SessionPrincipal:
    """Resolve the player from an expiring opaque cookie or bearer session."""
    token = investigation_session
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing or invalid session token")
    session = get_auth_service().db.load_session(token_hash(token), int(time.time()))
    if session is None:
        raise HTTPException(status_code=401, detail="Session user no longer exists")
    user = get_auth_service().db.load_auth_user(session.alias)
    if user is None or user.id != session.user_id:
        raise HTTPException(status_code=401, detail="Session user no longer exists")
    return SessionPrincipal(user_id=user.id, alias=user.alias, role=user.role)
