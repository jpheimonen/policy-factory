"""Feedback memo store mixin for bidirectional layer feedback.

Feedback memos are transient, actionable notes that connect layers.
During generation, an agent for layer N may discover tensions or
feasibility issues with items in layers below N. These are recorded
as feedback memos targeting the lower layer. The next time the target
layer is regenerated, the pending memos are included as context.

Memos progress through: pending → accepted/dismissed.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class FeedbackMemo:
    """A feedback memo record from the database."""

    id: str
    source_layer: str
    target_layer: str
    cascade_id: str | None
    content: str
    referenced_items: list[str]  # Item filenames in the target layer
    status: str  # pending, accepted, dismissed
    created_at: datetime
    resolved_at: datetime | None


class FeedbackMemoMixin:
    """Mixin providing feedback memo CRUD.

    Requires ``self.conn`` (a ``sqlite3.Connection``) to be set by the
    base store class.
    """

    conn: sqlite3.Connection  # Provided by BaseStore

    # -----------------------------------------------------------------------
    # Create
    # -----------------------------------------------------------------------

    def create_feedback_memo(
        self,
        source_layer: str,
        target_layer: str,
        cascade_id: str | None,
        content: str,
        referenced_items: list[str] | None = None,
    ) -> str:
        """Create a pending feedback memo.

        Args:
            source_layer: Layer slug whose generation produced this memo.
            target_layer: Layer slug the memo is directed at.
            cascade_id: The cascade during which the memo was generated.
            content: Text content of the feedback.
            referenced_items: Optional list of item filenames in the
                target layer that the feedback relates to.

        Returns:
            The generated memo ID.
        """
        memo_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        items_json = json.dumps(referenced_items or [])

        self.conn.execute(
            "INSERT INTO feedback_memos "
            "(id, source_layer, target_layer, cascade_id, content, "
            " referenced_items, status, created_at, resolved_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                memo_id,
                source_layer,
                target_layer,
                cascade_id,
                content,
                items_json,
                "pending",
                now,
                None,
            ),
        )
        self.conn.commit()
        return memo_id

    # -----------------------------------------------------------------------
    # Read
    # -----------------------------------------------------------------------

    def get_memo(self, memo_id: str) -> FeedbackMemo | None:
        """Return a single memo by ID.

        Args:
            memo_id: The memo ID.

        Returns:
            A FeedbackMemo dataclass, or None if not found.
        """
        row = self.conn.execute(
            "SELECT * FROM feedback_memos WHERE id = ?",
            (memo_id,),
        ).fetchone()
        if not row:
            return None
        return self._row_to_feedback_memo(row)

    def get_pending_memos(self, target_layer: str) -> list[FeedbackMemo]:
        """Return all pending memos for a target layer.

        Sorted by creation date (oldest first) so the generation agent
        processes them in order.

        Args:
            target_layer: Layer slug to get pending memos for.

        Returns:
            List of pending FeedbackMemo records.
        """
        rows = self.conn.execute(
            "SELECT * FROM feedback_memos "
            "WHERE target_layer = ? AND status = 'pending' "
            "ORDER BY created_at ASC",
            (target_layer,),
        ).fetchall()
        return [self._row_to_feedback_memo(r) for r in rows]

    def get_pending_memo_count(self, target_layer: str) -> int:
        """Return the count of pending memos for a target layer.

        Args:
            target_layer: Layer slug.

        Returns:
            Number of pending memos.
        """
        row = self.conn.execute(
            "SELECT COUNT(*) as count FROM feedback_memos "
            "WHERE target_layer = ? AND status = 'pending'",
            (target_layer,),
        ).fetchone()
        return row["count"]

    def list_memos(
        self,
        target_layer: str | None = None,
        source_layer: str | None = None,
        memo_status: str | None = None,
        cascade_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[FeedbackMemo]:
        """Return memos with optional filtering.

        Args:
            target_layer: Filter by target layer slug.
            source_layer: Filter by source layer slug.
            memo_status: Filter by status (pending, accepted, dismissed).
            cascade_id: Filter by cascade ID.
            limit: Maximum number of results.
            offset: Number of results to skip.

        Returns:
            List of FeedbackMemo records in reverse chronological order.
        """
        conditions: list[str] = []
        params: list[object] = []

        if target_layer is not None:
            conditions.append("target_layer = ?")
            params.append(target_layer)
        if source_layer is not None:
            conditions.append("source_layer = ?")
            params.append(source_layer)
        if memo_status is not None:
            conditions.append("status = ?")
            params.append(memo_status)
        if cascade_id is not None:
            conditions.append("cascade_id = ?")
            params.append(cascade_id)

        where = ""
        if conditions:
            where = "WHERE " + " AND ".join(conditions)

        query = (
            f"SELECT * FROM feedback_memos {where} "
            "ORDER BY created_at DESC LIMIT ? OFFSET ?"
        )
        params.extend([limit, offset])

        rows = self.conn.execute(query, params).fetchall()
        return [self._row_to_feedback_memo(r) for r in rows]

    # -----------------------------------------------------------------------
    # Update
    # -----------------------------------------------------------------------

    def update_memo_status(self, memo_id: str, new_status: str) -> bool:
        """Update a memo's status and set the resolved timestamp.

        Args:
            memo_id: The memo ID.
            new_status: New status (accepted or dismissed).

        Returns:
            True if the memo was updated, False if not found.
        """
        now = datetime.now(timezone.utc).isoformat()
        cursor = self.conn.execute(
            "UPDATE feedback_memos "
            "SET status = ?, resolved_at = ? "
            "WHERE id = ?",
            (new_status, now, memo_id),
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def batch_update_memo_status(
        self,
        memo_ids: list[str],
        new_status: str,
    ) -> int:
        """Update multiple memos at once.

        Args:
            memo_ids: List of memo IDs to update.
            new_status: New status (accepted or dismissed).

        Returns:
            Number of memos updated.
        """
        if not memo_ids:
            return 0

        now = datetime.now(timezone.utc).isoformat()
        placeholders = ",".join("?" for _ in memo_ids)
        cursor = self.conn.execute(
            f"UPDATE feedback_memos "
            f"SET status = ?, resolved_at = ? "
            f"WHERE id IN ({placeholders})",
            [new_status, now, *memo_ids],
        )
        self.conn.commit()
        return cursor.rowcount

    # -----------------------------------------------------------------------
    # Row conversion helper
    # -----------------------------------------------------------------------

    def _row_to_feedback_memo(self, row: sqlite3.Row) -> FeedbackMemo:
        """Convert a database row to a FeedbackMemo dataclass."""
        items_raw = row["referenced_items"]
        try:
            referenced_items = json.loads(items_raw) if items_raw else []
        except (json.JSONDecodeError, TypeError):
            referenced_items = []

        return FeedbackMemo(
            id=row["id"],
            source_layer=row["source_layer"],
            target_layer=row["target_layer"],
            cascade_id=row["cascade_id"],
            content=row["content"],
            referenced_items=referenced_items,
            status=row["status"],
            created_at=datetime.fromisoformat(row["created_at"]),
            resolved_at=(
                datetime.fromisoformat(row["resolved_at"])
                if row["resolved_at"]
                else None
            ),
        )
