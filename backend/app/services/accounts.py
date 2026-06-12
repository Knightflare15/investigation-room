from __future__ import annotations

import time
import uuid

from ..auth import hash_password, issue_token, needs_password_rehash, resolve_role, token_hash, verify_password
from ..config import Settings
from ..database import create_database
from ..models import AuthUserRecord, SessionRecord, SessionResponse


class AuthService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.db = create_database(settings.database_url, settings.db_path)

    def register(self, alias: str, password: str) -> SessionResponse:
        clean_alias = alias.strip()
        if not clean_alias:
            raise ValueError("Alias is required")
        if len(password) < 10:
            raise ValueError("Password must be at least 10 characters")
        if self.db.load_auth_user(clean_alias) is not None:
            raise ValueError("Alias is already registered")
        user = AuthUserRecord(
            id=str(uuid.uuid4()),
            alias=clean_alias,
            password_hash=hash_password(password),
            role=resolve_role(clean_alias),
        )
        self.db.create_auth_user(user)
        self.db.write_audit_log(clean_alias, "account.registered", user.id, {"role": user.role})
        return self._issue_session(user)

    def login(self, alias: str, password: str) -> SessionResponse:
        clean_alias = alias.strip()
        if not clean_alias or not password:
            raise ValueError("Alias and password are required")
        user = self.db.load_auth_user(clean_alias)
        if user is None or not verify_password(password, user.password_hash):
            raise PermissionError("Invalid alias or password")
        if needs_password_rehash(user.password_hash):
            self.db.update_auth_password(clean_alias, hash_password(password))
        return self._issue_session(user)

    def _issue_session(self, user: AuthUserRecord) -> SessionResponse:
        token = issue_token()
        self.db.create_session(
            SessionRecord(
                token_hash=token_hash(token),
                user_id=user.id,
                alias=user.alias,
                role=user.role,
                expires_at=int(time.time()) + self.settings.session_ttl_seconds,
            )
        )
        return SessionResponse(token=token, alias=user.alias, role=user.role)

    def revoke(self, token: str) -> None:
        self.db.revoke_session(token_hash(token))
