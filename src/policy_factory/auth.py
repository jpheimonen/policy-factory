"""Authentication service — password hashing and JWT operations.

This module provides the auth business logic, separate from the store
layer (which handles persistence) and the router layer (which handles
HTTP). It contains:

- Password hashing and verification via bcrypt
- JWT creation and validation via PyJWT
- Configuration loading from environment variables
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

logger = logging.getLogger(__name__)

# --- Configuration ---

# JWT secret key — MUST be set in production.
# Loaded once at module level; the server should fail to start if missing.
JWT_SECRET_KEY: str | None = None
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24  # Default, overridable via env


def load_auth_config() -> None:
    """Load auth configuration from environment variables.

    Must be called during server startup. If JWT_SECRET_KEY is not set,
    a random key is auto-generated and a warning is logged. This is fine
    for development but means tokens won't survive server restarts.
    """
    global JWT_SECRET_KEY, JWT_EXPIRY_HOURS

    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
    if not JWT_SECRET_KEY:
        import secrets

        JWT_SECRET_KEY = secrets.token_hex(32)
        logger.warning(
            "JWT_SECRET_KEY not set — generated a random key. "
            "Tokens will not survive server restarts. "
            "Set JWT_SECRET_KEY in your .env for persistent sessions."
        )

    expiry_str = os.environ.get("JWT_EXPIRY_HOURS")
    if expiry_str:
        try:
            JWT_EXPIRY_HOURS = int(expiry_str)
        except ValueError:
            logger.warning(
                "Invalid JWT_EXPIRY_HOURS value '%s', using default %d",
                expiry_str,
                JWT_EXPIRY_HOURS,
            )


def _get_secret_key() -> str:
    """Get the JWT secret key, raising if not configured."""
    if JWT_SECRET_KEY is None:
        raise RuntimeError("Auth not configured — call load_auth_config() first")
    return JWT_SECRET_KEY


# --- Password Hashing ---


def hash_password(plaintext: str) -> str:
    """Hash a plaintext password using bcrypt.

    Args:
        plaintext: The plaintext password to hash.

    Returns:
        The bcrypt hash as a string.
    """
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(plaintext.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plaintext: str, hashed: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash.

    Args:
        plaintext: The plaintext password to verify.
        hashed: The stored bcrypt hash.

    Returns:
        True if the password matches, False otherwise.
    """
    return bcrypt.checkpw(plaintext.encode("utf-8"), hashed.encode("utf-8"))


# --- JWT Operations ---


@dataclass
class TokenPayload:
    """Decoded JWT payload."""

    user_id: str
    email: str
    role: str
    iat: datetime
    exp: datetime


def create_access_token(user_id: str, email: str, role: str) -> str:
    """Create a JWT access token.

    Args:
        user_id: The user's UUID.
        email: The user's email address.
        role: The user's role ("admin" or "user").

    Returns:
        The encoded JWT string.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "iat": now,
        "exp": now + timedelta(hours=JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, _get_secret_key(), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> TokenPayload:
    """Decode and validate a JWT access token.

    Args:
        token: The encoded JWT string.

    Returns:
        A TokenPayload with the decoded claims.

    Raises:
        jwt.ExpiredSignatureError: If the token has expired.
        jwt.InvalidTokenError: If the token is malformed, has an
            invalid signature, or is missing required claims.
    """
    payload = jwt.decode(
        token,
        _get_secret_key(),
        algorithms=[JWT_ALGORITHM],
        options={"require": ["sub", "email", "role", "iat", "exp"]},
    )
    return TokenPayload(
        user_id=payload["sub"],
        email=payload["email"],
        role=payload["role"],
        iat=datetime.fromtimestamp(payload["iat"], tz=timezone.utc),
        exp=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
    )
