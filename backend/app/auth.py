from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from .config import settings


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _sign(payload_b64: str) -> str:
    digest = hmac.new(settings.secret_key.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256).digest()
    return _b64encode(digest)


def issue_token(alias: str) -> str:
    """Return an HMAC-signed token binding a player alias to the server secret.

    Format: <base64url(payload)>.<base64url(hmac-sha256)>. Stateless — no DB row needed.
    """
    payload = json.dumps({"alias": alias, "ts": int(time.time())}, separators=(",", ":"))
    payload_b64 = _b64encode(payload.encode("utf-8"))
    return f"{payload_b64}.{_sign(payload_b64)}"


def read_token(token: str | None) -> str | None:
    """Verify a token's signature and return its alias, or None if missing/invalid/tampered."""
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
    return alias if isinstance(alias, str) and alias else None
