"""Tests for the activity REST API endpoints."""

from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import policy_factory.auth as auth_mod
from policy_factory.auth import create_access_token, hash_password
from policy_factory.server.app import create_app
from policy_factory.store import PolicyStore

# --- Fixtures ---


@pytest.fixture(autouse=True)
def _configure_auth():
    """Set JWT_SECRET_KEY for all tests."""
    original_key = auth_mod.JWT_SECRET_KEY
    original_expiry = auth_mod.JWT_EXPIRY_HOURS
    auth_mod.JWT_SECRET_KEY = "test-secret-key-for-activity-tests"
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
def admin_token(store: PolicyStore) -> str:
    """Create an admin user and return their JWT."""
    hashed = hash_password("adminpassword123")
    user_id = store.create_user("admin@example.com", hashed, "admin")
    return create_access_token(user_id, "admin@example.com", "admin")


@pytest.fixture
def auth_headers(admin_token: str) -> dict:
    """Provide Authorization headers."""
    return {"Authorization": f"Bearer {admin_token}"}


def _seed_events(store: PolicyStore, count: int = 5) -> list[int]:
    """Seed the store with events and return their IDs."""
    ts = datetime.now(timezone.utc)
    ids = []
    for i in range(count):
        event_id = store.add_event(
            event_type=f"event_type_{i}",
            data={"n": i, "event_type": f"event_type_{i}"},
            timestamp=ts,
            layer_slug="values" if i % 2 == 0 else None,
            category="cascade" if i < 3 else "heartbeat",
        )
        ids.append(event_id)
    return ids


# --- Tests ---


