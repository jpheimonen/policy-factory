"""Idea evaluation orchestrator.

Drives the full evaluation pipeline for a single idea:
1. Update status to "evaluating", emit start event.
2. Gather the full policy stack summary as context.
3. Run the evaluation agent to produce 6-axis scores.
4. Parse and store scores.
5. Run all 6 critics against the idea (via the critic runner).
6. Run the synthesis agent.
7. Update status to "evaluated", emit completion event.

Evaluations are read-only against layer data — they don't modify
any files and don't need the cascade lock.  Multiple evaluations
can run concurrently.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from policy_factory.events import (
    EventEmitter,
    IdeaEvaluationCompleted,
    IdeaEvaluationStarted,
)
from policy_factory.store import PolicyStore

from .helpers import (
    gather_stack_summary,
    gather_stack_summary_text,
    get_default_scores,
    parse_evaluation_scores,
)

logger = logging.getLogger(__name__)


@dataclass
class EvaluationResult:
    """Result of an idea evaluation."""

    idea_id: str
    success: bool
    scores: dict[str, float] | None = None
    critic_count: int = 0
    synthesis_text: str = ""
    error: str | None = None


async def evaluate_idea(
    idea_id: str,
    store: PolicyStore,
    emitter: EventEmitter,
    data_dir: Path,
) -> EvaluationResult:
    """Run the full evaluation pipeline for a single idea.

    Args:
        idea_id: The idea to evaluate.
        store: PolicyStore for persistence.
        emitter: EventEmitter for broadcasting events.
        data_dir: Root data directory.

    Returns:
        An EvaluationResult with scores and metadata.
    """
    # Verify the idea exists
    idea = store.get_idea(idea_id)
    if idea is None:
        return EvaluationResult(
            idea_id=idea_id,
            success=False,
            error=f"Idea not found: {idea_id}",
        )

    try:
        # Step 1: Update status to "evaluating"
        store.update_idea_status(idea_id, "evaluating")

        # Step 2: Emit start event
        await emitter.emit(IdeaEvaluationStarted(idea_id=idea_id))

        # Step 3: Gather context
        stack_summaries = gather_stack_summary(data_dir)
        stack_text = gather_stack_summary_text(data_dir)

        # Step 4: Scoring
        scores = await _run_scoring(
            idea=idea,
            stack_summaries=stack_summaries,
            store=store,
            emitter=emitter,
            data_dir=data_dir,
        )

        if scores is None:
            # Scoring failed completely — reset to pending
            store.update_idea_status(idea_id, "pending")
            return EvaluationResult(
                idea_id=idea_id,
                success=False,
                error="Scoring step failed",
            )

        # Step 5: Critics
        critic_count = 0
        try:
            critic_count = await _run_critics(
                idea=idea,
                stack_text=stack_text,
                scores=scores,
                store=store,
                emitter=emitter,
                data_dir=data_dir,
            )
        except Exception as exc:
            logger.error("Critic step failed for idea %s: %s", idea_id, exc)
            # Continue — partial results are still useful

        # Step 6: Synthesis
        synthesis_text = ""
        try:
            synthesis_text = await _run_synthesis(
                idea=idea,
                store=store,
                emitter=emitter,
                data_dir=data_dir,
            )
        except Exception as exc:
            logger.error("Synthesis step failed for idea %s: %s", idea_id, exc)
            # Continue — partial results are still useful

        # Step 7: Mark as evaluated
        store.update_idea_status(idea_id, "evaluated")

        # Step 8: Emit completion event
        await emitter.emit(IdeaEvaluationCompleted(idea_id=idea_id))

        return EvaluationResult(
            idea_id=idea_id,
            success=True,
            scores=scores,
            critic_count=critic_count,
            synthesis_text=synthesis_text,
        )

    except Exception as exc:
        logger.error("Evaluation failed for idea %s: %s", idea_id, exc)

        # Reset to pending so it can be re-evaluated later
        try:
            store.update_idea_status(idea_id, "pending")
        except Exception:
            logger.error("Failed to reset idea %s status", idea_id)

        return EvaluationResult(
            idea_id=idea_id,
            success=False,
            error=str(exc),
        )


# ---------------------------------------------------------------------------
# Internal steps
# ---------------------------------------------------------------------------


async def _run_scoring(
    idea: Any,
    stack_summaries: dict[str, str],
    store: PolicyStore,
    emitter: EventEmitter,
    data_dir: Path,
) -> dict[str, float] | None:
    """Run the evaluation agent to produce 6-axis scores.

    Returns the parsed scores dict, or None on failure.
    """
    from policy_factory.agent.config import AgentConfig, resolve_model
    from policy_factory.agent.prompts import build_agent_prompt
    from policy_factory.agent.session import AgentSession

    model = resolve_model("idea-evaluator")

    # Record agent run start
    agent_run_id = store.create_agent_run(
        cascade_id=None,
        agent_type="idea-evaluator",
        agent_label="Idea evaluator",
        model=model,
    )

    try:
        # Build the evaluation prompt
        prompt = build_agent_prompt(
            "ideas",
            "evaluate",
            idea_text=idea.text,
            **stack_summaries,
        )

        config = AgentConfig(
            model=model,
            role="idea-evaluator",
        )

        session = AgentSession(
            config=config,
            emitter=emitter,
            context_id=idea.id,
            agent_label="Idea evaluator",
            data_dir=data_dir,
        )

        result = await session.run(prompt)

        # Extract output text
        output_text = result.full_output or result.result_text or ""

        # Record completion
        store.complete_agent_run(
            agent_run_id,
            success=not result.is_error,
            error_message=result.result_text if result.is_error else None,
            cost=result.total_cost_usd,
            output_text=result.full_output,
        )

        if result.is_error:
            logger.error("Evaluation agent error for idea %s: %s", idea.id, result.result_text)
            # Store default scores with a note that parsing failed
            default_scores = get_default_scores()
            store.store_scores(
                idea_id=idea.id,
                agent_run_id=agent_run_id,
                **default_scores,
            )
            return default_scores

        # Parse scores from output
        parsed = parse_evaluation_scores(output_text)
        if parsed is None:
            logger.warning(
                "Failed to parse scores from evaluation output for idea %s, "
                "using defaults",
                idea.id,
            )
            parsed = get_default_scores()

        # Store the scores
        store.store_scores(
            idea_id=idea.id,
            agent_run_id=agent_run_id,
            **parsed,
        )

        return parsed

    except Exception as exc:
        logger.error("Scoring failed for idea %s: %s", idea.id, exc)

        store.complete_agent_run(
            agent_run_id,
            success=False,
            error_message=str(exc),
        )

        return None


async def _run_critics(
    idea: Any,
    stack_text: str,
    scores: dict[str, float],
    store: PolicyStore,
    emitter: EventEmitter,
    data_dir: Path,
) -> int:
    """Run all 6 critics against the idea.

    Returns the number of successful critics.
    """
    from policy_factory.cascade.critic_runner import run_critics

    # Prepare content for critics: idea text + context
    scores_text = "\n".join(f"- {k}: {v}/10" for k, v in scores.items())
    content = (
        f"## Idea Under Evaluation\n\n{idea.text}\n\n"
        f"## Evaluation Scores\n\n{scores_text}\n\n"
        f"## Policy Stack Context\n\n{stack_text}"
    )

    # Run critics via the shared critic runner
    result = await run_critics(
        layer_slug="",  # Not a specific layer
        cascade_id="",  # Not part of a cascade
        store=store,
        emitter=emitter,
        data_dir=data_dir,
        layer_content=content,
        idea_id=idea.id,
    )

    return result.successful_count


async def _run_synthesis(
    idea: Any,
    store: PolicyStore,
    emitter: EventEmitter,
    data_dir: Path,
) -> str:
    """Run the synthesis agent on the idea's critic results.

    Returns the synthesis text.
    """
    from policy_factory.cascade.synthesis_runner import run_synthesis

    # Get critic results from the database to build CriticRunnerResult
    stored_critics = store.get_critic_results_for_idea(idea.id)
    if not stored_critics:
        return ""

    from policy_factory.cascade.critic_runner import (
        CriticRunnerResult,
        SingleCriticResult,
    )

    results_list = [
        SingleCriticResult(
            archetype=cr.archetype,
            success=cr.is_success,
            assessment_text=cr.assessment_text,
            structured_assessment=cr.structured_assessment,
            agent_run_id=cr.agent_run_id,
        )
        for cr in stored_critics
    ]

    critic_results = CriticRunnerResult(
        results=results_list,
        successful_count=sum(1 for r in results_list if r.success),
        failed_count=sum(1 for r in results_list if not r.success),
    )

    # Prepare idea content for the synthesis prompt
    content = f"## Idea Under Evaluation\n\n{idea.text}"

    result = await run_synthesis(
        layer_slug="",
        critic_results=critic_results,
        cascade_id="",
        store=store,
        emitter=emitter,
        data_dir=data_dir,
        layer_content=content,
        idea_id=idea.id,
    )

    return result.synthesis_text if result.success else ""
