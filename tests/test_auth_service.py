"""Tests for the auth service module (password hashing + JWT operations)."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import jwt as pyjwt
import pytest

from policy_factory.auth import (
    JWT_ALGORITHM,
    TokenPayload,
    create_access_token,
    decode_access_token,
    hash_password,
    load_auth_config,
    verify_password,
)


# --- Fixtures ---


@pytest.fixture(autouse=True)
def _configure_auth():
    """Set JWT_SECRET_KEY for all tests and clean up after."""
    import policy_factory.auth as auth_mod

    original_key = auth_mod.JWT_SECRET_KEY
    original_expiry = auth_mod.JWT_EXPIRY_HOURS
    auth_mod.JWT_SECRET_KEY = "test-secret-key-for-testing-only"
    auth_mod.JWT_EXPIRY_HOURS = 24
    yield
    auth_mod.JWT_SECRET_KEY = original_key
    auth_mod.JWT_EXPIRY_HOURS = original_expiry


# --- Password Hashing Tests ---


class TestHashPassword:
    """Tests for hash_password function."""

    def test_returns_string(self) -> None:
        """hash_password returns a string."""
        result = hash_password("mysecretpassword")
        assert isinstance(result, str)

    def test_hash_differs_from_plaintext(self) -> None:
        """The hash is not the same as the plaintext password."""
        plaintext = "mysecretpassword"
        hashed = hash_password(plaintext)
        assert hashed != plaintext

    def test_different_calls_produce_different_hashes(self) -> None:
        """Two calls with the same password produce different hashes (different salts)."""
        plaintext = "mysecretpassword"
        hash1 = hash_password(plaintext)
        hash2 = hash_password(plaintext)
        assert hash1 != hash2

    def test_hash_starts_with_bcrypt_prefix(self) -> None:
        """bcrypt hashes start with $2b$."""
        hashed = hash_password("test")
        assert hashed.startswith("$2b$")


class TestVerifyPassword:
    """Tests for verify_password function."""

    def test_correct_password_returns_true(self) -> None:
        """Verifying the correct password returns True."""
        plaintext = "mysecretpassword"
        hashed = hash_password(plaintext)
        assert verify_password(plaintext, hashed) is True

    def test_wrong_password_returns_false(self) -> None:
        """Verifying the wrong password returns False."""
        hashed = hash_password("correct-password")
        assert verify_password("wrong-password", hashed) is False

    def test_empty_password_returns_false(self) -> None:
        """Verifying an empty password against a non-empty hash returns False."""
        hashed = hash_password("notempty")
        assert verify_password("", hashed) is False


# --- JWT Tests ---


class TestCreateAccessToken:
    """Tests for create_access_token function."""

    def test_returns_string(self) -> None:
        """create_access_token returns a JWT string."""
        token = create_access_token("user-123", "test@example.com", "user")
        assert isinstance(token, str)
        # JWT has 3 parts separated by dots
        assert len(token.split(".")) == 3

    def test_token_contains_correct_claims(self) -> None:
        """The token encodes user_id, email, and role."""
        token = create_access_token("user-123", "test@example.com", "admin")
        payload = pyjwt.decode(
            token,
            "test-secret-key-for-testing-only",
            algorithms=[JWT_ALGORITHM],
        )
        assert payload["sub"] == "user-123"
        assert payload["email"] == "test@example.com"
        assert payload["role"] == "admin"

    def test_token_contains_expiry(self) -> None:
        """The token has an exp claim."""
        token = create_access_token("user-123", "test@example.com", "user")
        payload = pyjwt.decode(
            token,
            "test-secret-key-for-testing-only",
            algorithms=[JWT_ALGORITHM],
        )
        assert "exp" in payload
        assert "iat" in payload

    def test_expiry_is_in_future(self) -> None:
        """The token expiry is in the future."""
        token = create_access_token("user-123", "test@example.com", "user")
        payload = pyjwt.decode(
            token,
            "test-secret-key-for-testing-only",
            algorithms=[JWT_ALGORITHM],
        )
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        now = datetime.now(timezone.utc)
        assert exp > now


class TestDecodeAccessToken:
    """Tests for decode_access_token function."""

    def test_decodes_valid_token(self) -> None:
        """A valid token decodes to the correct payload."""
        token = create_access_token("user-123", "test@example.com", "admin")
        payload = decode_access_token(token)
        assert isinstance(payload, TokenPayload)
        assert payload.user_id == "user-123"
        assert payload.email == "test@example.com"
        assert payload.role == "admin"

    def test_expired_token_raises(self) -> None:
        """An expired token raises ExpiredSignatureError."""
        import policy_factory.auth as auth_mod

        # Create a token that expires immediately
        original_expiry = auth_mod.JWT_EXPIRY_HOURS
        auth_mod.JWT_EXPIRY_HOURS = 0  # Will use timedelta(hours=0) which is now

        # Create the token manually with expired time
        payload = {
            "sub": "user-123",
            "email": "test@example.com",
            "role": "user",
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        token = pyjwt.encode(
            payload,
            "test-secret-key-for-testing-only",
            algorithm=JWT_ALGORITHM,
        )

        auth_mod.JWT_EXPIRY_HOURS = original_expiry

        with pytest.raises(pyjwt.ExpiredSignatureError):
            decode_access_token(token)

    def test_invalid_signature_raises(self) -> None:
        """A token signed with a different key raises InvalidTokenError."""
        payload = {
            "sub": "user-123",
            "email": "test@example.com",
            "role": "user",
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        }
        token = pyjwt.encode(payload, "wrong-secret-key", algorithm=JWT_ALGORITHM)

        with pytest.raises(pyjwt.InvalidTokenError):
            decode_access_token(token)

    def test_malformed_token_raises(self) -> None:
        """A completely invalid string raises InvalidTokenError."""
        with pytest.raises(pyjwt.InvalidTokenError):
            decode_access_token("not.a.valid.jwt")

    def test_missing_claims_raises(self) -> None:
        """A token missing required claims raises InvalidTokenError."""
        payload = {
            "sub": "user-123",
            # Missing email and role
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        }
        token = pyjwt.encode(
            payload,
            "test-secret-key-for-testing-only",
            algorithm=JWT_ALGORITHM,
        )
        with pytest.raises(pyjwt.InvalidTokenError):
            decode_access_token(token)

    def test_payload_datetime_fields(self) -> None:
        """The decoded payload has datetime fields for iat and exp."""
        token = create_access_token("user-123", "test@example.com", "user")
        payload = decode_access_token(token)
        assert isinstance(payload.iat, datetime)
        assert isinstance(payload.exp, datetime)


# --- Config Tests ---


class TestLoadAuthConfig:
    """Tests for load_auth_config function."""

    def test_auto_generates_key_without_jwt_secret_key(self) -> None:
        """load_auth_config auto-generates a key if JWT_SECRET_KEY is not set."""
        import policy_factory.auth as auth_mod

        auth_mod.JWT_SECRET_KEY = None

        with patch.dict(os.environ, {}, clear=True):
            # Remove the key if present
            os.environ.pop("JWT_SECRET_KEY", None)
            load_auth_config()
            # Should have generated a random key (64 hex chars = 32 bytes)
            assert auth_mod.JWT_SECRET_KEY is not None
            assert len(auth_mod.JWT_SECRET_KEY) == 64

    def test_loads_secret_key_from_env(self) -> None:
        """load_auth_config loads JWT_SECRET_KEY from environment."""
        import policy_factory.auth as auth_mod

        with patch.dict(os.environ, {"JWT_SECRET_KEY": "my-test-secret"}):
            load_auth_config()
            assert auth_mod.JWT_SECRET_KEY == "my-test-secret"

    def test_loads_custom_expiry_hours(self) -> None:
        """load_auth_config loads JWT_EXPIRY_HOURS from environment."""
        import policy_factory.auth as auth_mod

        with patch.dict(
            os.environ, {"JWT_SECRET_KEY": "test", "JWT_EXPIRY_HOURS": "48"}
        ):
            load_auth_config()
            assert auth_mod.JWT_EXPIRY_HOURS == 48

    def test_invalid_expiry_hours_uses_default(self) -> None:
        """Invalid JWT_EXPIRY_HOURS falls back to default."""
        import policy_factory.auth as auth_mod

        auth_mod.JWT_EXPIRY_HOURS = 24  # Reset to default
        with patch.dict(
            os.environ, {"JWT_SECRET_KEY": "test", "JWT_EXPIRY_HOURS": "not-a-number"}
        ):
            load_auth_config()
            assert auth_mod.JWT_EXPIRY_HOURS == 24  # Stays at default
