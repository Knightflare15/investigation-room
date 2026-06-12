from __future__ import annotations

import hashlib
import secrets

from .config import settings
from .models import SessionRole


def resolve_role(alias: str) -> SessionRole:
    admins = settings.bootstrap_admin_aliases or settings.admin_aliases
    return "admin" if alias in admins else "player"


def hash_password(password: str) -> str:
    try:
        from argon2 import PasswordHasher

        return PasswordHasher().hash(password)
    except ImportError:
        salt = secrets.token_bytes(16)
        digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
        return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    if stored_hash.startswith("$argon2"):
        try:
            from argon2 import PasswordHasher
            from argon2.exceptions import VerificationError

            return PasswordHasher().verify(stored_hash, password)
        except (ImportError, VerificationError):
            return False
    try:
        algorithm, salt_hex, digest_hex = stored_hash.split("$", 2)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except ValueError:
        return False
    if algorithm != "scrypt":
        return False
    actual = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return secrets.compare_digest(actual, expected)


def needs_password_rehash(stored_hash: str) -> bool:
    return not stored_hash.startswith("$argon2")


def issue_token(alias: str = "") -> str:
    """Return an opaque high-entropy token with no embedded identity."""
    return secrets.token_urlsafe(48)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def read_token(token: str | None):
    """Legacy API retained to fail closed; sessions resolve through the database."""
    return None
