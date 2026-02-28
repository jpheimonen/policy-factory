"""Integration tests for event persistence and activity feed.

Tests that cascade and idea events appear in the activity endpoint,
and that filtering by type and layer works correctly.
"""

from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import policy_factory.auth as auth_mod
from policy_factory.auth import create_access_token, hash_password
from policy_factory.data.layers import LAYER_SLUGS
from policy_factory.events import EventEmitter
from policy_factory.server.app import create_app
from policy_factory.server.ws import ConnectionManager
from policy_factory.store import PolicyStore


@pytest.fixture(autouse=True)
def _configure_auth():
    original_key = auth_mod.JWT_SECRET_KEY
    original_expiry = auth_mod.JWT_EXPIRY_HOURS
    auth_mod.JWT_SECRET_KEY = "test-secret-key-for-activity-integration"
    auth_mod.JWT_EXPIRY_HOURS = 24
    yield
    auth_mod.JWT_SECRET_KEY = original_key
    auth_mod.JWT_EXPIRY_HOURS = original_expiry


@pytest.fixture
def store(tmp_path: Path) -> PolicyStore:
    return PolicyStore(tmp_path / "test.db")


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    d = tmp_path / "data"
    for slug in LAYER_SLUGS:
        (d / slug).mkdir(parents=True, exist_ok=True)
        (d / slug / "README.md").write_text(f"# {slug}\n\nSummary.")
    return d


@pytest.fixture
def client(
    store: PolicyStore, data_dir: Path
) -> Generator[TestClient, None, None]:
    app = create_app(
        store=store,
        data_dir=data_dir,
        event_emitter=EventEmitter(),
        ws_manager=ConnectionManager(),
    )
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_headers(store: PolicyStore) -> dict[str, str]:
    hashed = hash_password("testpassword")
    user_id = store.create_user("test@example.com", hashed, "admin")
    token = create_access_token(user_id, "test@example.com", "admin")
    return {"Authorization": f"Bearer {token}"}


def _extract_events(response_json):
    """Extract events list from API response, handling both list and dict formats."""
    if isinstance(response_json, list):
        return response_json
    if isinstance(response_json, dict) and "events" in response_json:
        return response_json["events"]
    return response_json


class TestCascadeEventsInActivity:
    """Cascade events appear in the activity feed."""

    def test_cascade_events_in_activity(
        self, client: TestClient, auth_headers: dict[str, str], store: PolicyStore
    ) -> None:
        """Trigger cascade events and verify they appear in activity."""
        # Add cascade events to the store
        store.add_event(
            event_type="cascade_started",
            data={"cascade_id": "test-cascade-1", "trigger_source": "manual"},
            timestamp=datetime.now(timezone.utc),
            layer_slug="values",
            category="cascade",
        )
        store.add_event(
            event_type="cascade_completed",
            data={"cascade_id": "test-cascade-1"},
            timestamp=datetime.now(timezone.utc),
            layer_slug="policies",
            category="cascade",
        )

        resp = client.get("/api/activity/", headers=auth_headers)
        assert resp.status_code == 200
        events = _extract_events(resp.json())
        assert isinstance(events, list)
        assert len(events) >= 2

        event_types = [e["event_type"] for e in events]
        assert "cascade_started" in event_types
        assert "cascade_completed" in event_types


class TestIdeaEventsInActivity:
    """Idea events appear in the activity feed."""

    def test_idea_events_in_activity(
        self, client: TestClient, auth_headers: dict[str, str], store: PolicyStore
    ) -> None:
        """Idea submission and evaluation events appear in activity."""
        store.add_event(
            event_type="idea_submitted",
            data={"idea_id": "idea-1", "text": "Test idea"},
            timestamp=datetime.now(timezone.utc),
            category="idea",
        )
        store.add_event(
            event_type="idea_evaluation_completed",
            data={"idea_id": "idea-1"},
            timestamp=datetime.now(timezone.utc),
            category="idea",
        )

        resp = client.get("/api/activity/", headers=auth_headers)
        assert resp.status_code == 200
        events = _extract_events(resp.json())

        event_types = [e["event_type"] for e in events]
        assert "idea_submitted" in event_types
        assert "idea_evaluation_completed" in event_types


class TestActivityFiltering:
    """Activity endpoint filtering by event type and layer."""

    def test_filter_by_event_type(
        self, client: TestClient, auth_headers: dict[str, str], store: PolicyStore
    ) -> None:
        """Filter by event type returns only matching events."""
        store.add_event(
            event_type="cascade_started",
            data={"cascade_id": "c1"},
            timestamp=datetime.now(timezone.utc),
            category="cascade",
        )
        store.add_event(
            event_type="idea_submitted",
            data={"idea_id": "i1"},
            timestamp=datetime.now(timezone.utc),
            category="idea",
        )

        # Filter for cascade events only
        resp = client.get(
            "/api/activity/?event_type=cascade_started",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        events = _extract_events(resp.json())
        for e in events:
            assert e["event_type"] == "cascade_started"

    def test_filter_by_category(
        self, client: TestClient, auth_headers: dict[str, str], store: PolicyStore
    ) -> None:
        """Filter by category returns only matching events."""
        store.add_event(
            event_type="cascade_started",
            data={"cascade_id": "c1"},
            timestamp=datetime.now(timezone.utc),
            category="cascade",
        )
        store.add_event(
            event_type="idea_submitted",
            data={"idea_id": "i1"},
            timestamp=datetime.now(timezone.utc),
            category="idea",
        )

        resp = client.get(
            "/api/activity/?category=cascade",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        events = _extract_events(resp.json())
        for e in events:
            assert e.get("category") == "cascade" or e["event_type"].startswith("cascade")

    def test_filter_by_layer(
        self, client: TestClient, auth_headers: dict[str, str], store: PolicyStore
    ) -> None:
        """Filter by layer returns only events for that layer."""
        store.add_event(
            event_type="cascade_started",
            data={"cascade_id": "c1"},
            timestamp=datetime.now(timezone.utc),
            layer_slug="values",
            category="cascade",
        )
        store.add_event(
            event_type="cascade_started",
            data={"cascade_id": "c2"},
            timestamp=datetime.now(timezone.utc),
            layer_slug="policies",
            category="cascade",
        )

        resp = client.get(
            "/api/activity/?layer=values",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        events = _extract_events(resp.json())
        for e in events:
            assert e.get("layer_slug") == "values" or e.get("layer") == "values"
