from __future__ import annotations

from functools import lru_cache

from fastapi import Header, HTTPException

from .auth import read_token
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


def get_player(authorization: str | None = Header(default=None)) -> SessionPrincipal:
    """Resolve the player alias from a signed bearer token.

    Raises 401 if the Authorization header is missing or the token fails signature
    verification. Replaces the old spoofable X-Player-Alias header.
    """
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    player = read_token(token)
    if player is None:
        raise HTTPException(status_code=401, detail="Missing or invalid session token")
    if get_auth_service().db.load_auth_user(player.alias) is None:
        raise HTTPException(status_code=401, detail="Session user no longer exists")
    return player
