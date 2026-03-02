"""Critic runner — launches all 6 critics in parallel against layer content.

Matches the ``CriticRunnerFn`` protocol defined in the orchestrator.
Each critic receives the same content, uses its archetype-specific prompt,
and produces an assessment. Partial failures are tolerated — the overall
run succeeds if at least one critic completes.

The critic runner is used by both the cascade orchestrator (for layer
critiques) and the idea evaluation pipeline (step 018).
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from policy_factory.events import (
    CriticCompleted,
    CriticStarted,
    EventEmitter,
)
from policy_factory.store import PolicyStore

from .content import gather_cross_layer_context, gather_layer_content
from .critics import CRITIC_ARCHETYPES, CriticArchetype

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class SingleCriticResult:
    """Result from a single critic's run."""

    archetype: str
    success: bool
    assessment_text: str = ""
    structured_assessment: dict[str, Any] | None = None
    error: str | None = None
    agent_run_id: str | None = None


@dataclass
class CriticRunnerResult:
    """Aggregated result from all 6 critics."""

    results: list[SingleCriticResult] = field(default_factory=list)
    successful_count: int = 0
    failed_count: int = 0

    @property
    def overall_success(self) -> bool:
        """True if at least one critic succeeded."""
        return self.successful_count > 0

    def get_successful_results(self) -> list[SingleCriticResult]:
        """Return only the successful critic results."""
        return [r for r in self.results if r.success]

    def get_result_by_archetype(self, archetype: str) -> SingleCriticResult | None:
        """Return the result for a specific archetype."""
        for r in self.results:
            if r.archetype == archetype:
                return r
        return None


# ---------------------------------------------------------------------------
# Assessment parsing
# ---------------------------------------------------------------------------


def parse_critic_assessment(text: str) -> dict[str, Any] | None:
    """Attempt to parse structured assessment from critic output.

    The critic prompt template instructs the AI to produce structured
    output with sections per item (agreement level, score, analysis,
    etc.). This parser extracts what it can from the text.

    Returns ``None`` if no structure can be extracted.
    The parser is lenient — missing sections are simply omitted.
    """
    if not text or not text.strip():
        return None

    structured: dict[str, Any] = {}
    items: list[dict[str, Any]] = []

    # Find assessment blocks: "## Assessment of ..."
    # Split by assessment headers
    assessment_pattern = re.compile(
        r'##\s+Assessment\s+of\s+"([^"]+)"', re.IGNORECASE
    )
    sections = assessment_pattern.split(text)

    # sections[0] is preamble, then alternating: title, content, title, content
    if len(sections) >= 3:
        for i in range(1, len(sections), 2):
            title = sections[i].strip()
            content = sections[i + 1] if i + 1 < len(sections) else ""

            item: dict[str, Any] = {"title": title}

            # Extract agreement level
            agreement_match = re.search(
                r'\*\*Agreement\s+level\*\*:\s*(.+)', content, re.IGNORECASE
            )
            if agreement_match:
                item["agreement_level"] = agreement_match.group(1).strip()

            # Extract score
            score_match = re.search(
                r'\*\*Score\*\*:\s*(\d+)/10', content, re.IGNORECASE
            )
            if score_match:
                item["score"] = int(score_match.group(1))

            # Extract analysis
            analysis_match = re.search(
                r'\*\*Analysis\*\*:\s*(.+?)(?=\*\*|$)',
                content,
                re.IGNORECASE | re.DOTALL,
            )
            if analysis_match:
                item["analysis"] = analysis_match.group(1).strip()

            # Extract alternative recommendation
            alt_match = re.search(
                r'\*\*Alternative\s+recommendation\*\*:\s*(.+?)(?=\*\*|##|$)',
                content,
                re.IGNORECASE | re.DOTALL,
            )
            if alt_match:
                item["alternative_recommendation"] = alt_match.group(1).strip()

            items.append(item)

    if items:
        structured["items"] = items

        # Calculate average score if available
        scores = [item["score"] for item in items if "score" in item]
        if scores:
            structured["average_score"] = round(sum(scores) / len(scores), 1)

    return structured if structured else None


