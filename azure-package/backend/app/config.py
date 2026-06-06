from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CASES_PATH = REPO_ROOT / "cases"
DEFAULT_FRONTEND_DIST_PATH = REPO_ROOT / "frontend" / "dist"


@dataclass(frozen=True)
class Settings:
    app_name: str = "Investigation Room API"
    database_url: str | None = os.getenv("INVESTIGATION_DATABASE_URL")
    db_path: Path = Path(os.getenv("INVESTIGATION_DB_PATH", "backend/data/investigation_room.db"))
    bundled_cases_path: Path = Path(os.getenv("INVESTIGATION_BUNDLED_CASES_PATH", str(DEFAULT_CASES_PATH)))
    cases_path: Path = Path(os.getenv("INVESTIGATION_CASES_PATH", str(DEFAULT_CASES_PATH)))
    frontend_dist_path: Path = Path(os.getenv("INVESTIGATION_FRONTEND_DIST_PATH", str(DEFAULT_FRONTEND_DIST_PATH)))
    seed_cases_on_start: bool = os.getenv("INVESTIGATION_SEED_CASES_ON_START", "true").lower() in {"1", "true", "yes"}
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    ollama_chat_model: str = os.getenv("OLLAMA_CHAT_MODEL", "llama3.1:8b")
    ollama_embed_model: str = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
    ollama_chat_timeout_seconds: int = int(os.getenv("OLLAMA_CHAT_TIMEOUT_SECONDS", "45"))
    ollama_stream_timeout_seconds: int = int(os.getenv("OLLAMA_STREAM_TIMEOUT_SECONDS", "60"))
    default_alias: str = "Consultant"
    secret_key: str = os.getenv("INVESTIGATION_SECRET_KEY", "dev-insecure-key")
    admin_access_code: str = os.getenv("INVESTIGATION_ADMIN_ACCESS_CODE", "change-me")
    admin_aliases: tuple[str, ...] = tuple(
        o.strip()
        for o in os.getenv("INVESTIGATION_ADMIN_ALIASES", "Consultant,Admin").split(",")
        if o.strip()
    )
    cors_origins: tuple[str, ...] = tuple(
        o.strip()
        for o in os.getenv("INVESTIGATION_CORS_ORIGINS", "http://localhost:5173").split(",")
        if o.strip()
    )


settings = Settings()
