"""Tests for heartbeat API router endpoints."""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import policy_factory.auth as auth_mod
from policy_factory.auth import create_access_token, hash_password
from policy_factory.server.app import create_app
from policy_factory.store import PolicyStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _configure_auth():
    """Set JWT_SECRET_KEY for all tests."""
    original_key = auth_mod.JWT_SECRET_KEY
    original_expiry = auth_mod.JWT_EXPIRY_HOURS
    auth_mod.JWT_SECRET_KEY = "test-secret-key-for-heartbeat-api-tests"
    auth_mod.JWT_EXPIRY_HOURS = 24
    yield
    auth_mod.JWT_SECRET_KEY = original_key
    auth_mod.JWT_EXPIRY_HOURS = original_expiry


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """Create minimal data directories."""
    for slug in (
        "values",
        "situational-awareness",
        "strategic-objectives",
        "tactical-objectives",
        "policies",
    ):
        d = tmp_path / slug
        d.mkdir()
        (d / "README.md").write_text(f"# {slug}", encoding="utf-8")
    return tmp_path


@pytest.fixture
def client(
    store: PolicyStore, data_dir: Path
) -> Generator[TestClient, None, None]:
    """Create a test client for the app."""
    # Disable heartbeat scheduler for tests
    with patch.dict(os.environ, {"POLICY_FACTORY_HEARTBEAT_INTERVAL_HOURS": "0"}):
        app = create_app(store=store, data_dir=data_dir)
        with TestClient(app) as c:
            yield c


@pytest.fixture
def auth_headers(store: PolicyStore) -> dict[str, str]:
    """Create an admin user and return auth headers."""
    user_id = store.create_user("admin@test.com", hash_password("password"), "admin")
    token = create_access_token(user_id, "admin@test.com", "admin")
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestHeartbeatHistory:
    """Tests for GET /api/heartbeat/history."""

    def test_history_empty(self, client: TestClient, auth_headers: dict) -> None:
        """Returns empty list when no heartbeat runs exist."""
        response = client.get("/api/heartbeat/history", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []

    def test_history_returns_runs(
        self, client: TestClient, auth_headers: dict, store: PolicyStore
    ) -> None:
        """Returns heartbeat runs in reverse chronological order."""
        run_id = store.create_heartbeat_run("manual")
        store.update_heartbeat_tier(
            run_id, tier=1, escalated=False, outcome="Nothing noteworthy"
        )
        store.complete_heartbeat_run(run_id)

        response = client.get("/api/heartbeat/history", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == run_id
        assert data[0]["trigger"] == "manual"
        assert data[0]["highest_tier"] == 1
        assert data[0]["completed_at"] is not None
        assert len(data[0]["structured_log"]) == 1

    def test_history_with_limit(
        self, client: TestClient, auth_headers: dict, store: PolicyStore
    ) -> None:
        """Respects the limit parameter."""
        for _ in range(5):
            run_id = store.create_heartbeat_run("scheduled")
            store.complete_heartbeat_run(run_id)

        response = client.get(
            "/api/heartbeat/history?limit=3", headers=auth_headers
        )
        assert response.status_code == 200
        assert len(response.json()) == 3

    def test_history_requires_auth(self, client: TestClient) -> None:
        """Returns 401 without auth."""
        response = client.get("/api/heartbeat/history")
        assert response.status_code == 401


class TestHeartbeatLatest:
    """Tests for GET /api/heartbeat/latest."""

    def test_latest_empty(self, client: TestClient, auth_headers: dict) -> None:
        """Returns null when no heartbeat runs exist."""
        response = client.get("/api/heartbeat/latest", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() is None

    def test_latest_returns_most_recent(
        self, client: TestClient, auth_headers: dict, store: PolicyStore
    ) -> None:
        """Returns the most recent heartbeat run."""
        id1 = store.create_heartbeat_run("scheduled")
        store.complete_heartbeat_run(id1)

        id2 = store.create_heartbeat_run("manual")
        store.update_heartbeat_tier(
            id2, tier=1, escalated=True, outcome="Flagged items"
        )
        store.update_heartbeat_tier(
            id2, tier=2, escalated=False, outcome="No updates"
        )
        store.complete_heartbeat_run(id2)

        response = client.get("/api/heartbeat/latest", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == id2
        assert data["highest_tier"] == 2
        assert len(data["structured_log"]) == 2

    def test_latest_requires_auth(self, client: TestClient) -> None:
        """Returns 401 without auth."""
        response = client.get("/api/heartbeat/latest")
        assert response.status_code == 401


class TestHeartbeatStatus:
    """Tests for GET /api/heartbeat/status."""

    def test_status_returns_info(
        self, client: TestClient, auth_headers: dict
    ) -> None:
        """Returns heartbeat system status."""
        response = client.get("/api/heartbeat/status", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "scheduler_active" in data
        assert "interval_hours" in data
        assert "next_run_time" in data
        assert "heartbeat_running" in data
        assert "latest_run" in data

    def test_status_heartbeat_not_running(
        self, client: TestClient, auth_headers: dict
    ) -> None:
        """Shows heartbeat_running=false when no heartbeat is active."""
        response = client.get("/api/heartbeat/status", headers=auth_headers)
        data = response.json()
        assert data["heartbeat_running"] is False

    def test_status_heartbeat_running(
        self, client: TestClient, auth_headers: dict, store: PolicyStore
    ) -> None:
        """Shows heartbeat_running=true when a heartbeat is active."""
        store.create_heartbeat_run("manual")
        # Don't complete it

        response = client.get("/api/heartbeat/status", headers=auth_headers)
        data = response.json()
        assert data["heartbeat_running"] is True

    def test_status_requires_auth(self, client: TestClient) -> None:
        """Returns 401 without auth."""
        response = client.get("/api/heartbeat/status")
        assert response.status_code == 401


class TestHeartbeatTrigger:
    """Tests for POST /api/heartbeat/trigger."""

    def test_trigger_409_when_running(
        self, client: TestClient, auth_headers: dict, store: PolicyStore
    ) -> None:
        """Returns 409 if a heartbeat is already running."""
        store.create_heartbeat_run("scheduled")
        # Don't complete — it's still running

        response = client.post(
            "/api/heartbeat/trigger", headers=auth_headers
        )
        assert response.status_code == 409
        assert "already running" in response.json()["detail"]

    def test_trigger_requires_auth(self, client: TestClient) -> None:
        """Returns 401 without auth."""
        response = client.post("/api/heartbeat/trigger")
        assert response.status_code == 401