# ---------------------------------------------------------------------------
# Single critic execution
# ---------------------------------------------------------------------------


async def _run_single_critic(
    archetype: CriticArchetype,
    layer_slug: str,
    cascade_id: str | None,
    layer_content: str,
    cross_layer_context: str,
    store: PolicyStore,
    emitter: EventEmitter,
    data_dir: Path,
    idea_id: str | None = None,
) -> SingleCriticResult:
    """Run a single critic agent and store the result.

    This function handles the full lifecycle for one critic:
    emit start event → create agent run → build prompt → run agent →
    parse output → store result → emit completion event.

    Args:
        archetype: The critic archetype definition.
        layer_slug: Layer being critiqued (may be empty for idea evals).
        cascade_id: Cascade run ID (None for idea evaluations).
        layer_content: The formatted layer content to critique.
        cross_layer_context: Context from adjacent layers.
        store: The PolicyStore for persistence.
        emitter: EventEmitter for broadcasting events.
        data_dir: Root data directory.
        idea_id: Idea ID (None for cascade critiques).

    Returns:
        A SingleCriticResult with success/failure and assessment data.
    """
    from policy_factory.agent.config import AgentConfig, resolve_model
    from policy_factory.agent.prompts import build_agent_prompt
    from policy_factory.agent.session import AgentSession
    from policy_factory.server.deps import get_anthropic_client

    # Emit start event
    await emitter.emit(
        CriticStarted(
            cascade_id=cascade_id or "",
            layer_slug=layer_slug,
            critic_archetype=archetype.slug,
        )
    )

    # Resolve model for critic role
    model = resolve_model("critic")

    # Record agent run start
    agent_run_id = store.create_agent_run(
        cascade_id=cascade_id,
        agent_type="critic",
        agent_label=archetype.agent_label,
        model=model,
        target_layer=layer_slug or None,
    )

    try:
        # Build the critic prompt
        prompt = build_agent_prompt(
            "critics",
            archetype.slug,
            layer_slug=layer_slug,
            layer_content=layer_content,
            cross_layer_context=cross_layer_context,
        )

        # Create agent config
        config = AgentConfig(
            model=model,
        )

        # Get shared Anthropic client
        client = get_anthropic_client()

        # Create and run the session
        session = AgentSession(
            config=config,
            emitter=emitter,
            context_id=cascade_id or "",
            agent_label=archetype.agent_label,
            client=client,
            data_dir=data_dir,
        )

        result = await session.run(prompt)

        # Extract assessment text (use full_output which has meditation filtered)
        assessment_text = result.full_output or result.result_text or ""

        # Attempt structured parsing
        structured = parse_critic_assessment(assessment_text)

        # Record success
        store.complete_agent_run(
            agent_run_id,
            success=not result.is_error,
            error_message=result.result_text if result.is_error else None,
            cost=result.total_cost_usd,
            output_text=result.full_output,
        )

        if result.is_error:
            # Agent reported an error result
            store.store_critic_result(
                cascade_id=cascade_id,
                layer_slug=layer_slug or None,
                idea_id=idea_id,
                archetype=archetype.slug,
                assessment_text="",
                structured_assessment=None,
                agent_run_id=agent_run_id,
            )

            await emitter.emit(
                CriticCompleted(
                    cascade_id=cascade_id or "",
                    layer_slug=layer_slug,
                    critic_archetype=archetype.slug,
                )
            )

            return SingleCriticResult(
                archetype=archetype.slug,
                success=False,
                error=result.result_text,
                agent_run_id=agent_run_id,
            )

        # Store the result
        store.store_critic_result(
            cascade_id=cascade_id,
            layer_slug=layer_slug or None,
            idea_id=idea_id,
            archetype=archetype.slug,
            assessment_text=assessment_text,
            structured_assessment=structured,
            agent_run_id=agent_run_id,
        )

        await emitter.emit(
            CriticCompleted(
                cascade_id=cascade_id or "",
                layer_slug=layer_slug,
                critic_archetype=archetype.slug,
            )
        )

        return SingleCriticResult(
            archetype=archetype.slug,
            success=True,
            assessment_text=assessment_text,
            structured_assessment=structured,
            agent_run_id=agent_run_id,
        )

    except Exception as exc:
        error_msg = str(exc)
        logger.error(
            "Critic %s failed for %s: %s",
            archetype.slug,
            layer_slug,
            error_msg,
        )

        # Record failure
        store.complete_agent_run(
            agent_run_id,
            success=False,
            error_message=error_msg,
        )

        # Store a failed result
        store.store_critic_result(
            cascade_id=cascade_id,
            layer_slug=layer_slug or None,
            idea_id=idea_id,
            archetype=archetype.slug,
            assessment_text="",
            structured_assessment=None,
            agent_run_id=agent_run_id,
        )

        await emitter.emit(
            CriticCompleted(
                cascade_id=cascade_id or "",
                layer_slug=layer_slug,
                critic_archetype=archetype.slug,
            )
        )

        return SingleCriticResult(
            archetype=archetype.slug,
            success=False,
            error=error_msg,
            agent_run_id=agent_run_id,
        )


