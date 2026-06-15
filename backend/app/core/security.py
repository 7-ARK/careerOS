"""Password hashing and compact HS256 JWT helpers."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID


class InvalidTokenError(ValueError):
    """Raised when a bearer token cannot be trusted."""


def hash_password(password: str) -> str:
    """Hash a password with a random salt using scrypt."""
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=64)
    return f"scrypt$16384$8$1${_encode(salt)}${_encode(derived)}"


def verify_password(password: str, password_hash: str) -> bool:
    """Compare a password against a stored scrypt hash."""
    try:
        algorithm, n, r, p, salt, expected = password_hash.split("$", 5)
        if algorithm != "scrypt":
            return False
        derived = hashlib.scrypt(
            password.encode(),
            salt=_decode(salt),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(_decode(expected)),
        )
        return hmac.compare_digest(derived, _decode(expected))
    except (ValueError, TypeError):
        return False


def create_access_token(
    user_id: UUID,
    *,
    secret_key: str,
    algorithm: str = "HS256",
    expires_minutes: int = 1440,
) -> str:
    """Create a signed JWT containing the user ID and expiration time."""
    _require_hs256(algorithm)
    now = datetime.now(UTC)
    header = {"alg": algorithm, "typ": "JWT"}
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=expires_minutes)).timestamp()),
    }
    unsigned = f"{_json_segment(header)}.{_json_segment(payload)}"
    signature = hmac.new(secret_key.encode(), unsigned.encode(), hashlib.sha256).digest()
    return f"{unsigned}.{_encode(signature)}"


def decode_access_token(
    token: str,
    *,
    secret_key: str,
    algorithm: str = "HS256",
) -> UUID:
    """Verify a JWT signature and return its unexpired user ID."""
    _require_hs256(algorithm)
    try:
        header_segment, payload_segment, signature_segment = token.split(".")
        unsigned = f"{header_segment}.{payload_segment}"
        expected = hmac.new(secret_key.encode(), unsigned.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _decode(signature_segment)):
            raise InvalidTokenError("invalid token signature")
        header = json.loads(_decode(header_segment))
        payload = json.loads(_decode(payload_segment))
        if header.get("alg") != algorithm or header.get("typ") != "JWT":
            raise InvalidTokenError("invalid token header")
        if int(payload["exp"]) <= int(datetime.now(UTC).timestamp()):
            raise InvalidTokenError("token has expired")
        return UUID(payload["sub"])
    except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
        if isinstance(exc, InvalidTokenError):
            raise
        raise InvalidTokenError("invalid access token") from exc


def _json_segment(value: dict[str, object]) -> str:
    return _encode(json.dumps(value, separators=(",", ":"), sort_keys=True).encode())


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _require_hs256(algorithm: str) -> None:
    if algorithm != "HS256":
        raise ValueError("careerOS MVP authentication supports only HS256")
