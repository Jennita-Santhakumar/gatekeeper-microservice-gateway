"""JWT issuance/verification and password hashing for the gateway's local auth table.

Uses PyJWT for tokens (HS256, configurable secret/expiry, unique `jti` per token)
and passlib[bcrypt] for password hashing. `require_auth` is a Flask decorator that
validates the `Authorization: Bearer <token>` header and attaches the decoded
identity to `flask.g.user` (and `flask.g.user_id`) for downstream handlers.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta
from functools import wraps
from typing import Any

import jwt
from flask import g, jsonify, request
from passlib.context import CryptContext

JWT_SECRET = os.getenv("JWT_SECRET", "dev-insecure-secret-change-me")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRY_MINUTES = int(os.getenv("JWT_EXPIRY_MINUTES", "60"))

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return _pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    try:
        return _pwd_context.verify(password, hashed)
    except (ValueError, TypeError):
        return False


def create_access_token(
    user_id: int | str,
    email: str | None = None,
    expiry_minutes: int | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Create a signed JWT access token for a user.

    Includes standard claims (`sub`, `iat`, `exp`) plus a unique `jti` so each
    issued token can be individually identified/revoked if needed later.
    """
    now = datetime.now(UTC)
    expiry = expiry_minutes if expiry_minutes is not None else JWT_EXPIRY_MINUTES
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "iat": now,
        "exp": now + timedelta(minutes=expiry),
        "jti": str(uuid.uuid4()),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


class TokenError(Exception):
    """Raised when a token is missing, malformed, expired, or invalid."""


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT, raising TokenError on any failure."""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("Token has expired") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError("Invalid token") from exc


def require_auth(view_func):
    """Flask route decorator enforcing a valid `Authorization: Bearer <jwt>` header.

    On success, attaches the decoded claims to `flask.g.user` and the subject
    (user id) to `flask.g.user_id`.
    """

    @wraps(view_func)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or malformed Authorization header"}), 401

        token = auth_header[len("Bearer "):].strip()
        if not token:
            return jsonify({"error": "Missing bearer token"}), 401

        try:
            claims = decode_token(token)
        except TokenError as exc:
            return jsonify({"error": str(exc)}), 401

        g.user = claims
        g.user_id = claims.get("sub")
        return view_func(*args, **kwargs)

    return wrapper