# ---------------------------------------------------------------------------
# Public API — run all critics
# ---------------------------------------------------------------------------


async def run_critics(
    layer_slug: str,
    cascade_id: str,
    store: PolicyStore,
    emitter: EventEmitter,
    data_dir: Path,
    *,
    layer_content: str | None = None,
    idea_id: str | None = None,
) -> CriticRunnerResult:
    """Run all 6 critic agents concurrently against layer content.

    This matches the ``CriticRunnerFn`` protocol from the orchestrator.

    If ``layer_content`` is not provided, it is gathered from the data
    directory using the layer slug.

    Args:
        layer_slug: Layer being critiqued.
        cascade_id: Cascade run ID (may be empty for idea evaluations).
        store: The PolicyStore for persistence.
        emitter: EventEmitter for broadcasting events.
        data_dir: Root data directory.
        layer_content: Pre-gathered layer content. If None, gathered
            automatically from the data directory.
        idea_id: Idea ID (None for cascade critiques).

    Returns:
        A CriticRunnerResult with all 6 individual results and counts.
    """
    # Gather content if not provided
    if layer_content is None:
        layer_content = gather_layer_content(data_dir, layer_slug)

    cross_layer_context = gather_cross_layer_context(data_dir, layer_slug)

    # Prepare coroutines for all 6 critics
    tasks = [
        _run_single_critic(
            archetype=archetype,
            layer_slug=layer_slug,
            cascade_id=cascade_id or None,
            layer_content=layer_content,
            cross_layer_context=cross_layer_context,
            store=store,
            emitter=emitter,
            data_dir=data_dir,
            idea_id=idea_id,
        )
        for archetype in CRITIC_ARCHETYPES
    ]

    # Launch all 6 concurrently with return_exceptions=True
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results
    critic_results: list[SingleCriticResult] = []
    successful = 0
    failed = 0

    for i, raw in enumerate(raw_results):
        archetype = CRITIC_ARCHETYPES[i]

        if isinstance(raw, Exception):
            # Unexpected exception from gather (shouldn't happen since
            # _run_single_critic catches internally, but be defensive)
            logger.error(
                "Unexpected exception from critic %s: %s",
                archetype.slug,
                raw,
            )
            critic_results.append(
                SingleCriticResult(
                    archetype=archetype.slug,
                    success=False,
                    error=str(raw),
                )
            )
            failed += 1
        elif isinstance(raw, SingleCriticResult):
            critic_results.append(raw)
            if raw.success:
                successful += 1
            else:
                failed += 1
        else:
            # Shouldn't happen
            logger.error("Unexpected result type from critic %s: %s", archetype.slug, type(raw))
            critic_results.append(
                SingleCriticResult(
                    archetype=archetype.slug,
                    success=False,
                    error=f"Unexpected result type: {type(raw)}",
                )
            )
            failed += 1

    result = CriticRunnerResult(
        results=critic_results,
        successful_count=successful,
        failed_count=failed,
    )

    if not result.overall_success:
        logger.error(
            "All 6 critics failed for %s (cascade %s)",
            layer_slug,
            cascade_id,
        )

    return result
