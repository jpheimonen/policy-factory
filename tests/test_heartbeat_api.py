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


class TestHeartbeatAgentRun:
    """Tests for GET /api/heartbeat/agent-run/{agent_run_id}."""

    def test_returns_full_agent_run_with_output_text(
        self, client: TestClient, auth_headers: dict, store: PolicyStore
    ) -> None:
        """Returns 200 with the full agent run record including output_text."""
        run_id = store.create_agent_run(
            None, "heartbeat-skim", "Heartbeat skim", "gemini-2.5-flash", None
        )
        store.complete_agent_run(
            run_id,
            success=True,
            output_text="Full skim agent output transcript here.",
        )

        response = client.get(
            f"/api/heartbeat/agent-run/{run_id}", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == run_id
        assert data["output_text"] == "Full skim agent output transcript here."

    def test_output_text_null_when_not_stored(
        self, client: TestClient, auth_headers: dict, store: PolicyStore
    ) -> None:
        """Returns output_text as null when the agent run has no output stored."""
        run_id = store.create_agent_run(
            None, "heartbeat-skim", "Heartbeat skim", "gemini-2.5-flash", None
        )

        response = client.get(
            f"/api/heartbeat/agent-run/{run_id}", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["output_text"] is None

    def test_returns_404_for_nonexistent_agent_run(
        self, client: TestClient, auth_headers: dict
    ) -> None:
        """Returns 404 when the agent run ID does not exist."""
        response = client.get(
            "/api/heartbeat/agent-run/nonexistent-id", headers=auth_headers
        )
        assert response.status_code == 404

    def test_requires_auth(self, client: TestClient) -> None:
        """Returns 401 without authentication."""
        response = client.get("/api/heartbeat/agent-run/some-id")
        assert response.status_code == 401

    def test_response_includes_all_fields(
        self, client: TestClient, auth_headers: dict, store: PolicyStore
    ) -> None:
        """The response includes all AgentRun fields with correct values."""
        cascade_id = store.create_cascade("user_input", "values")
        run_id = store.create_agent_run(
            cascade_id,
            "heartbeat-triage",
            "Heartbeat triage",
            "gemini-2.5-flash",
            "situational-awareness",
        )
        store.complete_agent_run(
            run_id,
            success=True,
            cost=0.003,
            output_text="Triage output content.",
        )

        response = client.get(
            f"/api/heartbeat/agent-run/{run_id}", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()

        # Verify all expected fields are present
        expected_fields = {
            "id",
            "cascade_id",
            "agent_type",
            "agent_label",
            "model",
            "target_layer",
            "started_at",
            "completed_at",
            "success",
            "error_message",
            "cost_usd",
            "output_text",
        }
        assert set(data.keys()) == expected_fields

        # Verify field values
        assert data["id"] == run_id
        assert data["cascade_id"] == cascade_id
        assert data["agent_type"] == "heartbeat-triage"
        assert data["agent_label"] == "Heartbeat triage"
        assert data["model"] == "gemini-2.5-flash"
        assert data["target_layer"] == "situational-awareness"
        assert data["started_at"] is not None  # ISO format string
        assert data["completed_at"] is not None  # ISO format string
        assert data["success"] is True
        assert data["error_message"] is None
        assert data["cost_usd"] == pytest.approx(0.003)
        assert data["output_text"] == "Triage output content."

    def test_datetime_fields_are_iso_format(
        self, client: TestClient, auth_headers: dict, store: PolicyStore
    ) -> None:
        """Datetime fields are serialized as ISO format strings."""
        run_id = store.create_agent_run(
            None, "heartbeat-skim", "Heartbeat skim", "gemini-2.5-flash", None
        )
        store.complete_agent_run(run_id, success=True)

        response = client.get(
            f"/api/heartbeat/agent-run/{run_id}", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()

        # Verify ISO format by checking they're parseable strings with 'T' separator
        assert isinstance(data["started_at"], str)
        assert "T" in data["started_at"]
        assert isinstance(data["completed_at"], str)
        assert "T" in data["completed_at"]

    def test_cascade_id_can_be_null(
        self, client: TestClient, auth_headers: dict, store: PolicyStore
    ) -> None:
        """cascade_id is null for agent runs from heartbeat (not cascade)."""
        run_id = store.create_agent_run(
            None, "heartbeat-skim", "Heartbeat skim", "gemini-2.5-flash", None
        )

        response = client.get(
            f"/api/heartbeat/agent-run/{run_id}", headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["cascade_id"] is None


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
