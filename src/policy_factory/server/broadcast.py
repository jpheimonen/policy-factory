"""Broadcast handler — bridges EventEmitter to persistence and WebSocket.

Analogous to cc-runner's ``WebRenderer``: subscribes to the EventEmitter,
persists each event to SQLite, and broadcasts it to all connected WebSocket
clients (including the database-generated event ID for deduplication).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from policy_factory.events import BaseEvent, EventEmitter, get_event_category

if TYPE_CHECKING:
    from policy_factory.server.ws import ConnectionManager
    from policy_factory.store import PolicyStore

logger = logging.getLogger(__name__)


class BroadcastHandler:
    """Bridges EventEmitter → SQLite persistence → WebSocket broadcast.

    Created during app startup and subscribed to the EventEmitter.
    On each event:
    1. Persists the event to SQLite (receiving a database-generated ID).
    2. Broadcasts the event to all WebSocket clients, including the DB ID.
    """

    def __init__(
        self,
        store: PolicyStore,
        ws_manager: ConnectionManager,
        emitter: EventEmitter,
    ) -> None:
        self.store = store
        self.ws_manager = ws_manager
        self.emitter = emitter
        self.emitter.subscribe(self._handle_event)

    async def _handle_event(self, event: BaseEvent) -> None:
        """Handle an event: persist to SQLite, then broadcast via WebSocket."""
        event_data = event.to_dict()

        # Derive layer_slug from the event data (if present)
        layer_slug = event_data.get("layer_slug")

        # Derive category from the event type
        category = get_event_category(event.event_type)

        # Persist to SQLite
        try:
            db_id = self.store.add_event(
                event_type=event.event_type,
                data=event_data,
                timestamp=event.timestamp,
                layer_slug=layer_slug,
                category=category,
            )
        except Exception:
            logger.exception("Failed to persist event %s", event.event_type)
            # Still try to broadcast even if persistence fails
            db_id = None

        # Broadcast via WebSocket — include DB-generated ID
        broadcast_payload = event_data.copy()
        if db_id is not None:
            broadcast_payload["db_id"] = db_id

        try:
            await self.ws_manager.broadcast(broadcast_payload)
        except Exception:
            logger.exception("Failed to broadcast event %s", event.event_type)

    def shutdown(self) -> None:
        """Unsubscribe from the EventEmitter."""
        self.emitter.unsubscribe(self._handle_event)
