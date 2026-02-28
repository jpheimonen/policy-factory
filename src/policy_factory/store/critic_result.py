"""Critic and synthesis result store mixin.

Provides storage and retrieval for:
- Individual critic assessments (one per archetype per layer/cascade or idea).
- Synthesis results integrating all critic outputs.

Both are linked to either a cascade run + layer (for cascade critiques)
or an idea ID (for idea evaluations). The nullable foreign keys allow
the same tables to serve both use cases.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass
class CriticResult:
    """A single critic's assessment stored in the database."""

    id: str
    cascade_id: str | None
    layer_slug: str | None
    idea_id: str | None
    archetype: str
    assessment_text: str
    structured_assessment: dict[str, Any] | None
    agent_run_id: str | None
    created_at: datetime

    @property
    def is_success(self) -> bool:
        """Whether this critic produced a non-empty assessment."""
        return bool(self.assessment_text)


@dataclass
class SynthesisResult:
    """A synthesis result stored in the database."""

    id: str
    cascade_id: str | None
    layer_slug: str | None
    idea_id: str | None
    synthesis_text: str
    structured_synthesis: dict[str, Any] | None
    agent_run_id: str | None
    created_at: datetime


class CriticResultMixin:
    """Mixin providing critic and synthesis result storage.

    Requires ``self.conn`` (a ``sqlite3.Connection``) to be set by the
    base store class.
    """

    conn: sqlite3.Connection  # Provided by BaseStore

    # ------------------------------------------------------------------
    # Critic result CRUD
    # ------------------------------------------------------------------

    def store_critic_result(
        self,
        cascade_id: str | None,
        layer_slug: str | None,
        idea_id: str | None,
        archetype: str,
        assessment_text: str,
        structured_assessment: dict[str, Any] | None,
        agent_run_id: str | None,
    ) -> str:
        """Store a single critic assessment.

        Args:
            cascade_id: Cascade run ID (None for idea evaluations).
            layer_slug: Layer slug (None for idea evaluations).
            idea_id: Idea ID (None for cascade critiques).
            archetype: Critic archetype slug (e.g. ``"realist"``).
            assessment_text: Full raw assessment text from the critic.
            structured_assessment: Optional parsed structured assessment.
            agent_run_id: The agent run ID for this critic invocation.

        Returns:
            The generated critic result ID.
        """
        result_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        structured_json = (
            json.dumps(structured_assessment)
            if structured_assessment is not None
            else None
        )
        self.conn.execute(
            "INSERT INTO critic_results "
            "(id, cascade_id, layer_slug, idea_id, archetype, "
            " assessment_text, structured_assessment, agent_run_id, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                result_id,
                cascade_id,
                layer_slug,
                idea_id,
                archetype,
                assessment_text,
                structured_json,
                agent_run_id,
                now,
            ),
        )
        self.conn.commit()
        return result_id

    def get_critic_results(
        self,
        cascade_id: str,
        layer_slug: str,
    ) -> list[CriticResult]:
        """Return all critic results for a cascade run and layer.

        Args:
            cascade_id: The cascade run ID.
            layer_slug: The layer slug.

        Returns:
            List of CriticResult records for all archetypes that ran.
        """
        rows = self.conn.execute(
            "SELECT * FROM critic_results "
            "WHERE cascade_id = ? AND layer_slug = ? "
            "ORDER BY created_at",
            (cascade_id, layer_slug),
        ).fetchall()
        return [self._row_to_critic_result(r) for r in rows]

    def get_critic_results_for_idea(
        self,
        idea_id: str,
    ) -> list[CriticResult]:
        """Return all critic results for an idea evaluation.

        Args:
            idea_id: The idea ID.

        Returns:
            List of CriticResult records.
        """
        rows = self.conn.execute(
            "SELECT * FROM critic_results "
            "WHERE idea_id = ? "
            "ORDER BY created_at",
            (idea_id,),
        ).fetchall()
        return [self._row_to_critic_result(r) for r in rows]

    def get_critic_result_by_archetype(
        self,
        cascade_id: str,
        layer_slug: str,
        archetype: str,
    ) -> CriticResult | None:
        """Return a single critic result by archetype for a cascade/layer.

        Args:
            cascade_id: The cascade run ID.
            layer_slug: The layer slug.
            archetype: Critic archetype slug.

        Returns:
            The CriticResult, or None if not found.
        """
        row = self.conn.execute(
            "SELECT * FROM critic_results "
            "WHERE cascade_id = ? AND layer_slug = ? AND archetype = ?",
            (cascade_id, layer_slug, archetype),
        ).fetchone()
        if not row:
            return None
        return self._row_to_critic_result(row)

    def get_latest_critic_results(
        self,
        layer_slug: str,
    ) -> list[CriticResult]:
        """Return the most recent critic results for a layer.

        Finds the latest cascade that has critic results for the given
        layer and returns all of that cascade's critic results for the
        layer.

        Args:
            layer_slug: The layer slug.

        Returns:
            List of CriticResult records from the most recent cascade,
            or an empty list if no results exist.
        """
        # Find the latest cascade_id that has results for this layer
        row = self.conn.execute(
            "SELECT cascade_id FROM critic_results "
            "WHERE layer_slug = ? AND cascade_id IS NOT NULL "
            "ORDER BY created_at DESC LIMIT 1",
            (layer_slug,),
        ).fetchone()
        if not row:
            return []
        return self.get_critic_results(row["cascade_id"], layer_slug)

    # ------------------------------------------------------------------
    # Synthesis result CRUD
    # ------------------------------------------------------------------

    def store_synthesis_result(
        self,
        cascade_id: str | None,
        layer_slug: str | None,
        idea_id: str | None,
        synthesis_text: str,
        structured_synthesis: dict[str, Any] | None,
        agent_run_id: str | None,
    ) -> str:
        """Store a synthesis result.

        Args:
            cascade_id: Cascade run ID (None for idea evaluations).
            layer_slug: Layer slug (None for idea evaluations).
            idea_id: Idea ID (None for cascade critiques).
            synthesis_text: Full raw synthesis text.
            structured_synthesis: Optional parsed structured synthesis.
            agent_run_id: The agent run ID for this synthesis invocation.

        Returns:
            The generated synthesis result ID.
        """
        result_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        structured_json = (
            json.dumps(structured_synthesis)
            if structured_synthesis is not None
            else None
        )
        self.conn.execute(
            "INSERT INTO synthesis_results "
            "(id, cascade_id, layer_slug, idea_id, "
            " synthesis_text, structured_synthesis, agent_run_id, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                result_id,
                cascade_id,
                layer_slug,
                idea_id,
                synthesis_text,
                structured_json,
                agent_run_id,
                now,
            ),
        )
        self.conn.commit()
        return result_id

    def get_synthesis_result(
        self,
        cascade_id: str,
        layer_slug: str,
    ) -> SynthesisResult | None:
        """Return the synthesis result for a cascade run and layer.

        Args:
            cascade_id: The cascade run ID.
            layer_slug: The layer slug.

        Returns:
            The SynthesisResult, or None if not found.
        """
        row = self.conn.execute(
            "SELECT * FROM synthesis_results "
            "WHERE cascade_id = ? AND layer_slug = ?",
            (cascade_id, layer_slug),
        ).fetchone()
        if not row:
            return None
        return self._row_to_synthesis_result(row)

    def get_synthesis_result_for_idea(
        self,
        idea_id: str,
    ) -> SynthesisResult | None:
        """Return the synthesis result for an idea evaluation.

        Args:
            idea_id: The idea ID.

        Returns:
            The SynthesisResult, or None if not found.
        """
        row = self.conn.execute(
            "SELECT * FROM synthesis_results "
            "WHERE idea_id = ?",
            (idea_id,),
        ).fetchone()
        if not row:
            return None
        return self._row_to_synthesis_result(row)

    def get_latest_synthesis_result(
        self,
        layer_slug: str,
    ) -> SynthesisResult | None:
        """Return the most recent synthesis result for a layer.

        Args:
            layer_slug: The layer slug.

        Returns:
            The SynthesisResult from the most recent cascade, or None.
        """
        row = self.conn.execute(
            "SELECT * FROM synthesis_results "
            "WHERE layer_slug = ? AND cascade_id IS NOT NULL "
            "ORDER BY created_at DESC LIMIT 1",
            (layer_slug,),
        ).fetchone()
        if not row:
            return None
        return self._row_to_synthesis_result(row)

    # ------------------------------------------------------------------
    # Row conversion helpers
    # ------------------------------------------------------------------

    def _row_to_critic_result(self, row: sqlite3.Row) -> CriticResult:
        """Convert a database row to a CriticResult."""
        structured = None
        if row["structured_assessment"]:
            try:
                structured = json.loads(row["structured_assessment"])
            except (json.JSONDecodeError, TypeError):
                pass

        return CriticResult(
            id=row["id"],
            cascade_id=row["cascade_id"],
            layer_slug=row["layer_slug"],
            idea_id=row["idea_id"],
            archetype=row["archetype"],
            assessment_text=row["assessment_text"],
            structured_assessment=structured,
            agent_run_id=row["agent_run_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def _row_to_synthesis_result(self, row: sqlite3.Row) -> SynthesisResult:
        """Convert a database row to a SynthesisResult."""
        structured = None
        if row["structured_synthesis"]:
            try:
                structured = json.loads(row["structured_synthesis"])
            except (json.JSONDecodeError, TypeError):
                pass

        return SynthesisResult(
            id=row["id"],
            cascade_id=row["cascade_id"],
            layer_slug=row["layer_slug"],
            idea_id=row["idea_id"],
            synthesis_text=row["synthesis_text"],
            structured_synthesis=structured,
            agent_run_id=row["agent_run_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
