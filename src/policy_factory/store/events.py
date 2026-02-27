"""Event storage mixin for Policy Factory.

Provides SQLite persistence for typed events — used by the broadcast
handler to store events and by the activity REST endpoint to retrieve
them for replay and the activity feed.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime


@dataclass
class StoredEvent:
    """An event as persisted in the database."""

    id: int
    event_type: str
    data: dict
    timestamp: datetime
    layer_slug: str | None
    category: str | None


class EventStoreMixin:
    """Mixin providing event persistence and retrieval.

    Requires ``self.conn`` (a ``sqlite3.Connection``) to be set by the
    base store class.
    """

    conn: sqlite3.Connection  # Provided by BaseStore

    def add_event(
        self,
        event_type: str,
        data: dict,
        timestamp: datetime,
        layer_slug: str | None = None,
        category: str | None = None,
    ) -> int:
        """Persist an event and return its auto-generated ID.

        Args:
            event_type: The event type string (e.g. ``"cascade_started"``).
            data: The full serialised event as a dictionary.
            timestamp: Event timestamp.
            layer_slug: Optional layer slug for filtering.
            category: Optional event category (cascade/heartbeat/idea/system).

        Returns:
            The database-generated integer ID.
        """
        cursor = self.conn.execute(
            "INSERT INTO events (event_type, data, timestamp, layer_slug, category) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                event_type,
                json.dumps(data),
                timestamp.isoformat(),
                layer_slug,
                category,
            ),
        )
        self.conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]

    def get_events(
        self,
        since_id: int | None = None,
        event_type: str | None = None,
        layer_slug: str | None = None,
        category: str | None = None,
        limit: int = 100,
    ) -> list[StoredEvent]:
        """Retrieve events with optional filters.

        Events are returned in chronological order (oldest first).
        The ``since_id`` parameter returns only events with ID > the
        given value — used for incremental replay after WebSocket
        reconnection.

        Args:
            since_id: If given, return only events with ID greater than this.
            event_type: Filter by event type string.
            layer_slug: Filter by layer slug.
            category: Filter by event category.
            limit: Maximum number of events to return (default 100, max 500).

        Returns:
            List of ``StoredEvent`` in chronological order.
        """
        limit = min(limit, 500)
        conditions: list[str] = []
        params: list[object] = []

        if since_id is not None:
            conditions.append("id > ?")
            params.append(since_id)
        if event_type is not None:
            conditions.append("event_type = ?")
            params.append(event_type)
        if layer_slug is not None:
            conditions.append("layer_slug = ?")
            params.append(layer_slug)
        if category is not None:
            conditions.append("category = ?")
            params.append(category)

        where = ""
        if conditions:
            where = "WHERE " + " AND ".join(conditions)

        query = f"SELECT * FROM events {where} ORDER BY id ASC LIMIT ?"
        params.append(limit)

        rows = self.conn.execute(query, params).fetchall()
        return [self._row_to_event(r) for r in rows]

    def get_recent_events(
        self,
        limit: int = 50,
        offset: int = 0,
        event_type: str | None = None,
        layer_slug: str | None = None,
        category: str | None = None,
    ) -> list[StoredEvent]:
        """Retrieve recent events in reverse chronological order.

        Used by the activity feed page. Supports pagination and filtering.

        Args:
            limit: Maximum events to return (default 50, max 200).
            offset: Number of events to skip for pagination.
            event_type: Filter by event type string.
            layer_slug: Filter by layer slug.
            category: Filter by event category.

        Returns:
            List of ``StoredEvent`` in reverse chronological order.
        """
        limit = min(limit, 200)
        conditions: list[str] = []
        params: list[object] = []

        if event_type is not None:
            conditions.append("event_type = ?")
            params.append(event_type)
        if layer_slug is not None:
            conditions.append("layer_slug = ?")
            params.append(layer_slug)
        if category is not None:
            conditions.append("category = ?")
            params.append(category)

        where = ""
        if conditions:
            where = "WHERE " + " AND ".join(conditions)

        query = f"SELECT * FROM events {where} ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = self.conn.execute(query, params).fetchall()
        return [self._row_to_event(r) for r in rows]

    def _row_to_event(self, row: sqlite3.Row) -> StoredEvent:
        """Convert a database row to a StoredEvent."""
        return StoredEvent(
            id=row["id"],
            event_type=row["event_type"],
            data=json.loads(row["data"]),
            timestamp=datetime.fromisoformat(row["timestamp"]),
            layer_slug=row["layer_slug"],
            category=row["category"],
        )
