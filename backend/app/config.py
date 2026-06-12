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
    ai_provider: str = os.getenv("INVESTIGATION_AI_PROVIDER", "ollama")
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY")
    gemini_chat_model: str = os.getenv("GEMINI_CHAT_MODEL", "gemini-2.5-flash-lite")
    gemini_embed_model: str = os.getenv("GEMINI_EMBED_MODEL", "gemini-embedding-001")
    ai_failure_threshold: int = int(os.getenv("INVESTIGATION_AI_FAILURE_THRESHOLD", "3"))
    ai_circuit_seconds: int = int(os.getenv("INVESTIGATION_AI_CIRCUIT_SECONDS", "30"))
    session_ttl_seconds: int = int(os.getenv("INVESTIGATION_SESSION_TTL_SECONDS", "604800"))
    secure_cookies: bool = os.getenv("INVESTIGATION_SECURE_COOKIES", "false").lower() in {"1", "true", "yes"}
    rate_limits_enabled: bool = os.getenv("INVESTIGATION_RATE_LIMITS_ENABLED", "false").lower() in {"1", "true", "yes"}
    auth_rate_limit: int = int(os.getenv("INVESTIGATION_AUTH_RATE_LIMIT", "5"))
    dialogue_rate_limit: int = int(os.getenv("INVESTIGATION_DIALOGUE_RATE_LIMIT", "20"))
    generation_rate_limit: int = int(os.getenv("INVESTIGATION_GENERATION_RATE_LIMIT", "5"))
    max_drafts_per_player: int = int(os.getenv("INVESTIGATION_MAX_DRAFTS_PER_PLAYER", "5"))
    max_upload_bytes: int = int(os.getenv("INVESTIGATION_MAX_UPLOAD_BYTES", str(5 * 1024 * 1024)))
    max_draft_asset_bytes: int = int(os.getenv("INVESTIGATION_MAX_DRAFT_ASSET_BYTES", str(25 * 1024 * 1024)))
    r2_endpoint_url: str | None = os.getenv("R2_ENDPOINT_URL")
    r2_access_key_id: str | None = os.getenv("R2_ACCESS_KEY_ID")
    r2_secret_access_key: str | None = os.getenv("R2_SECRET_ACCESS_KEY")
    r2_bucket: str | None = os.getenv("R2_BUCKET")
    r2_public_base_url: str | None = os.getenv("R2_PUBLIC_BASE_URL")
    bootstrap_admin_aliases: tuple[str, ...] = tuple(
        o.strip()
        for o in os.getenv("INVESTIGATION_BOOTSTRAP_ADMIN_ALIASES", "").split(",")
        if o.strip()
    )
    default_alias: str = "Consultant"
    secret_key: str = os.getenv("INVESTIGATION_SECRET_KEY", "dev-insecure-key")
    admin_aliases: tuple[str, ...] = tuple(
        o.strip()
        for o in os.getenv("INVESTIGATION_ADMIN_ALIASES", "Consultant,Admin").split(",")
        if o.strip()
    )
    cors_origins: tuple[str, ...] = tuple(
        o.strip()
        for o in os.getenv(
            "INVESTIGATION_CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173",
        ).split(",")
        if o.strip()
    )


settings = Settings()
