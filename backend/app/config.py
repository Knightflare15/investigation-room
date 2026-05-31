from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    app_name: str = "Investigation Room API"
    database_url: str | None = os.getenv("INVESTIGATION_DATABASE_URL")
    db_path: Path = Path(os.getenv("INVESTIGATION_DB_PATH", "backend/data/investigation_room.db"))
    cases_path: Path = Path("cases")
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    ollama_chat_model: str = os.getenv("OLLAMA_CHAT_MODEL", "llama3.1:8b")
    ollama_embed_model: str = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
    default_alias: str = "Consultant"
    cors_origins: tuple[str, ...] = tuple(
        o.strip()
        for o in os.getenv("INVESTIGATION_CORS_ORIGINS", "http://localhost:5173").split(",")
        if o.strip()
    )


settings = Settings()
