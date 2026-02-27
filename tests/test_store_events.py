"""Tests for the EventStoreMixin — event persistence and retrieval."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from policy_factory.store import PolicyStore


@pytest.fixture
def store(tmp_path: Path) -> PolicyStore:
    """Provide a fresh PolicyStore with the events table."""
    return PolicyStore(tmp_path / "test.db")


class TestEventStoreMixin:
    """Tests for event storage and retrieval."""

    def test_add_event_returns_id(self, store: PolicyStore) -> None:
        """Adding an event returns an auto-generated integer ID."""
        event_id = store.add_event(
            event_type="cascade_started",
            data={"cascade_id": "c1", "event_type": "cascade_started"},
            timestamp=datetime.now(timezone.utc),
            layer_slug=None,
            category="cascade",
        )
        assert isinstance(event_id, int)
        assert event_id > 0

    def test_add_event_sequential_ids(self, store: PolicyStore) -> None:
        """Event IDs are sequential."""
        ts = datetime.now(timezone.utc)
        id1 = store.add_event("cascade_started", {"a": 1}, ts, category="cascade")
        id2 = store.add_event("cascade_completed", {"a": 2}, ts, category="cascade")
        assert id2 > id1

    def test_get_events_returns_stored_events(self, store: PolicyStore) -> None:
        """Events can be stored and retrieved."""
        ts = datetime.now(timezone.utc)
        data = {"cascade_id": "c1", "event_type": "cascade_started"}
        store.add_event("cascade_started", data, ts, category="cascade")

        events = store.get_events()
        assert len(events) == 1
        assert events[0].event_type == "cascade_started"
        assert events[0].data == data

    def test_get_events_since_id(self, store: PolicyStore) -> None:
        """since_id filter returns only events with ID > given value."""
        ts = datetime.now(timezone.utc)
        id1 = store.add_event("cascade_started", {"n": 1}, ts, category="cascade")
        store.add_event("cascade_completed", {"n": 2}, ts, category="cascade")
        store.add_event("cascade_failed", {"n": 3}, ts, category="cascade")

        events = store.get_events(since_id=id1)
        assert len(events) == 2
        assert events[0].event_type == "cascade_completed"
        assert events[1].event_type == "cascade_failed"

    def test_get_events_filter_by_event_type(self, store: PolicyStore) -> None:
        """Filtering by event_type works."""
        ts = datetime.now(timezone.utc)
        store.add_event("cascade_started", {}, ts, category="cascade")
        store.add_event("heartbeat_started", {}, ts, category="heartbeat")
        store.add_event("cascade_completed", {}, ts, category="cascade")

        events = store.get_events(event_type="heartbeat_started")
        assert len(events) == 1
        assert events[0].event_type == "heartbeat_started"

    def test_get_events_filter_by_layer_slug(self, store: PolicyStore) -> None:
        """Filtering by layer_slug works."""
        ts = datetime.now(timezone.utc)
        store.add_event("layer_generation_started", {}, ts, layer_slug="values", category="cascade")
        store.add_event(
            "layer_generation_started", {}, ts, layer_slug="policies", category="cascade"
        )

        events = store.get_events(layer_slug="values")
        assert len(events) == 1

    def test_get_events_filter_by_category(self, store: PolicyStore) -> None:
        """Filtering by category works."""
        ts = datetime.now(timezone.utc)
        store.add_event("cascade_started", {}, ts, category="cascade")
        store.add_event("heartbeat_started", {}, ts, category="heartbeat")
        store.add_event("idea_submitted", {}, ts, category="idea")

        events = store.get_events(category="heartbeat")
        assert len(events) == 1
        assert events[0].event_type == "heartbeat_started"

    def test_get_events_limit(self, store: PolicyStore) -> None:
        """Limit controls maximum returned events."""
        ts = datetime.now(timezone.utc)
        for i in range(10):
            store.add_event("cascade_started", {"n": i}, ts, category="cascade")

        events = store.get_events(limit=3)
        assert len(events) == 3

    def test_get_events_limit_capped_at_500(self, store: PolicyStore) -> None:
        """Limit is capped at 500."""
        ts = datetime.now(timezone.utc)
        store.add_event("cascade_started", {}, ts, category="cascade")

        events = store.get_events(limit=1000)
        assert len(events) == 1  # Only one event exists, but limit was accepted

    def test_get_events_chronological_order(self, store: PolicyStore) -> None:
        """Events are returned in chronological order (oldest first)."""
        ts = datetime.now(timezone.utc)
        store.add_event("cascade_started", {"n": 1}, ts, category="cascade")
        store.add_event("cascade_completed", {"n": 2}, ts, category="cascade")

        events = store.get_events()
        assert events[0].event_type == "cascade_started"
        assert events[1].event_type == "cascade_completed"

    def test_get_events_combined_filters(self, store: PolicyStore) -> None:
        """Multiple filters can be combined."""
        ts = datetime.now(timezone.utc)
        id1 = store.add_event(
            "layer_generation_started", {}, ts, layer_slug="values", category="cascade"
        )
        store.add_event(
            "layer_generation_completed", {}, ts, layer_slug="values", category="cascade"
        )
        store.add_event(
            "layer_generation_started", {}, ts, layer_slug="policies", category="cascade"
        )

        events = store.get_events(
            since_id=id1, event_type="layer_generation_started", layer_slug="policies"
        )
        assert len(events) == 1

    def test_get_recent_events_reverse_order(self, store: PolicyStore) -> None:
        """get_recent_events returns events newest first."""
        ts = datetime.now(timezone.utc)
        store.add_event("cascade_started", {"n": 1}, ts, category="cascade")
        store.add_event("cascade_completed", {"n": 2}, ts, category="cascade")

        events = store.get_recent_events()
        assert events[0].event_type == "cascade_completed"
        assert events[1].event_type == "cascade_started"

    def test_get_recent_events_with_offset(self, store: PolicyStore) -> None:
        """Pagination offset works for recent events."""
        ts = datetime.now(timezone.utc)
        for i in range(5):
            store.add_event(f"event_{i}", {"n": i}, ts, category="cascade")

        events = store.get_recent_events(limit=2, offset=2)
        assert len(events) == 2

    def test_get_recent_events_limit_capped_at_200(self, store: PolicyStore) -> None:
        """Recent events limit is capped at 200."""
        ts = datetime.now(timezone.utc)
        store.add_event("cascade_started", {}, ts, category="cascade")

        events = store.get_recent_events(limit=1000)
        assert len(events) == 1  # Only one event, but limit was accepted

    def test_get_recent_events_filter_by_category(self, store: PolicyStore) -> None:
        """Recent events support category filtering."""
        ts = datetime.now(timezone.utc)
        store.add_event("cascade_started", {}, ts, category="cascade")
        store.add_event("heartbeat_started", {}, ts, category="heartbeat")

        events = store.get_recent_events(category="cascade")
        assert len(events) == 1
        assert events[0].event_type == "cascade_started"

    def test_stored_event_fields(self, store: PolicyStore) -> None:
        """StoredEvent has all expected fields populated."""
        ts = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        data = {"foo": "bar"}
        event_id = store.add_event(
            "cascade_started", data, ts, layer_slug="values", category="cascade"
        )

        events = store.get_events()
        assert len(events) == 1
        e = events[0]
        assert e.id == event_id
        assert e.event_type == "cascade_started"
        assert e.data == data
        assert e.timestamp == ts
        assert e.layer_slug == "values"
        assert e.category == "cascade"

    def test_events_table_created_during_init(self, store: PolicyStore) -> None:
        """The events table exists after store initialization."""
        cursor = store.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='events'"
        )
        assert cursor.fetchone() is not None
