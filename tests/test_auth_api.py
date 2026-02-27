"""Tests for auth and users API endpoints."""

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
    auth_mod.JWT_SECRET_KEY = "test-secret-key-for-auth-api-tests"
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
    """Provide a FastAPI test client with initialized store (lifespan triggered)."""
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


@pytest.fixture
def regular_user(store: PolicyStore) -> dict:
    """Create a regular user and return their info + token."""
    hashed = hash_password("userpassword123")
    user_id = store.create_user("user@example.com", hashed, "user")
    token = create_access_token(user_id, "user@example.com", "user")
    return {"id": user_id, "email": "user@example.com", "token": token}


def auth_header(token: str) -> dict:
    """Create an Authorization header dict."""
    return {"Authorization": f"Bearer {token}"}


# =============================================================================
# Auth Router Tests
# =============================================================================


class TestLogin:
    """Tests for POST /api/auth/login."""

    def test_login_success(self, client: TestClient, admin_user: dict) -> None:
        """Login with correct credentials returns a JWT and user info."""
        resp = client.post(
            "/api/auth/login",
            json={"email": "admin@example.com", "password": "adminpassword123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert data["user"]["email"] == "admin@example.com"
        assert data["user"]["role"] == "admin"
        assert "id" in data["user"]

    def test_login_wrong_password(self, client: TestClient, admin_user: dict) -> None:
        """Login with wrong password returns 401."""
        resp = client.post(
            "/api/auth/login",
            json={"email": "admin@example.com", "password": "wrongpassword"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid email or password"

    def test_login_nonexistent_email(self, client: TestClient) -> None:
        """Login with non-existent email returns 401 with same generic message."""
        resp = client.post(
            "/api/auth/login",
            json={"email": "nobody@example.com", "password": "anything"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid email or password"

    def test_login_no_email_enumeration(self, client: TestClient, admin_user: dict) -> None:
        """Wrong email and wrong password produce the same error message."""
        resp_bad_email = client.post(
            "/api/auth/login",
            json={"email": "nobody@example.com", "password": "anything"},
        )
        resp_bad_pwd = client.post(
            "/api/auth/login",
            json={"email": "admin@example.com", "password": "wrongpassword"},
        )
        assert resp_bad_email.json()["detail"] == resp_bad_pwd.json()["detail"]

    def test_login_returns_valid_jwt(self, client: TestClient, admin_user: dict) -> None:
        """The returned JWT can be decoded and contains correct claims."""
        resp = client.post(
            "/api/auth/login",
            json={"email": "admin@example.com", "password": "adminpassword123"},
        )
        token = resp.json()["token"]
        payload = pyjwt.decode(
            token,
            "test-secret-key-for-auth-api-tests",
            algorithms=[JWT_ALGORITHM],
        )
        assert payload["sub"] == admin_user["id"]
        assert payload["email"] == "admin@example.com"
        assert payload["role"] == "admin"
        assert "exp" in payload


class TestRegister:
    """Tests for POST /api/auth/register."""

    def test_first_user_becomes_admin(self, client: TestClient) -> None:
        """The first user to register is automatically admin."""
        resp = client.post(
            "/api/auth/register",
            json={"email": "first@example.com", "password": "securepassword123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data  # First user gets a JWT
        assert data["user"]["role"] == "admin"
        assert data["user"]["email"] == "first@example.com"

    def test_first_user_returns_jwt(self, client: TestClient) -> None:
        """The first registration returns a JWT so they're immediately logged in."""
        resp = client.post(
            "/api/auth/register",
            json={"email": "first@example.com", "password": "securepassword123"},
        )
        data = resp.json()
        assert "token" in data
        # Verify the token is valid
        payload = pyjwt.decode(
            data["token"],
            "test-secret-key-for-auth-api-tests",
            algorithms=[JWT_ALGORITHM],
        )
        assert payload["role"] == "admin"

    def test_register_without_auth_after_first_user_returns_403(
        self, client: TestClient, admin_user: dict
    ) -> None:
        """Registration without auth after the first user returns 403."""
        resp = client.post(
            "/api/auth/register",
            json={"email": "newuser@example.com", "password": "securepassword123"},
        )
        assert resp.status_code == 403

    def test_register_with_non_admin_jwt_returns_403(
        self, client: TestClient, admin_user: dict, regular_user: dict
    ) -> None:
        """Registration with a non-admin JWT returns 403."""
        resp = client.post(
            "/api/auth/register",
            json={"email": "newuser@example.com", "password": "securepassword123"},
            headers=auth_header(regular_user["token"]),
        )
        assert resp.status_code == 403

    def test_register_with_admin_jwt_creates_regular_user(
        self, client: TestClient, admin_user: dict
    ) -> None:
        """Admin can create a new regular user."""
        resp = client.post(
            "/api/auth/register",
            json={"email": "newuser@example.com", "password": "securepassword123"},
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"]["role"] == "user"
        assert data["user"]["email"] == "newuser@example.com"
        # Admin-created user does NOT get a JWT
        assert "token" not in data

    def test_duplicate_email_returns_409(self, client: TestClient, admin_user: dict) -> None:
        """Registering a duplicate email returns 409."""
        resp = client.post(
            "/api/auth/register",
            json={"email": "admin@example.com", "password": "securepassword123"},
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 409

    def test_invalid_email_format(self, client: TestClient) -> None:
        """Invalid email format is rejected."""
        resp = client.post(
            "/api/auth/register",
            json={"email": "not-an-email", "password": "securepassword123"},
        )
        assert resp.status_code == 422

    def test_password_too_short(self, client: TestClient) -> None:
        """Password under minimum length is rejected."""
        resp = client.post(
            "/api/auth/register",
            json={"email": "test@example.com", "password": "short"},
        )
        assert resp.status_code == 422

    def test_passwords_are_hashed(self, client: TestClient, store: PolicyStore) -> None:
        """Passwords are stored as bcrypt hashes, not plaintext."""
        client.post(
            "/api/auth/register",
            json={"email": "hashtest@example.com", "password": "plaintextpassword123"},
        )
        user = store.get_user_by_email("hashtest@example.com")
        assert user is not None
        assert user.hashed_password != "plaintextpassword123"
        assert user.hashed_password.startswith("$2b$")


class TestRefresh:
    """Tests for POST /api/auth/refresh."""

    def test_refresh_returns_new_token(
        self, client: TestClient, admin_user: dict
    ) -> None:
        """Refresh with valid token returns a new JWT."""
        resp = client.post(
            "/api/auth/refresh",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert data["user"]["email"] == "admin@example.com"
        # New token should be different from the old one (different iat)
        # (May be the same if created in the same second, but we just check it's valid)
        new_payload = pyjwt.decode(
            data["token"],
            "test-secret-key-for-auth-api-tests",
            algorithms=[JWT_ALGORITHM],
        )
        assert new_payload["sub"] == admin_user["id"]

    def test_refresh_with_expired_token_returns_401(self, client: TestClient) -> None:
        """Refresh with an expired token returns 401."""
        # Create an expired token
        payload = {
            "sub": "user-123",
            "email": "test@example.com",
            "role": "user",
            "iat": datetime.now(timezone.utc) - timedelta(hours=48),
            "exp": datetime.now(timezone.utc) - timedelta(hours=24),
        }
        expired_token = pyjwt.encode(
            payload,
            "test-secret-key-for-auth-api-tests",
            algorithm=JWT_ALGORITHM,
        )
        resp = client.post(
            "/api/auth/refresh",
            headers=auth_header(expired_token),
        )
        assert resp.status_code == 401

    def test_refresh_without_token_returns_401(self, client: TestClient) -> None:
        """Refresh without any token returns 401."""
        resp = client.post("/api/auth/refresh")
        assert resp.status_code == 401


# =============================================================================
# Auth Dependencies Tests
# =============================================================================


class TestGetCurrentUser:
    """Tests for the get_current_user dependency (via protected endpoints)."""

    def test_valid_token_allows_access(
        self, client: TestClient, admin_user: dict
    ) -> None:
        """A valid token grants access to protected endpoints."""
        # Use refresh as a proxy for testing get_current_user
        resp = client.post(
            "/api/auth/refresh",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 200

    def test_no_auth_header_returns_401(self, client: TestClient) -> None:
        """No Authorization header returns 401."""
        resp = client.post("/api/auth/refresh")
        assert resp.status_code == 401

    def test_malformed_token_returns_401(self, client: TestClient) -> None:
        """A malformed/corrupted token returns 401."""
        resp = client.post(
            "/api/auth/refresh",
            headers=auth_header("not-a-jwt-token"),
        )
        assert resp.status_code == 401

    def test_expired_token_returns_401(self, client: TestClient) -> None:
        """An expired token returns 401."""
        payload = {
            "sub": "user-123",
            "email": "test@example.com",
            "role": "user",
            "iat": datetime.now(timezone.utc) - timedelta(hours=48),
            "exp": datetime.now(timezone.utc) - timedelta(hours=24),
        }
        expired = pyjwt.encode(
            payload,
            "test-secret-key-for-auth-api-tests",
            algorithm=JWT_ALGORITHM,
        )
        resp = client.post(
            "/api/auth/refresh",
            headers=auth_header(expired),
        )
        assert resp.status_code == 401

    def test_invalid_signature_returns_401(self, client: TestClient) -> None:
        """A token signed with a different key returns 401."""
        payload = {
            "sub": "user-123",
            "email": "test@example.com",
            "role": "user",
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        }
        bad_token = pyjwt.encode(payload, "wrong-key", algorithm=JWT_ALGORITHM)
        resp = client.post(
            "/api/auth/refresh",
            headers=auth_header(bad_token),
        )
        assert resp.status_code == 401

    def test_deleted_user_token_returns_401(
        self, client: TestClient, store: PolicyStore, admin_user: dict, regular_user: dict
    ) -> None:
        """A deleted user's still-valid JWT is rejected."""
        # Delete the regular user
        store.delete_user(regular_user["id"])

        # Their token should now fail
        resp = client.post(
            "/api/auth/refresh",
            headers=auth_header(regular_user["token"]),
        )
        assert resp.status_code == 401


class TestRequireAdmin:
    """Tests for the require_admin dependency (via admin-only endpoints)."""

    def test_admin_user_allowed(self, client: TestClient, admin_user: dict) -> None:
        """Admin users can access admin-only endpoints."""
        resp = client.get(
            "/api/users/",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 200

    def test_regular_user_returns_403(
        self, client: TestClient, admin_user: dict, regular_user: dict
    ) -> None:
        """Non-admin users get 403 on admin-only endpoints."""
        resp = client.get(
            "/api/users/",
            headers=auth_header(regular_user["token"]),
        )
        assert resp.status_code == 403

    def test_no_token_returns_401(self, client: TestClient) -> None:
        """No token returns 401 (before checking admin role)."""
        resp = client.get("/api/users/")
        assert resp.status_code == 401


# =============================================================================
# Users Router Tests
# =============================================================================


class TestListUsers:
    """Tests for GET /api/users/."""

    def test_admin_can_list_users(self, client: TestClient, admin_user: dict) -> None:
        """Admin can see the user list."""
        resp = client.get(
            "/api/users/",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "users" in data
        assert len(data["users"]) >= 1
        # Should contain the admin user
        emails = [u["email"] for u in data["users"]]
        assert "admin@example.com" in emails

    def test_user_list_excludes_password_hashes(
        self, client: TestClient, admin_user: dict
    ) -> None:
        """User list never includes password hashes."""
        resp = client.get(
            "/api/users/",
            headers=auth_header(admin_user["token"]),
        )
        for user in resp.json()["users"]:
            assert "hashed_password" not in user
            assert "password" not in user

    def test_non_admin_returns_403(
        self, client: TestClient, admin_user: dict, regular_user: dict
    ) -> None:
        """Non-admin user gets 403."""
        resp = client.get(
            "/api/users/",
            headers=auth_header(regular_user["token"]),
        )
        assert resp.status_code == 403


class TestCreateUser:
    """Tests for POST /api/users/."""

    def test_admin_can_create_user(self, client: TestClient, admin_user: dict) -> None:
        """Admin can create a new user."""
        resp = client.post(
            "/api/users/",
            json={"email": "newuser@example.com", "password": "securepassword123"},
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "newuser@example.com"
        assert data["role"] == "user"
        assert "id" in data

    def test_created_user_has_user_role(
        self, client: TestClient, admin_user: dict
    ) -> None:
        """Admin-created users always get the 'user' role."""
        resp = client.post(
            "/api/users/",
            json={"email": "newuser@example.com", "password": "securepassword123"},
            headers=auth_header(admin_user["token"]),
        )
        assert resp.json()["role"] == "user"

    def test_non_admin_returns_403(
        self, client: TestClient, admin_user: dict, regular_user: dict
    ) -> None:
        """Non-admin user gets 403."""
        resp = client.post(
            "/api/users/",
            json={"email": "newuser@example.com", "password": "securepassword123"},
            headers=auth_header(regular_user["token"]),
        )
        assert resp.status_code == 403

    def test_duplicate_email_returns_409(
        self, client: TestClient, admin_user: dict
    ) -> None:
        """Creating a user with a duplicate email returns 409."""
        resp = client.post(
            "/api/users/",
            json={"email": "admin@example.com", "password": "securepassword123"},
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 409


class TestDeleteUser:
    """Tests for DELETE /api/users/:id."""

    def test_admin_can_delete_user(
        self, client: TestClient, admin_user: dict, regular_user: dict
    ) -> None:
        """Admin can delete another user."""
        resp = client.delete(
            f"/api/users/{regular_user['id']}",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 204

    def test_admin_cannot_delete_self(
        self, client: TestClient, admin_user: dict
    ) -> None:
        """Admin cannot delete their own account."""
        resp = client.delete(
            f"/api/users/{admin_user['id']}",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 400
        assert "Cannot delete your own account" in resp.json()["detail"]

    def test_delete_nonexistent_user_returns_404(
        self, client: TestClient, admin_user: dict
    ) -> None:
        """Deleting a non-existent user returns 404."""
        resp = client.delete(
            "/api/users/nonexistent-uuid",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 404

    def test_non_admin_returns_403(
        self, client: TestClient, admin_user: dict, regular_user: dict
    ) -> None:
        """Non-admin user gets 403."""
        resp = client.delete(
            f"/api/users/{admin_user['id']}",
            headers=auth_header(regular_user["token"]),
        )
        assert resp.status_code == 403


# =============================================================================
# Health Endpoint Accessibility
# =============================================================================


class TestHealthNoAuth:
    """Test that the health endpoint remains accessible without authentication."""

    def test_health_check_no_auth(self, client: TestClient) -> None:
        """Health check works without authentication."""
        resp = client.get("/api/health/check")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
