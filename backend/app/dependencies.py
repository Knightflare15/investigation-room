from __future__ import annotations

from functools import lru_cache

from fastapi import Header, HTTPException

from .auth import read_token
from .config import settings
from .services.authoring import AuthoringService
from .services.game import GameService


@lru_cache(maxsize=1)
def get_game_service() -> GameService:
    return GameService(settings)


@lru_cache(maxsize=1)
def get_authoring_service() -> AuthoringService:
    return AuthoringService(settings.cases_path)


def get_player(authorization: str | None = Header(default=None)) -> str:
    """Resolve the player alias from a signed bearer token.

    Raises 401 if the Authorization header is missing or the token fails signature
    verification. Replaces the old spoofable X-Player-Alias header.
    """
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    alias = read_token(token)
    if alias is None:
        raise HTTPException(status_code=401, detail="Missing or invalid session token")
    return alias
