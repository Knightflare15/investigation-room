from __future__ import annotations

from functools import lru_cache

from fastapi import Header

from .config import settings
from .services.authoring import AuthoringService
from .services.game import GameService


@lru_cache(maxsize=1)
def get_game_service() -> GameService:
    return GameService(settings)


@lru_cache(maxsize=1)
def get_authoring_service() -> AuthoringService:
    return AuthoringService(settings.cases_path)


def get_alias(x_player_alias: str | None = Header(default=None)) -> str:
    return x_player_alias or settings.default_alias
