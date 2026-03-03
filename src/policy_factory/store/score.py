"""Score store mixin for 6-axis idea evaluation scores.

Stores the numeric scores produced by the idea evaluation agent
for each axis: strategic fit, feasibility, cost, risk, public
acceptance, and international impact.  An overall score (average
of all 6 axes) is computed and stored alongside.
"""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class IdeaScore:
    """The 6-axis evaluation scores for an idea."""

    id: str
    idea_id: str
    strategic_fit: float
    feasibility: float
    cost: float
    risk: float
    public_acceptance: float
    international_impact: float
    overall_score: float
    agent_run_id: str | None
    created_at: datetime


class ScoreStoreMixin:
    """Mixin providing idea score storage and retrieval.

    Requires ``self.conn`` (a ``sqlite3.Connection``) to be set by the
    base store class.
    """

    conn: sqlite3.Connection  # Provided by BaseStore

    # ------------------------------------------------------------------
    # Store
    # ------------------------------------------------------------------

    def store_scores(
        self,
        idea_id: str,
        strategic_fit: float,
        feasibility: float,
        cost: float,
        risk: float,
        public_acceptance: float,
        international_impact: float,
        agent_run_id: str | None = None,
    ) -> str:
        """Store the 6-axis scores for an idea.

        Computes and stores the overall score as the average of the
        6 axes.

        Args:
            idea_id: The idea ID.
            strategic_fit: Score 1-10.
            feasibility: Score 1-10.
            cost: Score 1-10.
            risk: Score 1-10.
            public_acceptance: Score 1-10.
            international_impact: Score 1-10.
            agent_run_id: Optional agent run ID that produced these
                scores.

        Returns:
            The generated score record ID.
        """
        score_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        overall = round(
            (
                strategic_fit
                + feasibility
                + cost
                + risk
                + public_acceptance
                + international_impact
            )
            / 6.0,
            2,
        )

        self.conn.execute(
            "INSERT INTO idea_scores "
            "(id, idea_id, strategic_fit, feasibility, cost, risk, "
            " public_acceptance, international_impact, overall_score, "
            " agent_run_id, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                score_id,
                idea_id,
                strategic_fit,
                feasibility,
                cost,
                risk,
                public_acceptance,
                international_impact,
                overall,
                agent_run_id,
                now,
            ),
        )
        self.conn.commit()
        return score_id

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_scores(self, idea_id: str) -> IdeaScore | None:
        """Return the scores for an idea, or ``None`` if not evaluated.

        Args:
            idea_id: The idea ID.

        Returns:
            An IdeaScore dataclass, or None.
        """
        row = self.conn.execute(
            "SELECT * FROM idea_scores WHERE idea_id = ? "
            "ORDER BY created_at DESC LIMIT 1",
            (idea_id,),
        ).fetchone()
        if not row:
            return None
        return self._row_to_score(row)

    def get_top_scored_ideas(self, limit: int = 10) -> list[str]:
        """Return idea IDs ordered by overall score descending.

        Args:
            limit: Maximum number of IDs to return.

        Returns:
            List of idea IDs ordered by highest overall score first.
        """
        rows = self.conn.execute(
            "SELECT idea_id FROM idea_scores "
            "ORDER BY overall_score DESC "
            "LIMIT ?",
            (limit,),
        ).fetchall()
        return [row["idea_id"] for row in rows]

    # ------------------------------------------------------------------
    # Row conversion
    # ------------------------------------------------------------------

    def _row_to_score(self, row: sqlite3.Row) -> IdeaScore:
        """Convert a database row to an IdeaScore dataclass."""
        return IdeaScore(
            id=row["id"],
            idea_id=row["idea_id"],
            strategic_fit=row["strategic_fit"],
            feasibility=row["feasibility"],
            cost=row["cost"],
            risk=row["risk"],
            public_acceptance=row["public_acceptance"],
            international_impact=row["international_impact"],
            overall_score=row["overall_score"],
            agent_run_id=row["agent_run_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
