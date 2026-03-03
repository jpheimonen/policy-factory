"""Integration tests for the auth flow end-to-end.

Tests the complete authentication lifecycle: first-user registration,
subsequent user creation, role enforcement, and protected endpoint access.
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import policy_factory.auth as auth_mod
from policy_factory.auth import create_access_token, hash_password
from policy_factory.events import EventEmitter
from policy_factory.server.app import create_app
from policy_factory.server.ws import ConnectionManager
from policy_factory.store import PolicyStore

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _configure_auth():
    """Set JWT_SECRET_KEY for all tests in this module."""
    original_key = auth_mod.JWT_SECRET_KEY
    original_expiry = auth_mod.JWT_EXPIRY_HOURS
    auth_mod.JWT_SECRET_KEY = "test-secret-key-for-integration-auth"
    auth_mod.JWT_EXPIRY_HOURS = 24
    yield
    auth_mod.JWT_SECRET_KEY = original_key
    auth_mod.JWT_EXPIRY_HOURS = original_expiry


@pytest.fixture
def store(tmp_path: Path) -> PolicyStore:
    return PolicyStore(tmp_path / "test.db")


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    from policy_factory.data.layers import LAYER_SLUGS

    d = tmp_path / "data"
    for slug in LAYER_SLUGS:
        (d / slug).mkdir(parents=True, exist_ok=True)
        (d / slug / "README.md").write_text(f"# {slug}\n\nSummary.")
    return d


@pytest.fixture
def client(store: PolicyStore, data_dir: Path) -> Generator[TestClient, None, None]:
    app = create_app(
        store=store,
        data_dir=data_dir,
        event_emitter=EventEmitter(),
        ws_manager=ConnectionManager(),
    )
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------


class TestFirstUserRegistration:
    """First user registration flow — creates admin automatically."""

    def test_first_user_becomes_admin(self, client: TestClient) -> None:
        """Register the first user and verify they receive admin role."""
        resp = client.post(
            "/api/auth/register",
            json={"email": "first@example.com", "password": "password123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert data["user"]["role"] == "admin"
        assert data["user"]["email"] == "first@example.com"

    def test_first_user_can_access_protected_endpoint(self, client: TestClient) -> None:
        """Register, then use the JWT to access a protected endpoint."""
        # Register
        resp = client.post(
            "/api/auth/register",
            json={"email": "first@example.com", "password": "password123"},
        )
        token = resp.json()["token"]

        # Access protected endpoint
        resp = client.get(
            "/api/layers/",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    def test_login_after_registration(self, client: TestClient) -> None:
        """Register the first user, then log in with the same credentials."""
        client.post(
            "/api/auth/register",
            json={"email": "first@example.com", "password": "password123"},
        )

        resp = client.post(
            "/api/auth/login",
            json={"email": "first@example.com", "password": "password123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert data["user"]["role"] == "admin"


class TestSecondUserCreation:
    """Admin creates a second user — they should be non-admin."""

    def test_admin_creates_non_admin_user(self, client: TestClient) -> None:
        """As admin, create a second user and verify they are non-admin."""
        # Register first user (admin)
        resp = client.post(
            "/api/auth/register",
            json={"email": "admin@example.com", "password": "password123"},
        )
        admin_token = resp.json()["token"]

        # Admin creates second user
        resp = client.post(
            "/api/auth/register",
            json={"email": "user@example.com", "password": "password456"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"]["role"] == "user"
        assert data["user"]["email"] == "user@example.com"
        # No token returned for admin-created users
        assert "token" not in data

    def test_second_user_can_login(self, client: TestClient) -> None:
        """Create a second user via admin, then log in as that user."""
        # Register admin
        resp = client.post(
            "/api/auth/register",
            json={"email": "admin@example.com", "password": "password123"},
        )
        admin_token = resp.json()["token"]

        # Create second user
        client.post(
            "/api/auth/register",
            json={"email": "user@example.com", "password": "password456"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        # Login as second user
        resp = client.post(
            "/api/auth/login",
            json={"email": "user@example.com", "password": "password456"},
        )
        assert resp.status_code == 200
        assert resp.json()["user"]["role"] == "user"


class TestAdminOnlyEndpoints:
    """Non-admin users should be rejected from admin-only endpoints."""

    def test_non_admin_cannot_create_user(self, client: TestClient, store: PolicyStore) -> None:
        """A non-admin user attempting to create another user gets 403."""
        # Create admin and regular user
        hashed = hash_password("password123")
        store.create_user("admin@example.com", hashed, "admin")
        user_id = store.create_user("user@example.com", hashed, "user")
        user_token = create_access_token(user_id, "user@example.com", "user")

        resp = client.post(
            "/api/users/",
            json={"email": "new@example.com", "password": "newpassword1"},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert resp.status_code == 403

    def test_non_admin_cannot_delete_user(self, client: TestClient, store: PolicyStore) -> None:
        """A non-admin user attempting to delete a user gets 403."""
        hashed = hash_password("password123")
        admin_id = store.create_user("admin@example.com", hashed, "admin")
        user_id = store.create_user("user@example.com", hashed, "user")
        user_token = create_access_token(user_id, "user@example.com", "user")

        resp = client.delete(
            f"/api/users/{admin_id}",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert resp.status_code == 403

    def test_non_admin_cannot_list_users(self, client: TestClient, store: PolicyStore) -> None:
        """A non-admin user listing users gets 403."""
        hashed = hash_password("password123")
        store.create_user("admin@example.com", hashed, "admin")
        user_id = store.create_user("user@example.com", hashed, "user")
        user_token = create_access_token(user_id, "user@example.com", "user")

        resp = client.get(
            "/api/users/",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert resp.status_code == 403


class TestProtectedEndpoints:
    """All protected endpoints reject unauthenticated requests."""

    @pytest.mark.parametrize(
        "method,path",
        [
            ("GET", "/api/layers/"),
            ("GET", "/api/layers/values/items"),
            ("GET", "/api/cascade/status"),
            ("GET", "/api/ideas/"),
            ("GET", "/api/activity/"),
            ("GET", "/api/users/"),
            ("GET", "/api/heartbeat/history"),
            ("GET", "/api/history/values"),
        ],
    )
    def test_unauthenticated_requests_return_401(
        self, client: TestClient, method: str, path: str
    ) -> None:
        """Protected endpoints return 401 without a JWT."""
        resp = getattr(client, method.lower())(path)
        assert resp.status_code == 401