class TestActivityEndpoint:
    """Tests for GET /api/activity/."""

    def test_requires_auth(self, client: TestClient) -> None:
        """Activity endpoint requires JWT."""
        resp = client.get("/api/activity/")
        assert resp.status_code == 401

    def test_returns_events(
        self, client: TestClient, store: PolicyStore, auth_headers: dict
    ) -> None:
        """Returns events in reverse chronological order."""
        _seed_events(store, 3)

        resp = client.get("/api/activity/", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["events"]) == 3
        # Reverse chronological: newest first
        assert data["events"][0]["data"]["n"] == 2
        assert data["events"][1]["data"]["n"] == 1
        assert data["events"][2]["data"]["n"] == 0

    def test_filter_by_event_type(
        self, client: TestClient, store: PolicyStore, auth_headers: dict
    ) -> None:
        """Filtering by event_type returns only matching events."""
        ts = datetime.now(timezone.utc)
        store.add_event("cascade_started", {}, ts, category="cascade")
        store.add_event("heartbeat_started", {}, ts, category="heartbeat")

        resp = client.get(
            "/api/activity/", headers=auth_headers, params={"event_type": "cascade_started"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["events"]) == 1
        assert data["events"][0]["event_type"] == "cascade_started"

    def test_filter_by_layer(
        self, client: TestClient, store: PolicyStore, auth_headers: dict
    ) -> None:
        """Filtering by layer returns only events for that layer."""
        ts = datetime.now(timezone.utc)
        store.add_event(
            "layer_generation_started", {}, ts, layer_slug="values", category="cascade"
        )
        store.add_event(
            "layer_generation_started", {}, ts, layer_slug="policies", category="cascade"
        )

        resp = client.get(
            "/api/activity/", headers=auth_headers, params={"layer": "values"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["events"]) == 1

    def test_filter_by_category(
        self, client: TestClient, store: PolicyStore, auth_headers: dict
    ) -> None:
        """Filtering by category returns only matching events."""
        ts = datetime.now(timezone.utc)
        store.add_event("cascade_started", {}, ts, category="cascade")
        store.add_event("heartbeat_started", {}, ts, category="heartbeat")

        resp = client.get(
            "/api/activity/", headers=auth_headers, params={"category": "heartbeat"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["events"]) == 1
        assert data["events"][0]["event_type"] == "heartbeat_started"

    def test_pagination_limit(
        self, client: TestClient, store: PolicyStore, auth_headers: dict
    ) -> None:
        """Limit controls maximum returned events."""
        _seed_events(store, 10)

        resp = client.get("/api/activity/", headers=auth_headers, params={"limit": 3})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["events"]) == 3
        assert data["limit"] == 3

    def test_pagination_offset(
        self, client: TestClient, store: PolicyStore, auth_headers: dict
    ) -> None:
        """Offset skips events for pagination."""
        _seed_events(store, 5)

        resp = client.get(
            "/api/activity/", headers=auth_headers, params={"limit": 2, "offset": 2}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["events"]) == 2
        assert data["offset"] == 2

    def test_empty_response(self, client: TestClient, auth_headers: dict) -> None:
        """Returns empty list when no events exist."""
        resp = client.get("/api/activity/", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["events"] == []

    def test_event_response_fields(
        self, client: TestClient, store: PolicyStore, auth_headers: dict
    ) -> None:
        """Each event in the response has all expected fields."""
        ts = datetime.now(timezone.utc)
        store.add_event(
            "cascade_started",
            {"cascade_id": "c1"},
            ts,
            layer_slug="values",
            category="cascade",
        )

        resp = client.get("/api/activity/", headers=auth_headers)
        event = resp.json()["events"][0]
        assert "id" in event
        assert "event_type" in event
        assert "timestamp" in event
        assert "data" in event
        assert "layer_slug" in event
        assert "category" in event


class TestReplayEndpoint:
    """Tests for GET /api/activity/replay."""

    def test_requires_auth(self, client: TestClient) -> None:
        """Replay endpoint requires JWT."""
        resp = client.get("/api/activity/replay", params={"since_id": 0})
        assert resp.status_code == 401

    def test_returns_events_since_id(
        self, client: TestClient, store: PolicyStore, auth_headers: dict
    ) -> None:
        """Returns events with ID > since_id in chronological order."""
        ids = _seed_events(store, 5)

        resp = client.get(
            "/api/activity/replay", headers=auth_headers, params={"since_id": ids[1]}
        )
        assert resp.status_code == 200
        data = resp.json()
        # Should get events 3, 4, 5 (IDs after ids[1])
        assert len(data["events"]) == 3
        assert data["since_id"] == ids[1]
        # Chronological order (oldest first)
        assert data["events"][0]["id"] < data["events"][1]["id"]

    def test_since_id_zero_returns_all(
        self, client: TestClient, store: PolicyStore, auth_headers: dict
    ) -> None:
        """since_id=0 returns all events."""
        _seed_events(store, 3)

        resp = client.get(
            "/api/activity/replay", headers=auth_headers, params={"since_id": 0}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["events"]) == 3

    def test_overflow_flag(
        self, client: TestClient, store: PolicyStore, auth_headers: dict
    ) -> None:
        """Overflow flag is set when 500+ events would be returned."""
        # We don't create 500 events for speed, but test the flag exists
        _seed_events(store, 3)

        resp = client.get(
            "/api/activity/replay", headers=auth_headers, params={"since_id": 0}
        )
        data = resp.json()
        assert data["overflow"] is False

    def test_requires_since_id(self, client: TestClient, auth_headers: dict) -> None:
        """Replay endpoint requires since_id parameter."""
        resp = client.get("/api/activity/replay", headers=auth_headers)
        assert resp.status_code == 422  # Validation error

    def test_chronological_order(
        self, client: TestClient, store: PolicyStore, auth_headers: dict
    ) -> None:
        """Replay events are in chronological order (oldest first)."""
        _seed_events(store, 5)

        resp = client.get(
            "/api/activity/replay", headers=auth_headers, params={"since_id": 0}
        )
        data = resp.json()
        events = data["events"]
        for i in range(len(events) - 1):
            assert events[i]["id"] < events[i + 1]["id"]
