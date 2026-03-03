"""Tests for the cascade REST API router.

Tests trigger endpoints, status queries, control endpoints (pause/resume/cancel),
and queue management.
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import policy_factory.auth as auth_mod
from policy_factory.auth import create_access_token, hash_password
from policy_factory.data.layers import LAYER_SLUGS
from policy_factory.events import EventEmitter
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
    auth_mod.JWT_SECRET_KEY = "test-secret-key-for-cascade-api-tests"
    auth_mod.JWT_EXPIRY_HOURS = 24
    yield
    auth_mod.JWT_SECRET_KEY = original_key
    auth_mod.JWT_EXPIRY_HOURS = original_expiry


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """Create a data directory with layer subdirectories."""
    d = tmp_path / "data"
    for slug in LAYER_SLUGS:
        (d / slug).mkdir(parents=True, exist_ok=True)
    return d


@pytest.fixture
def store(tmp_path: Path) -> PolicyStore:
    return PolicyStore(tmp_path / "test.db")


@pytest.fixture
def emitter() -> EventEmitter:
    return EventEmitter()


@pytest.fixture
def client(
    store: PolicyStore, emitter: EventEmitter, data_dir: Path
) -> Generator[TestClient, None, None]:
    app = create_app(store=store, event_emitter=emitter, data_dir=data_dir)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_headers(store: PolicyStore) -> dict[str, str]:
    hashed = hash_password("testpassword")
    user_id = store.create_user("test@example.com", hashed, "admin")
    token = create_access_token(user_id, "test@example.com", "admin")
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Trigger endpoint tests
# ---------------------------------------------------------------------------


class TestTriggerFromInput:
    """Tests for POST /api/cascade/trigger."""

    def test_requires_auth(self, client: TestClient) -> None:
        resp = client.post("/api/cascade/trigger", json={"input_text": "test"})
        assert resp.status_code == 401

    def test_triggers_cascade_with_classification(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        mock_classification = MagicMock()
        mock_classification.target_layer = "policies"
        mock_classification.secondary_layers = []
        mock_classification.confidence = "high"
        mock_classification.explanation = "A specific policy proposal."

        with patch(
            "policy_factory.server.routers.cascade.classify_input",
            new_callable=AsyncMock,
            return_value=mock_classification,
        ), patch(
            "policy_factory.server.routers.cascade.trigger_cascade",
            new_callable=AsyncMock,
            return_value=("cascade-123", True),
        ):
            resp = client.post(
                "/api/cascade/trigger",
                json={"input_text": "Finland should invest in AI"},
                headers=auth_headers,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "cascade-123"
        assert data["is_cascade"] is True
        assert data["classification"]["target_layer"] == "policies"


class TestTriggerRefresh:
    """Tests for POST /api/cascade/refresh."""

    def test_requires_auth(self, client: TestClient) -> None:
        resp = client.post("/api/cascade/refresh", json={"layer_slug": "values"})
        assert resp.status_code == 401

    def test_returns_404_for_invalid_layer(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        resp = client.post(
            "/api/cascade/refresh",
            json={"layer_slug": "invalid"},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_triggers_cascade_for_valid_layer(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        with patch(
            "policy_factory.server.routers.cascade.trigger_cascade",
            new_callable=AsyncMock,
            return_value=("cascade-456", True),
        ):
            resp = client.post(
                "/api/cascade/refresh",
                json={"layer_slug": "values"},
                headers=auth_headers,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "cascade-456"
        assert data["is_cascade"] is True


class TestTriggerFull:
    """Tests for POST /api/cascade/full."""

    def test_requires_auth(self, client: TestClient) -> None:
        resp = client.post("/api/cascade/full")
        assert resp.status_code == 401

    def test_triggers_full_cascade(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        with patch(
            "policy_factory.server.routers.cascade.trigger_cascade",
            new_callable=AsyncMock,
            return_value=("cascade-789", True),
        ):
            resp = client.post("/api/cascade/full", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "cascade-789"


# ---------------------------------------------------------------------------
# Status endpoint tests
# ---------------------------------------------------------------------------


class TestCascadeStatus:
    """Tests for GET /api/cascade/status."""

    def test_requires_auth(self, client: TestClient) -> None:
        resp = client.get("/api/cascade/status")
        assert resp.status_code == 401

    def test_returns_idle_when_no_cascade(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        resp = client.get("/api/cascade/status", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "idle"
        assert data["cascade_id"] is None
        assert data["queue_depth"] == 0

    def test_returns_running_status(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        store: PolicyStore,
    ) -> None:
        # Create a running cascade
        cascade_id = store.create_cascade("user_input", "values", "test context")

        resp = client.get("/api/cascade/status", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "running"
        assert data["cascade_id"] == cascade_id

    def test_includes_queue_entries(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        store: PolicyStore,
    ) -> None:
        # Create running cascade and queue entry
        store.create_cascade("user_input", "values")
        store.enqueue_cascade("layer_refresh", "policies")

        resp = client.get("/api/cascade/status", headers=auth_headers)
        data = resp.json()
        assert data["queue_depth"] == 1
        assert len(data["queue_entries"]) == 1


# ---------------------------------------------------------------------------
# Detail endpoint tests
# ---------------------------------------------------------------------------


class TestCascadeDetail:
    """Tests for GET /api/cascade/{cascade_id}."""

    def test_returns_404_for_unknown_id(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        resp = client.get("/api/cascade/nonexistent", headers=auth_headers)
        assert resp.status_code == 404

    def test_returns_cascade_detail(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        store: PolicyStore,
    ) -> None:
        cascade_id = store.create_cascade("user_input", "values", "test context")

        resp = client.get(f"/api/cascade/{cascade_id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == cascade_id
        assert data["trigger_source"] == "user_input"
        assert data["starting_layer"] == "values"

    def test_includes_agent_runs(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        store: PolicyStore,
    ) -> None:
        cascade_id = store.create_cascade("user_input", "values")
        store.create_agent_run(cascade_id, "generator", "Values generator", "opus", "values")

        resp = client.get(f"/api/cascade/{cascade_id}", headers=auth_headers)
        data = resp.json()
        assert len(data["agent_runs"]) == 1


# ---------------------------------------------------------------------------
# History endpoint tests
# ---------------------------------------------------------------------------


class TestCascadeHistory:
    """Tests for GET /api/cascade/history."""

    def test_returns_cascade_history(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        store: PolicyStore,
    ) -> None:
        store.create_cascade("user_input", "values")
        store.create_cascade("layer_refresh", "policies")

        resp = client.get("/api/cascade/history", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    def test_pagination(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        store: PolicyStore,
    ) -> None:
        for i in range(5):
            store.create_cascade("user_input", "values")

        resp = client.get("/api/cascade/history?limit=2&offset=0", headers=auth_headers)
        data = resp.json()
        assert len(data) == 2


# ---------------------------------------------------------------------------
# Control endpoint tests
# ---------------------------------------------------------------------------


class TestPauseCascade:
    """Tests for POST /api/cascade/{cascade_id}/pause."""

    def test_returns_404_for_unknown_cascade(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        resp = client.post("/api/cascade/nonexistent/pause", headers=auth_headers)
        assert resp.status_code == 404

    def test_returns_409_for_non_running_cascade(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        store: PolicyStore,
    ) -> None:
        from policy_factory.cascade.controller import CascadeController, CascadeState
        from policy_factory.server.deps import register_cascade_controller

        cascade_id = store.create_cascade("user_input", "values")
        controller = CascadeController(cascade_id, EventEmitter())

        # Manually set to paused state
        controller._state = CascadeState.PAUSED
        register_cascade_controller(cascade_id, controller)

        resp = client.post(f"/api/cascade/{cascade_id}/pause", headers=auth_headers)
        assert resp.status_code == 409

        # Cleanup
        from policy_factory.server.deps import unregister_cascade_controller
        unregister_cascade_controller(cascade_id)


class TestResumeCascade:
    """Tests for POST /api/cascade/{cascade_id}/resume."""

    def test_returns_404_for_unknown_cascade(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        resp = client.post("/api/cascade/nonexistent/resume", headers=auth_headers)
        assert resp.status_code == 404

    def test_returns_409_for_non_paused_cascade(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        store: PolicyStore,
    ) -> None:
        from policy_factory.cascade.controller import CascadeController
        from policy_factory.server.deps import register_cascade_controller

        cascade_id = store.create_cascade("user_input", "values")
        controller = CascadeController(cascade_id, EventEmitter())
        register_cascade_controller(cascade_id, controller)

        resp = client.post(f"/api/cascade/{cascade_id}/resume", headers=auth_headers)
        assert resp.status_code == 409

        from policy_factory.server.deps import unregister_cascade_controller
        unregister_cascade_controller(cascade_id)


class TestCancelCascade:
    """Tests for POST /api/cascade/{cascade_id}/cancel."""

    def test_returns_404_for_unknown_cascade(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        resp = client.post("/api/cascade/nonexistent/cancel", headers=auth_headers)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Queue management tests
# ---------------------------------------------------------------------------


class TestCancelQueuedCascade:
    """Tests for DELETE /api/cascade/queue/{queue_id}."""

    def test_returns_404_for_nonexistent_queue_entry(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        resp = client.delete("/api/cascade/queue/nonexistent", headers=auth_headers)
        assert resp.status_code == 404

    def test_removes_queued_cascade(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        store: PolicyStore,
    ) -> None:
        queue_id, _ = store.enqueue_cascade("user_input", "values")
        resp = client.delete(f"/api/cascade/queue/{queue_id}", headers=auth_headers)
        assert resp.status_code == 204

        # Verify it's gone
        assert store.get_queue_depth() == 0
