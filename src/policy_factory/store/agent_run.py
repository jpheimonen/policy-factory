"""Agent run store mixin for tracking agent invocations.

Records each agent invocation: who ran, when, how long, success/failure,
model used, cost. Every agent session run is logged here for the activity
feed and diagnostics.
"""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

# Valid agent types
AgentType = Literal[
    "generator",
    "critic",
    "synthesis",
    "heartbeat-skim",
    "heartbeat-triage",
    "heartbeat-sa-update",
    "classifier",
    "idea-evaluator",
    "idea-generator",
    "seed",
]


@dataclass
class AgentRun:
    """An agent run record from the database."""

    id: str
    cascade_id: str | None
    agent_type: str
    agent_label: str
    model: str
    target_layer: str | None
    started_at: datetime
    completed_at: datetime | None
    success: bool | None
    error_message: str | None
    cost_usd: float | None
    output_text: str | None


class AgentRunStoreMixin:
    """Mixin providing agent run tracking and retrieval.

    Requires ``self.conn`` (a ``sqlite3.Connection``) to be set by the
    base store class.
    """

    conn: sqlite3.Connection  # Provided by BaseStore

    def create_agent_run(
        self,
        cascade_id: str | None,
        agent_type: str,
        agent_label: str,
        model: str,
        target_layer: str | None = None,
    ) -> str:
        """Create an agent run record with the started timestamp.

        Args:
            cascade_id: Optional cascade ID (None for runs outside cascades).
            agent_type: The agent type string (e.g. "generator", "critic").
            agent_label: Human-readable label (e.g. "Values layer generator").
            model: The model name used for this run.
            target_layer: Optional target layer slug.

        Returns:
            The generated agent run ID.
        """
        run_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "INSERT INTO agent_runs "
            "(id, cascade_id, agent_type, agent_label, model, target_layer, "
            " started_at, completed_at, success, error_message, cost_usd, output_text) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                cascade_id,
                agent_type,
                agent_label,
                model,
                target_layer,
                now,
                None,
                None,
                None,
                None,
                None,
            ),
        )
        self.conn.commit()
        return run_id

    def complete_agent_run(
        self,
        agent_run_id: str,
        success: bool,
        error_message: str | None = None,
        cost: float | None = None,
        output_text: str | None = None,
    ) -> None:
        """Update the agent run record with completion data.

        Args:
            agent_run_id: The agent run ID.
            success: Whether the agent completed successfully.
            error_message: Optional error message on failure.
            cost: Optional cost in USD.
            output_text: The full unfiltered output text (for auditability).
        """
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "UPDATE agent_runs "
            "SET completed_at = ?, success = ?, error_message = ?, "
            "    cost_usd = ?, output_text = ? "
            "WHERE id = ?",
            (now, success, error_message, cost, output_text, agent_run_id),
        )
        self.conn.commit()

    def get_agent_run(self, agent_run_id: str) -> AgentRun | None:
        """Return the full agent run record by ID.

        Args:
            agent_run_id: The agent run ID.

        Returns:
            An AgentRun dataclass, or None if not found.
        """
        row = self.conn.execute(
            "SELECT * FROM agent_runs WHERE id = ?",
            (agent_run_id,),
        ).fetchone()
        if not row:
            return None
        return self._row_to_agent_run(row)

    def list_agent_runs(
        self,
        cascade_id: str | None = None,
        agent_type: str | None = None,
        target_layer: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AgentRun]:
        """Return agent runs with optional filtering.

        Args:
            cascade_id: Filter by cascade ID.
            agent_type: Filter by agent type.
            target_layer: Filter by target layer slug.
            limit: Maximum number of results.
            offset: Number of results to skip.

        Returns:
            List of AgentRun records in reverse chronological order.
        """
        conditions: list[str] = []
        params: list[object] = []

        if cascade_id is not None:
            conditions.append("cascade_id = ?")
            params.append(cascade_id)
        if agent_type is not None:
            conditions.append("agent_type = ?")
            params.append(agent_type)
        if target_layer is not None:
            conditions.append("target_layer = ?")
            params.append(target_layer)

        where = ""
        if conditions:
            where = "WHERE " + " AND ".join(conditions)

        query = (
            f"SELECT * FROM agent_runs {where} "
            "ORDER BY started_at DESC LIMIT ? OFFSET ?"
        )
        params.extend([limit, offset])

        rows = self.conn.execute(query, params).fetchall()
        return [self._row_to_agent_run(r) for r in rows]

    def _row_to_agent_run(self, row: sqlite3.Row) -> AgentRun:
        """Convert a database row to an AgentRun dataclass."""
        return AgentRun(
            id=row["id"],
            cascade_id=row["cascade_id"],
            agent_type=row["agent_type"],
            agent_label=row["agent_label"],
            model=row["model"],
            target_layer=row["target_layer"],
            started_at=datetime.fromisoformat(row["started_at"]),
            completed_at=(
                datetime.fromisoformat(row["completed_at"])
                if row["completed_at"]
                else None
            ),
            success=bool(row["success"]) if row["success"] is not None else None,
            error_message=row["error_message"],
            cost_usd=row["cost_usd"],
            output_text=row["output_text"],
        )
