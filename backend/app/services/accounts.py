from __future__ import annotations

from ..auth import hash_password, issue_token, read_token, require_admin_code, verify_password
from ..config import Settings
from ..database import create_database
from ..models import AuthUserRecord, SessionResponse


class AuthService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.db = create_database(settings.database_url, settings.db_path)

    def register(self, alias: str, password: str, admin_code: str | None = None) -> SessionResponse:
        clean_alias = alias.strip()
        if not clean_alias:
            raise ValueError("Alias is required")
        if len(password) < 6:
            raise ValueError("Password must be at least 6 characters")
        if self.db.load_auth_user(clean_alias) is not None:
            raise ValueError("Alias is already registered")
        require_admin_code(clean_alias, admin_code)
        self.db.create_auth_user(AuthUserRecord(alias=clean_alias, password_hash=hash_password(password)))
        return self._issue_session(clean_alias)

    def login(self, alias: str, password: str, admin_code: str | None = None) -> SessionResponse:
        clean_alias = alias.strip()
        if not clean_alias or not password:
            raise ValueError("Alias and password are required")
        user = self.db.load_auth_user(clean_alias)
        if user is None or not verify_password(password, user.password_hash):
            raise PermissionError("Invalid alias or password")
        require_admin_code(clean_alias, admin_code)
        return self._issue_session(clean_alias)

    def _issue_session(self, alias: str) -> SessionResponse:
        token = issue_token(alias)
        principal = read_token(token)
        if principal is None:
            raise RuntimeError("Failed to issue session token")
        return SessionResponse(token=token, alias=principal.alias, role=principal.role)
