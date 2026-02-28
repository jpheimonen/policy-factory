"""Heartbeat run store mixin for tracking heartbeat executions.

Records each heartbeat run with its structured log of tier outcomes,
highest tier reached, trigger type, and timing. Each tier entry
in the structured log captures: tier number, escalated boolean,
outcome description, agent run ID, and start/end timestamps.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class TierEntry:
    """A single tier's result within a heartbeat run."""

    tier: int
    escalated: bool
    outcome: str
    agent_run_id: str | None = None
    started_at: str | None = None
    ended_at: str | None = None


@dataclass
class HeartbeatRun:
    """A heartbeat run record from the database."""

    id: str
    trigger: str  # "scheduled" or "manual"
    started_at: datetime
    completed_at: datetime | None
    highest_tier: int
    structured_log: list[TierEntry] = field(default_factory=list)


class HeartbeatMixin:
    """Mixin providing heartbeat run tracking and retrieval.

    Requires ``self.conn`` (a ``sqlite3.Connection``) to be set by the
    base store class.
    """

    conn: sqlite3.Connection  # Provided by BaseStore

    # -------------------------------------------------------------------
    # Create
    # -------------------------------------------------------------------

    def create_heartbeat_run(self, trigger: str) -> str:
        """Create a heartbeat run record with the started timestamp.

        Args:
            trigger: How the heartbeat was initiated ("scheduled" or "manual").

        Returns:
            The generated heartbeat run ID.
        """
        run_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "INSERT INTO heartbeat_runs "
            "(id, trigger, started_at, completed_at, highest_tier, structured_log) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (run_id, trigger, now, None, 0, "[]"),
        )
        self.conn.commit()
        return run_id

    # -------------------------------------------------------------------
    # Update
    # -------------------------------------------------------------------

    def update_heartbeat_tier(
        self,
        run_id: str,
        tier: int,
        escalated: bool,
        outcome: str,
        agent_run_id: str | None = None,
    ) -> None:
        """Append a tier entry to the structured log and update highest tier.

        Called after each tier completes.

        Args:
            run_id: The heartbeat run ID.
            tier: Tier number (1–4).
            escalated: Whether this tier escalated to the next.
            outcome: Brief description of the tier result.
            agent_run_id: Optional link to the agent run record.
        """
        now = datetime.now(timezone.utc).isoformat()

        # Fetch current structured log
        row = self.conn.execute(
            "SELECT structured_log FROM heartbeat_runs WHERE id = ?",
            (run_id,),
        ).fetchone()
        if row is None:
            return

        try:
            current_log = json.loads(row["structured_log"] or "[]")
        except (json.JSONDecodeError, TypeError):
            current_log = []

        # Append new tier entry
        tier_entry = {
            "tier": tier,
            "escalated": escalated,
            "outcome": outcome,
            "agent_run_id": agent_run_id,
            "started_at": now,
            "ended_at": now,
        }
        current_log.append(tier_entry)

        self.conn.execute(
            "UPDATE heartbeat_runs "
            "SET highest_tier = ?, structured_log = ? "
            "WHERE id = ?",
            (tier, json.dumps(current_log), run_id),
        )
        self.conn.commit()

    def complete_heartbeat_run(self, run_id: str) -> None:
        """Set the completed timestamp on a heartbeat run.

        Called when the heartbeat finishes (tier didn't escalate or Tier 4 done).

        Args:
            run_id: The heartbeat run ID.
        """
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "UPDATE heartbeat_runs SET completed_at = ? WHERE id = ?",
            (now, run_id),
        )
        self.conn.commit()

    # -------------------------------------------------------------------
    # Read
    # -------------------------------------------------------------------

    def get_heartbeat_run(self, run_id: str) -> HeartbeatRun | None:
        """Return the full heartbeat run record by ID.

        Args:
            run_id: The heartbeat run ID.

        Returns:
            A HeartbeatRun dataclass, or None if not found.
        """
        row = self.conn.execute(
            "SELECT * FROM heartbeat_runs WHERE id = ?",
            (run_id,),
        ).fetchone()
        if not row:
            return None
        return self._row_to_heartbeat_run(row)

    def list_heartbeat_runs(
        self,
        limit: int = 20,
        offset: int = 0,
    ) -> list[HeartbeatRun]:
        """Return recent heartbeat runs in reverse chronological order.

        Args:
            limit: Maximum number of results (default 20).
            offset: Number of results to skip.

        Returns:
            List of HeartbeatRun records.
        """
        rows = self.conn.execute(
            "SELECT * FROM heartbeat_runs "
            "ORDER BY started_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [self._row_to_heartbeat_run(r) for r in rows]

    def get_latest_heartbeat_run(self) -> HeartbeatRun | None:
        """Return the most recent heartbeat run record.

        Returns:
            The latest HeartbeatRun, or None if no heartbeat has ever run.
        """
        row = self.conn.execute(
            "SELECT * FROM heartbeat_runs ORDER BY started_at DESC LIMIT 1",
        ).fetchone()
        if not row:
            return None
        return self._row_to_heartbeat_run(row)

    def has_running_heartbeat(self) -> bool:
        """Check whether a heartbeat is currently running (not completed).

        Returns:
            True if a heartbeat run exists without a completed_at timestamp.
        """
        row = self.conn.execute(
            "SELECT COUNT(*) as count FROM heartbeat_runs "
            "WHERE completed_at IS NULL",
        ).fetchone()
        return row["count"] > 0

    # -------------------------------------------------------------------
    # Row conversion helper
    # -------------------------------------------------------------------

    def _row_to_heartbeat_run(self, row: sqlite3.Row) -> HeartbeatRun:
        """Convert a database row to a HeartbeatRun dataclass."""
        raw_log = row["structured_log"]
        try:
            log_data = json.loads(raw_log) if raw_log else []
        except (json.JSONDecodeError, TypeError):
            log_data = []

        tier_entries = [
            TierEntry(
                tier=entry.get("tier", 0),
                escalated=entry.get("escalated", False),
                outcome=entry.get("outcome", ""),
                agent_run_id=entry.get("agent_run_id"),
                started_at=entry.get("started_at"),
                ended_at=entry.get("ended_at"),
            )
            for entry in log_data
            if isinstance(entry, dict)
        ]

        return HeartbeatRun(
            id=row["id"],
            trigger=row["trigger"],
            started_at=datetime.fromisoformat(row["started_at"]),
            completed_at=(
                datetime.fromisoformat(row["completed_at"])
                if row["completed_at"]
                else None
            ),
            highest_tier=row["highest_tier"],
            structured_log=tier_entries,
        )
