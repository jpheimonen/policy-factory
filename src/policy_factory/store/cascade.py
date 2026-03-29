"""Cascade store mixin for cascade run tracking, lock management, and queue.

Provides SQLite persistence for:
- Cascade run records (tracking each cascade execution).
- Single-writer lock (represented by running/paused cascade records).
- Cascade queue (FIFO queue of pending cascade requests).
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

# Valid cascade statuses
CascadeStatus = Literal["running", "paused", "completed", "failed", "cancelled"]

# Valid cascade trigger sources
TriggerSource = Literal["user_input", "layer_refresh", "heartbeat", "seed"]

# Valid cascade steps within a layer
CascadeStep = Literal["generation", "critics", "synthesis"]


@dataclass
class CascadeRun:
    """A cascade run record from the database."""

    id: str
    trigger_source: str
    starting_layer: str
    current_layer: str
    current_step: str  # generation, critics, synthesis
    status: str  # running, paused, completed, failed, cancelled
    error_message: str | None
    error_layer: str | None
    context: str | None  # Additional context (e.g. user input text)
    created_at: datetime
    completed_at: datetime | None


@dataclass
class QueueEntry:
    """A queued cascade request."""

    id: str
    trigger_source: str
    starting_layer: str
    context: str | None
    queued_at: datetime


@dataclass
class PendingCascadeEntry:
    """A pending conversation cascade awaiting user approval.

    Unlike the cascade queue which auto-processes, pending cascades
    persist until the user explicitly triggers or dismisses them.
    """

    id: str
    conversation_id: str
    starting_layer: str
    affected_layers: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class CascadeStoreMixin:
    """Mixin providing cascade run tracking, lock management, and queue.

    Requires ``self.conn`` (a ``sqlite3.Connection``) to be set by the
    base store class.
    """

    conn: sqlite3.Connection  # Provided by BaseStore

    # -----------------------------------------------------------------------
    # Cascade CRUD
    # -----------------------------------------------------------------------

    def create_cascade(
        self,
        trigger_source: str,
        starting_layer: str,
        context: str | None = None,
    ) -> str:
        """Create a cascade run record.

        Does NOT acquire the lock — that is a separate call.

        Args:
            trigger_source: What triggered the cascade (user_input, layer_refresh,
                heartbeat, seed).
            starting_layer: Layer slug where the cascade starts.
            context: Optional context data (e.g. user input text).

        Returns:
            The generated cascade run ID.
        """
        cascade_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "INSERT INTO cascade_runs "
            "(id, trigger_source, starting_layer, current_layer, current_step, "
            " status, error_message, error_layer, context, created_at, completed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                cascade_id,
                trigger_source,
                starting_layer,
                starting_layer,  # current_layer starts at starting_layer
                "generation",  # first step
                "running",  # initial status
                None,
                None,
                context,
                now,
                None,
            ),
        )
        self.conn.commit()
        return cascade_id

    def update_cascade_progress(
        self,
        cascade_id: str,
        current_layer: str,
        current_step: str,
    ) -> None:
        """Update the current position in the cascade.

        Called by the orchestrator at each state transition.

        Args:
            cascade_id: The cascade run ID.
            current_layer: The layer currently being processed.
            current_step: The step within the layer (generation, critics, synthesis).
        """
        self.conn.execute(
            "UPDATE cascade_runs SET current_layer = ?, current_step = ? WHERE id = ?",
            (current_layer, current_step, cascade_id),
        )
        self.conn.commit()

    def update_cascade_status(
        self,
        cascade_id: str,
        status: str,
        error_message: str | None = None,
        error_layer: str | None = None,
    ) -> None:
        """Update the cascade status.

        Used for transitions to paused, completed, failed, or cancelled.

        Args:
            cascade_id: The cascade run ID.
            status: The new status.
            error_message: Optional error message (for paused/failed).
            error_layer: Optional layer slug where error occurred.
        """
        completed_at = None
        if status in ("completed", "failed", "cancelled"):
            completed_at = datetime.now(timezone.utc).isoformat()

        self.conn.execute(
            "UPDATE cascade_runs "
            "SET status = ?, error_message = ?, error_layer = ?, completed_at = ? "
            "WHERE id = ?",
            (status, error_message, error_layer, completed_at, cascade_id),
        )
        self.conn.commit()

    def get_cascade(self, cascade_id: str) -> CascadeRun | None:
        """Return the full cascade run record by ID.

        Args:
            cascade_id: The cascade run ID.

        Returns:
            A CascadeRun dataclass, or None if not found.
        """
        row = self.conn.execute(
            "SELECT * FROM cascade_runs WHERE id = ?",
            (cascade_id,),
        ).fetchone()
        if not row:
            return None
        return self._row_to_cascade_run(row)

    def list_cascades(
        self,
        limit: int = 20,
        offset: int = 0,
    ) -> list[CascadeRun]:
        """Return recent cascade runs in reverse chronological order.

        Args:
            limit: Maximum number of results.
            offset: Number of results to skip.

        Returns:
            List of CascadeRun records.
        """
        rows = self.conn.execute(
            "SELECT * FROM cascade_runs ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [self._row_to_cascade_run(r) for r in rows]

    # -----------------------------------------------------------------------
    # Lock management
    # -----------------------------------------------------------------------

    def acquire_lock(self, cascade_id: str) -> bool:
        """Attempt to acquire the cascade lock.

        The lock is represented by a running or paused cascade run record.
        Since ``create_cascade()`` sets status to 'running', the new
        cascade already holds the lock. This method checks that no *other*
        cascade was running/paused at the time.

        Args:
            cascade_id: The cascade run ID that wants the lock.

        Returns:
            True if the lock was acquired (no other cascade is running/paused),
            False if the lock is already held by a different cascade.
        """
        row = self.conn.execute(
            "SELECT id FROM cascade_runs "
            "WHERE status IN ('running', 'paused') AND id != ? "
            "LIMIT 1",
            (cascade_id,),
        ).fetchone()
        if row:
            return False
        # Lock is free (the only running cascade is this one)
        return True

    def release_lock(self, cascade_id: str, terminal_status: str) -> None:
        """Release the cascade lock by setting the cascade to a terminal state.

        Args:
            cascade_id: The cascade run ID.
            terminal_status: The terminal status (completed, failed, cancelled).
        """
        self.update_cascade_status(cascade_id, terminal_status)

    def is_lock_held(self) -> tuple[bool, str | None]:
        """Check whether the cascade lock is currently held.

        Returns:
            A tuple of (is_held, cascade_id_holding_lock).
            If no lock is held, returns (False, None).
        """
        row = self.conn.execute(
            "SELECT id FROM cascade_runs WHERE status IN ('running', 'paused') "
            "ORDER BY created_at DESC LIMIT 1",
        ).fetchone()
        if row:
            return True, row["id"]
        return False, None

    def get_active_cascade(self) -> CascadeRun | None:
        """Return the currently running or paused cascade, or None."""
        row = self.conn.execute(
            "SELECT * FROM cascade_runs WHERE status IN ('running', 'paused') "
            "ORDER BY created_at DESC LIMIT 1",
        ).fetchone()
        if not row:
            return None
        return self._row_to_cascade_run(row)

    # -----------------------------------------------------------------------
    # Queue management
    # -----------------------------------------------------------------------

    def enqueue_cascade(
        self,
        trigger_source: str,
        starting_layer: str,
        context: str | None = None,
    ) -> tuple[str, int]:
        """Add a cascade request to the queue.

        Args:
            trigger_source: What triggered the cascade.
            starting_layer: Layer slug where the cascade starts.
            context: Optional context data.

        Returns:
            Tuple of (queue_entry_id, queue_position). Position is 1-based.
        """
        queue_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "INSERT INTO cascade_queue "
            "(id, trigger_source, starting_layer, context, queued_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (queue_id, trigger_source, starting_layer, context, now),
        )
        self.conn.commit()

        position = self.get_queue_depth()
        return queue_id, position

    def dequeue_cascade(self) -> QueueEntry | None:
        """Remove and return the oldest entry from the queue (FIFO).

        Returns:
            The oldest QueueEntry, or None if the queue is empty.
        """
        row = self.conn.execute(
            "SELECT * FROM cascade_queue ORDER BY queued_at ASC LIMIT 1",
        ).fetchone()
        if not row:
            return None

        entry = self._row_to_queue_entry(row)
        self.conn.execute("DELETE FROM cascade_queue WHERE id = ?", (entry.id,))
        self.conn.commit()
        return entry

    def get_queue(self) -> list[QueueEntry]:
        """Return all queued cascade requests in order (oldest first).

        Returns:
            List of QueueEntry records in FIFO order.
        """
        rows = self.conn.execute(
            "SELECT * FROM cascade_queue ORDER BY queued_at ASC",
        ).fetchall()
        return [self._row_to_queue_entry(r) for r in rows]

    def cancel_queued_cascade(self, queue_id: str) -> bool:
        """Remove a specific entry from the queue.

        Args:
            queue_id: The queue entry ID to remove.

        Returns:
            True if an entry was removed, False if not found.
        """
        cursor = self.conn.execute(
            "DELETE FROM cascade_queue WHERE id = ?", (queue_id,)
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def get_queue_depth(self) -> int:
        """Return the number of entries in the queue."""
        row = self.conn.execute(
            "SELECT COUNT(*) as count FROM cascade_queue"
        ).fetchone()
        return row["count"]

    # -----------------------------------------------------------------------
    # Pending conversation cascade management
    # -----------------------------------------------------------------------

    def create_or_update_pending_cascade(
        self,
        conversation_id: str,
        starting_layer: str,
    ) -> PendingCascadeEntry:
        """Create or update a pending conversation cascade.

        Unlike the normal cascade queue which auto-processes, pending cascades
        persist until the user explicitly triggers or dismisses them.

        If no pending cascade exists, creates one with the given starting_layer.
        If a pending cascade already exists:
        - If the new starting_layer is lower in hierarchy, updates starting_layer
        - Adds the new layer to affected_layers if not already present
        - Updates the updated_at timestamp

        Args:
            conversation_id: ID of the conversation that triggered this.
            starting_layer: The layer that was edited.

        Returns:
            The created or updated PendingCascadeEntry.
        """
        from policy_factory.data.layers import get_layer

        now = datetime.now(timezone.utc).isoformat()

        # Check for existing pending cascade
        existing = self.get_pending_cascade()

        if existing is None:
            # Create new pending cascade
            entry_id = str(uuid.uuid4())
            affected = [starting_layer]
            self.conn.execute(
                "INSERT INTO pending_conversation_cascade "
                "(id, conversation_id, starting_layer, affected_layers, "
                " created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    entry_id,
                    conversation_id,
                    starting_layer,
                    json.dumps(affected),
                    now,
                    now,
                ),
            )
            self.conn.commit()
            return PendingCascadeEntry(
                id=entry_id,
                conversation_id=conversation_id,
                starting_layer=starting_layer,
                affected_layers=affected,
                created_at=datetime.fromisoformat(now),
                updated_at=datetime.fromisoformat(now),
            )

        # Update existing pending cascade
        new_starting_layer = existing.starting_layer
        new_affected = list(existing.affected_layers)

        # Check if new layer is lower in hierarchy (smaller position number)
        existing_layer_info = get_layer(existing.starting_layer)
        new_layer_info = get_layer(starting_layer)

        if existing_layer_info and new_layer_info:
            if new_layer_info.position < existing_layer_info.position:
                new_starting_layer = starting_layer

        # Add to affected layers if not present
        if starting_layer not in new_affected:
            new_affected.append(starting_layer)

        self.conn.execute(
            "UPDATE pending_conversation_cascade "
            "SET conversation_id = ?, starting_layer = ?, affected_layers = ?, "
            "    updated_at = ? "
            "WHERE id = ?",
            (
                conversation_id,
                new_starting_layer,
                json.dumps(new_affected),
                now,
                existing.id,
            ),
        )
        self.conn.commit()

        return PendingCascadeEntry(
            id=existing.id,
            conversation_id=conversation_id,
            starting_layer=new_starting_layer,
            affected_layers=new_affected,
            created_at=existing.created_at,
            updated_at=datetime.fromisoformat(now),
        )

    def get_pending_cascade(self) -> PendingCascadeEntry | None:
        """Return the current pending cascade if one exists.

        Only one pending cascade should exist at a time (single-user system).

        Returns:
            The PendingCascadeEntry, or None if no pending cascade exists.
        """
        row = self.conn.execute(
            "SELECT * FROM pending_conversation_cascade LIMIT 1"
        ).fetchone()
        if not row:
            return None
        return self._row_to_pending_cascade_entry(row)

    def get_pending_cascade_by_conversation(
        self,
        conversation_id: str,
    ) -> PendingCascadeEntry | None:
        """Return pending cascade associated with a specific conversation.

        Args:
            conversation_id: The conversation ID to filter by.

        Returns:
            The PendingCascadeEntry if found, None otherwise.
        """
        row = self.conn.execute(
            "SELECT * FROM pending_conversation_cascade WHERE conversation_id = ?",
            (conversation_id,),
        ).fetchone()
        if not row:
            return None
        return self._row_to_pending_cascade_entry(row)

    def clear_pending_cascade(self) -> bool:
        """Delete the pending cascade record.

        Used after the cascade is triggered or dismissed.

        Returns:
            True if a record was deleted, False if none existed.
        """
        cursor = self.conn.execute(
            "DELETE FROM pending_conversation_cascade"
        )
        self.conn.commit()
        return cursor.rowcount > 0

    # -----------------------------------------------------------------------
    # Row conversion helpers
    # -----------------------------------------------------------------------

    def _row_to_cascade_run(self, row: sqlite3.Row) -> CascadeRun:
        """Convert a database row to a CascadeRun dataclass."""
        return CascadeRun(
            id=row["id"],
            trigger_source=row["trigger_source"],
            starting_layer=row["starting_layer"],
            current_layer=row["current_layer"],
            current_step=row["current_step"],
            status=row["status"],
            error_message=row["error_message"],
            error_layer=row["error_layer"],
            context=row["context"],
            created_at=datetime.fromisoformat(row["created_at"]),
            completed_at=(
                datetime.fromisoformat(row["completed_at"])
                if row["completed_at"]
                else None
            ),
        )

    def _row_to_queue_entry(self, row: sqlite3.Row) -> QueueEntry:
        """Convert a database row to a QueueEntry dataclass."""
        return QueueEntry(
            id=row["id"],
            trigger_source=row["trigger_source"],
            starting_layer=row["starting_layer"],
            context=row["context"],
            queued_at=datetime.fromisoformat(row["queued_at"]),
        )

    def _row_to_pending_cascade_entry(
        self, row: sqlite3.Row
    ) -> PendingCascadeEntry:
        """Convert a database row to a PendingCascadeEntry dataclass."""
        affected_layers = json.loads(row["affected_layers"])
        return PendingCascadeEntry(
            id=row["id"],
            conversation_id=row["conversation_id"],
            starting_layer=row["starting_layer"],
            affected_layers=affected_layers,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
