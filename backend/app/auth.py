from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time

from .config import settings
from .models import SessionPrincipal, SessionRole


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _sign(payload_b64: str) -> str:
    digest = hmac.new(settings.secret_key.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256).digest()
    return _b64encode(digest)


def resolve_role(alias: str) -> SessionRole:
    return "admin" if alias in settings.admin_aliases else "player"


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return f"pbkdf2_sha256$200000${_b64encode(salt)}${_b64encode(digest)}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations_text, salt_b64, digest_b64 = stored_hash.split("$", 3)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    try:
        iterations = int(iterations_text)
    except ValueError:
        return False
    salt = _b64decode(salt_b64)
    expected = _b64decode(digest_b64)
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)


def require_admin_code(alias: str, admin_code: str | None) -> None:
    if alias not in settings.admin_aliases:
        return
    if admin_code != settings.admin_access_code:
        raise PermissionError("Admin access requires the configured secret code")


def issue_token(alias: str) -> str:
    """Return an HMAC-signed token binding a player alias to the server secret.

    Format: <base64url(payload)>.<base64url(hmac-sha256)>. Stateless — no DB row needed.
    """
    payload = json.dumps({"alias": alias, "role": resolve_role(alias), "ts": int(time.time())}, separators=(",", ":"))
    payload_b64 = _b64encode(payload.encode("utf-8"))
    return f"{payload_b64}.{_sign(payload_b64)}"


def read_token(token: str | None) -> SessionPrincipal | None:
    """Verify a token's signature and return the signed session principal."""
    if not token or "." not in token:
        return None
    payload_b64, _, signature = token.partition(".")
    expected = _sign(payload_b64)
    # Constant-time comparison defends against timing attacks on the signature.
    if not hmac.compare_digest(expected, signature):
        return None
    try:
        data = json.loads(_b64decode(payload_b64))
    except (ValueError, json.JSONDecodeError):
        return None
    alias = data.get("alias")
    if not isinstance(alias, str) or not alias:
        return None
    role = data.get("role")
    if role not in {"player", "admin"}:
        role = resolve_role(alias)
    return SessionPrincipal(alias=alias, role=role)
