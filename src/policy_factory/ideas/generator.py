"""AI idea generation agent.

Generates new policy ideas based on the current policy stack.
When scoped, focuses on a specific strategic or tactical objective.
Each generated idea is stored as a separate idea record with source "AI".
Generated ideas are optionally auto-evaluated.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from policy_factory.events import (
    EventEmitter,
    IdeaGenerationCompleted,
    IdeaGenerationStarted,
    IdeaSubmitted,
)
from policy_factory.store import PolicyStore

from .helpers import gather_stack_summary, parse_generated_ideas

logger = logging.getLogger(__name__)


async def generate_ideas(
    store: PolicyStore,
    emitter: EventEmitter,
    data_dir: Path,
    *,
    target_objective: str | None = None,
    auto_evaluate: bool = True,
) -> list[str]:
    """Generate new policy ideas via AI.

    Args:
        store: PolicyStore for persistence.
        emitter: EventEmitter for broadcasting events.
        data_dir: Root data directory.
        target_objective: Optional scoping (``"layer-slug/filename.md"``).
            When provided, the generation prompt focuses on that objective.
        auto_evaluate: Whether to auto-launch evaluation for each
            generated idea. Defaults to True.

    Returns:
        List of generated idea IDs.
    """
    from policy_factory.agent.config import AgentConfig, resolve_model
    from policy_factory.agent.prompts import build_agent_prompt
    from policy_factory.agent.session import AgentSession

    # Step 1: Emit start event
    await emitter.emit(IdeaGenerationStarted())

    # Step 2: Gather stack summary
    stack_summaries = gather_stack_summary(data_dir)

    # Step 3: Build scoping context
    scoping_context = _build_scoping_context(data_dir, target_objective)

    # Step 4: Resolve model
    model = resolve_model("idea-generator")

    # Step 5: Record agent run
    agent_run_id = store.create_agent_run(
        cascade_id=None,
        agent_type="idea-generator",
        agent_label="Idea generator",
        model=model,
    )

    try:
        # Step 6: Build and run the generation prompt
        prompt = build_agent_prompt(
            "ideas",
            "generate",
            scoping_context=scoping_context,
            **stack_summaries,
        )

        config = AgentConfig(
            cwd=data_dir,
            model=model,
        )

        session = AgentSession(
            config=config,
            emitter=emitter,
            context_id="idea-generation",
            agent_label="Idea generator",
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
            logger.error("Idea generation agent error: %s", result.result_text)
            await emitter.emit(IdeaGenerationCompleted(count=0))
            return []

        # Step 7: Parse output into individual ideas
        parsed_ideas = parse_generated_ideas(output_text)
        if not parsed_ideas:
            logger.warning("No ideas could be parsed from generation output")
            await emitter.emit(IdeaGenerationCompleted(count=0))
            return []

        # Step 8: Create idea records
        idea_ids: list[str] = []
        for idea_data in parsed_ideas:
            idea_id = store.create_idea(
                text=idea_data["text"],
                source="AI",
                target_objective=target_objective,
                submitted_by="system",
            )
            idea_ids.append(idea_id)

            # Emit submission event for each idea
            await emitter.emit(
                IdeaSubmitted(idea_id=idea_id, source="AI")
            )

        # Step 9: Emit completion event
        await emitter.emit(IdeaGenerationCompleted(count=len(idea_ids)))

        # Step 10: Auto-evaluate if requested
        if auto_evaluate and idea_ids:
            _launch_auto_evaluations(idea_ids, store, emitter, data_dir)

        return idea_ids

    except Exception as exc:
        logger.error("Idea generation failed: %s", exc)

        store.complete_agent_run(
            agent_run_id,
            success=False,
            error_message=str(exc),
        )

        await emitter.emit(IdeaGenerationCompleted(count=0))
        return []


def _build_scoping_context(
    data_dir: Path,
    target_objective: str | None,
) -> str:
    """Build the scoping context text for the generation prompt.

    Args:
        data_dir: Root data directory.
        target_objective: Optional ``"layer-slug/filename.md"`` reference.

    Returns:
        Text describing the scoping context, or a note that generation
        is unscoped.
    """
    if not target_objective:
        return (
            "No specific scoping — generate ideas across the entire "
            "policy framework. Consider all layers and look for gaps, "
            "opportunities, and novel approaches."
        )

    # Try to read the target objective's content
    parts = target_objective.split("/", 1)
    if len(parts) != 2:
        return f"Scoped to: {target_objective} (unable to read content)"

    layer_slug, filename = parts

    try:
        from policy_factory.data.layers import read_item

        fm, body = read_item(data_dir, layer_slug, filename)
        title = fm.get("title", filename)
        return (
            f"**Scoped to objective:** {title}\n\n"
            f"**Layer:** {layer_slug}\n\n"
            f"**Content:**\n{body}\n\n"
            f"Focus your ideas on this specific objective. Generate "
            f"ideas that directly support, extend, or implement this "
            f"objective. You may also suggest adjacent opportunities "
            f"discovered while analysing this objective."
        )
    except Exception:
        return f"Scoped to: {target_objective} (content could not be read)"


def _launch_auto_evaluations(
    idea_ids: list[str],
    store: PolicyStore,
    emitter: EventEmitter,
    data_dir: Path,
) -> None:
    """Launch evaluation as background tasks for generated ideas.

    Each evaluation runs as a separate background asyncio task.

    Args:
        idea_ids: List of idea IDs to evaluate.
        store: PolicyStore instance.
        emitter: EventEmitter instance.
        data_dir: Root data directory.
    """
    from .evaluator import evaluate_idea

    for idea_id in idea_ids:

        async def _eval(iid: str = idea_id) -> None:
            try:
                await evaluate_idea(iid, store, emitter, data_dir)
            except Exception:
                logger.exception(
                    "Auto-evaluation failed for generated idea %s", iid
                )

        asyncio.create_task(_eval())
