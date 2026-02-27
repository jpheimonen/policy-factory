"""Tests for WebSocket JWT authentication."""

from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt as pyjwt
import pytest
from fastapi.testclient import TestClient

import policy_factory.auth as auth_mod
from policy_factory.auth import JWT_ALGORITHM, create_access_token, hash_password
from policy_factory.server.app import create_app
from policy_factory.store import PolicyStore


# --- Fixtures ---


@pytest.fixture(autouse=True)
def _configure_auth():
    """Set JWT_SECRET_KEY for all tests."""
    original_key = auth_mod.JWT_SECRET_KEY
    original_expiry = auth_mod.JWT_EXPIRY_HOURS
    auth_mod.JWT_SECRET_KEY = "test-secret-key-for-ws-tests"
    auth_mod.JWT_EXPIRY_HOURS = 24
    yield
    auth_mod.JWT_SECRET_KEY = original_key
    auth_mod.JWT_EXPIRY_HOURS = original_expiry


@pytest.fixture
def store(tmp_path: Path) -> PolicyStore:
    """Provide a fresh PolicyStore."""
    return PolicyStore(tmp_path / "test.db")


@pytest.fixture
def client(store: PolicyStore) -> Generator[TestClient, None, None]:
    """Provide a FastAPI test client (lifespan triggered)."""
    app = create_app(store=store)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def admin_user(store: PolicyStore) -> dict:
    """Create an admin user and return their info + token."""
    hashed = hash_password("adminpassword123")
    user_id = store.create_user("admin@example.com", hashed, "admin")
    token = create_access_token(user_id, "admin@example.com", "admin")
    return {"id": user_id, "email": "admin@example.com", "token": token}


# --- Tests ---


class TestWebSocketAuth:
    """Tests for WebSocket JWT authentication via query parameter."""

    def test_valid_token_accepts_connection(
        self, client: TestClient, admin_user: dict
    ) -> None:
        """A WebSocket connection with a valid JWT is accepted."""
        with client.websocket_connect(f"/ws?token={admin_user['token']}") as ws:
            # Connection was accepted — send a ping and verify it doesn't crash
            ws.send_text("ping")

    def test_no_token_rejects_connection(self, client: TestClient) -> None:
        """A WebSocket connection with no token is rejected."""
        with pytest.raises(Exception):
            with client.websocket_connect("/ws") as ws:
                ws.send_text("ping")

    def test_invalid_token_rejects_connection(self, client: TestClient) -> None:
        """A WebSocket connection with an invalid token is rejected."""
        with pytest.raises(Exception):
            with client.websocket_connect("/ws?token=invalid-jwt-token") as ws:
                ws.send_text("ping")

    def test_expired_token_rejects_connection(self, client: TestClient) -> None:
        """A WebSocket connection with an expired token is rejected."""
        payload = {
            "sub": "user-123",
            "email": "test@example.com",
            "role": "user",
            "iat": datetime.now(timezone.utc) - timedelta(hours=48),
            "exp": datetime.now(timezone.utc) - timedelta(hours=24),
        }
        expired_token = pyjwt.encode(
            payload,
            "test-secret-key-for-ws-tests",
            algorithm=JWT_ALGORITHM,
        )

        with pytest.raises(Exception):
            with client.websocket_connect(f"/ws?token={expired_token}") as ws:
                ws.send_text("ping")

    def test_wrong_signature_rejects_connection(self, client: TestClient) -> None:
        """A WebSocket connection with a token signed by wrong key is rejected."""
        payload = {
            "sub": "user-123",
            "email": "test@example.com",
            "role": "user",
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        }
        bad_token = pyjwt.encode(payload, "wrong-secret", algorithm=JWT_ALGORITHM)

        with pytest.raises(Exception):
            with client.websocket_connect(f"/ws?token={bad_token}") as ws:
                ws.send_text("ping")

    def test_deleted_user_token_rejects_connection(
        self, client: TestClient, store: PolicyStore, admin_user: dict
    ) -> None:
        """A token for a deleted user is rejected at WebSocket connection."""
        # Create and delete a user
        hashed = hash_password("temppassword123")
        user_id = store.create_user("temp@example.com", hashed, "user")
        token = create_access_token(user_id, "temp@example.com", "user")
        store.delete_user(user_id)

        with pytest.raises(Exception):
            with client.websocket_connect(f"/ws?token={token}") as ws:
                ws.send_text("ping")
