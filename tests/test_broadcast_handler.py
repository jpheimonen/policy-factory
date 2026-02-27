"""Tests for the BroadcastHandler — event persistence + WebSocket bridge."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from policy_factory.events import CascadeStarted, EventEmitter
from policy_factory.server.broadcast import BroadcastHandler
from policy_factory.server.ws import ConnectionManager
from policy_factory.store import PolicyStore


@pytest.fixture
def store(tmp_path: Path) -> PolicyStore:
    """Provide a fresh PolicyStore."""
    return PolicyStore(tmp_path / "test.db")


@pytest.fixture
def ws_manager() -> ConnectionManager:
    """Provide a ConnectionManager instance."""
    return ConnectionManager()


@pytest.fixture
def emitter() -> EventEmitter:
    """Provide an EventEmitter instance."""
    return EventEmitter()


@pytest.fixture
def handler(
    store: PolicyStore, ws_manager: ConnectionManager, emitter: EventEmitter
) -> BroadcastHandler:
    """Provide a BroadcastHandler wired to store, ws_manager, and emitter."""
    return BroadcastHandler(store=store, ws_manager=ws_manager, emitter=emitter)


class TestBroadcastHandler:
    """Tests for the BroadcastHandler."""

    @pytest.mark.asyncio
    async def test_persists_event_to_sqlite(
        self, handler: BroadcastHandler, emitter: EventEmitter, store: PolicyStore
    ) -> None:
        """Emitting an event persists it to SQLite."""
        event = CascadeStarted(cascade_id="c1", trigger_source="user_input")
        await emitter.emit(event)

        events = store.get_events()
        assert len(events) == 1
        assert events[0].event_type == "cascade_started"
        assert events[0].data["cascade_id"] == "c1"

    @pytest.mark.asyncio
    async def test_includes_db_id_in_broadcast(
        self, handler: BroadcastHandler, emitter: EventEmitter, ws_manager: ConnectionManager
    ) -> None:
        """The broadcast payload includes the database-generated event ID."""
        ws_manager.broadcast = AsyncMock()  # type: ignore

        event = CascadeStarted(cascade_id="c1")
        await emitter.emit(event)

        ws_manager.broadcast.assert_called_once()  # type: ignore
        payload = ws_manager.broadcast.call_args[0][0]  # type: ignore
        assert "db_id" in payload
        assert isinstance(payload["db_id"], int)

    @pytest.mark.asyncio
    async def test_broadcast_payload_has_event_data(
        self, handler: BroadcastHandler, emitter: EventEmitter, ws_manager: ConnectionManager
    ) -> None:
        """The broadcast payload contains the full event data."""
        ws_manager.broadcast = AsyncMock()  # type: ignore

        event = CascadeStarted(cascade_id="c1", trigger_source="heartbeat")
        await emitter.emit(event)

        payload = ws_manager.broadcast.call_args[0][0]  # type: ignore
        assert payload["event_type"] == "cascade_started"
        assert payload["cascade_id"] == "c1"
        assert payload["trigger_source"] == "heartbeat"

    @pytest.mark.asyncio
    async def test_category_derived_from_event_type(
        self, handler: BroadcastHandler, emitter: EventEmitter, store: PolicyStore
    ) -> None:
        """The category is derived from the event type during persistence."""
        event = CascadeStarted(cascade_id="c1")
        await emitter.emit(event)

        events = store.get_events()
        assert events[0].category == "cascade"

    @pytest.mark.asyncio
    async def test_shutdown_unsubscribes(
        self, handler: BroadcastHandler, emitter: EventEmitter, store: PolicyStore
    ) -> None:
        """After shutdown, no more events are persisted."""
        handler.shutdown()

        await emitter.emit(CascadeStarted(cascade_id="c1"))

        events = store.get_events()
        assert len(events) == 0

    @pytest.mark.asyncio
    async def test_broadcast_to_empty_ws_no_error(
        self, handler: BroadcastHandler, emitter: EventEmitter
    ) -> None:
        """Emitting with no WebSocket clients connected doesn't error."""
        event = CascadeStarted(cascade_id="c1")
        await emitter.emit(event)  # Should not raise
