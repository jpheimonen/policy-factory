"""Heartbeat orchestrator — drives the four-tier escalation chain.

The heartbeat orchestrator is an async function that drives the
tiered escalation chain. All dependencies are passed as arguments
to keep the function testable and decoupled.

Tier 1: News skim (Haiku) — scans yle.fi for relevant developments
Tier 2: Triage analysis (Sonnet) — assesses flagged items with web search
Tier 3: SA update (Opus) — modifies SA markdown files
Tier 4: Cascade + idea generation — triggers cascade and generates ideas
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable

from policy_factory.events import (
    EventEmitter,
    HeartbeatCompleted,
    HeartbeatStarted,
    HeartbeatTierCompleted,
)
from policy_factory.store import PolicyStore

logger = logging.getLogger(__name__)

# Tier output markers (must match prompt templates)
_NOTHING_NOTEWORTHY_MARKER = "NOTHING_NOTEWORTHY"
_NO_UPDATE_MARKER = "NO_UPDATE_NEEDED"

# Type alias for cascade trigger callable
CascadeTriggerFn = Callable[..., Awaitable[Any]]

# Type alias for idea generation callable
IdeaGeneratorFn = Callable[..., Awaitable[Any]]


async def run_heartbeat(
    trigger: str,
    store: PolicyStore,
    emitter: EventEmitter,
    data_dir: Path,
    cascade_trigger: CascadeTriggerFn | None = None,
    idea_generator: IdeaGeneratorFn | None = None,
) -> str:
    """Run the four-tier heartbeat escalation chain.

    Args:
        trigger: How the heartbeat was initiated ("scheduled" or "manual").
        store: PolicyStore for persistence.
        emitter: EventEmitter for broadcasting events.
        data_dir: Root data directory.
        cascade_trigger: Callable to trigger a cascade (from step 015).
        idea_generator: Callable to generate ideas (from step 018).

    Returns:
        The heartbeat run ID.
    """
    # Create heartbeat run record
    run_id = store.create_heartbeat_run(trigger)
    logger.info("Heartbeat started: run_id=%s, trigger=%s", run_id[:8], trigger)

    # Emit start event
    await emitter.emit(HeartbeatStarted(heartbeat_run_id=run_id))

    try:
        # --- Tier 1: News Skim ---
        tier1_result = await _run_tier1(run_id, store, emitter, data_dir)

        if not tier1_result["escalated"]:
            # Nothing noteworthy — stop here
            store.complete_heartbeat_run(run_id)
            await emitter.emit(
                HeartbeatCompleted(heartbeat_run_id=run_id, highest_tier=1)
            )
            logger.info("Heartbeat %s completed at Tier 1: nothing noteworthy", run_id[:8])
            return run_id

        # --- Tier 2: Triage Analysis ---
        tier2_result = await _run_tier2(
            run_id, store, emitter, data_dir,
            flagged_items=tier1_result["output"],
        )

        if not tier2_result["escalated"]:
            # No updates warranted — stop here
            store.complete_heartbeat_run(run_id)
            await emitter.emit(
                HeartbeatCompleted(heartbeat_run_id=run_id, highest_tier=2)
            )
            logger.info("Heartbeat %s completed at Tier 2: no updates warranted", run_id[:8])
            return run_id

        # --- Tier 3: SA Update ---
        tier3_result = await _run_tier3(
            run_id, store, emitter, data_dir,
            triage_assessment=tier2_result["output"],
        )

        # Tier 3 always escalates to Tier 4 on success
        if not tier3_result["success"]:
            # Tier 3 failed — stop here
            store.complete_heartbeat_run(run_id)
            await emitter.emit(
                HeartbeatCompleted(heartbeat_run_id=run_id, highest_tier=2)
            )
            logger.warning("Heartbeat %s stopped: Tier 3 failed", run_id[:8])
            return run_id

        # --- Tier 4: Cascade + Idea Generation ---
        await _run_tier4(
            run_id, store, emitter, data_dir,
            cascade_trigger=cascade_trigger,
            idea_generator=idea_generator,
        )

        store.complete_heartbeat_run(run_id)
        await emitter.emit(
            HeartbeatCompleted(heartbeat_run_id=run_id, highest_tier=4)
        )
        logger.info("Heartbeat %s completed at Tier 4: full cascade triggered", run_id[:8])
        return run_id

    except Exception as exc:
        logger.exception("Heartbeat %s failed unexpectedly: %s", run_id[:8], exc)
        store.complete_heartbeat_run(run_id)
        return run_id


# ---------------------------------------------------------------------------
# Tier 1 — News Skim
# ---------------------------------------------------------------------------


async def _run_tier1(
    run_id: str,
    store: PolicyStore,
    emitter: EventEmitter,
    data_dir: Path,
) -> dict[str, Any]:
    """Run Tier 1: news skim with Haiku.

    Returns:
        Dict with 'escalated' (bool), 'output' (str), and 'success' (bool).
    """
    from policy_factory.agent.config import AgentConfig, resolve_model
    from policy_factory.agent.prompts import build_agent_prompt
    from policy_factory.agent.session import AgentSession
    from policy_factory.data.layers import read_narrative
    from policy_factory.server.deps import get_anthropic_client

    # Gather context
    sa_summary = read_narrative(data_dir, "situational-awareness")
    if not sa_summary:
        sa_summary = "(No situational awareness content available yet.)"

    current_date = date.today().isoformat()

    # Build prompt
    prompt = build_agent_prompt(
        "heartbeat",
        "skim",
        current_date=current_date,
        sa_summary=sa_summary,
    )

    # Resolve model
    model = resolve_model("heartbeat-skim")

    # Record agent run
    agent_run_id = store.create_agent_run(
        cascade_id=None,
        agent_type="heartbeat-skim",
        agent_label="Heartbeat — news skim",
        model=model,
        target_layer="situational-awareness",
    )

    try:
        # Get shared Anthropic client
        client = get_anthropic_client()

        # Create and run session
        config = AgentConfig(model=model)
        session = AgentSession(
            config=config,
            emitter=emitter,
            context_id=run_id,
            agent_label="Heartbeat — news skim",
            client=client,
            data_dir=data_dir,
        )
        result = await session.run(prompt)

        # Record completion
        output_text = result.full_output or result.result_text or ""
        store.complete_agent_run(
            agent_run_id,
            success=not result.is_error,
            error_message=result.result_text if result.is_error else None,
            cost=result.total_cost_usd,
            output_text=result.full_output,
        )

        if result.is_error:
            raise RuntimeError(f"Tier 1 agent error: {result.result_text}")

        # Parse: check for nothing-noteworthy marker
        escalated = _NOTHING_NOTEWORTHY_MARKER not in output_text.upper()

        if escalated:
            outcome = _extract_outcome_summary(output_text, tier=1)
        else:
            outcome = "No significant developments found"

        # Update heartbeat record
        store.update_heartbeat_tier(
            run_id, tier=1, escalated=escalated,
            outcome=outcome, agent_run_id=agent_run_id,
        )

        # Emit tier completed event
        await emitter.emit(
            HeartbeatTierCompleted(
                heartbeat_run_id=run_id,
                tier=1,
                outcome=outcome,
                escalated=escalated,
            )
        )

        return {"escalated": escalated, "output": output_text, "success": True}

    except Exception as exc:
        error_msg = str(exc)
        logger.error("Heartbeat Tier 1 failed: %s", error_msg)

        store.complete_agent_run(
            agent_run_id,
            success=False,
            error_message=error_msg,
        )

        store.update_heartbeat_tier(
            run_id, tier=1, escalated=False,
            outcome=f"Failed: {error_msg}", agent_run_id=agent_run_id,
        )

        await emitter.emit(
            HeartbeatTierCompleted(
                heartbeat_run_id=run_id,
                tier=1,
                outcome=f"Failed: {error_msg}",
                escalated=False,
            )
        )

        return {"escalated": False, "output": "", "success": False}


# ---------------------------------------------------------------------------
# Tier 2 — Triage Analysis
# ---------------------------------------------------------------------------


async def _run_tier2(
    run_id: str,
    store: PolicyStore,
    emitter: EventEmitter,
    data_dir: Path,
    *,
    flagged_items: str,
) -> dict[str, Any]:
    """Run Tier 2: triage analysis with Sonnet.

    Args:
        flagged_items: The flagged items text from Tier 1.

    Returns:
        Dict with 'escalated' (bool), 'output' (str), and 'success' (bool).
    """
    from policy_factory.agent.config import AgentConfig, resolve_model
    from policy_factory.agent.prompts import build_agent_prompt
    from policy_factory.agent.session import AgentSession
    from policy_factory.data.layers import read_narrative
    from policy_factory.server.deps import get_anthropic_client

    # Gather context
    sa_summary = read_narrative(data_dir, "situational-awareness")
    if not sa_summary:
        sa_summary = "(No situational awareness content available yet.)"

    # Build prompt
    prompt = build_agent_prompt(
        "heartbeat",
        "triage",
        flagged_items=flagged_items,
        sa_summary=sa_summary,
    )

    # Resolve model
    model = resolve_model("heartbeat-triage")

    # Record agent run
    agent_run_id = store.create_agent_run(
        cascade_id=None,
        agent_type="heartbeat-triage",
        agent_label="Heartbeat — triage analysis",
        model=model,
        target_layer="situational-awareness",
    )

    try:
        # Get shared Anthropic client
        client = get_anthropic_client()

        # Create and run session
        config = AgentConfig(model=model)
        session = AgentSession(
            config=config,
            emitter=emitter,
            context_id=run_id,
            agent_label="Heartbeat — triage analysis",
            client=client,
            data_dir=data_dir,
        )
        result = await session.run(prompt)

        # Record completion
        output_text = result.full_output or result.result_text or ""
        store.complete_agent_run(
            agent_run_id,
            success=not result.is_error,
            error_message=result.result_text if result.is_error else None,
            cost=result.total_cost_usd,
            output_text=result.full_output,
        )

        if result.is_error:
            raise RuntimeError(f"Tier 2 agent error: {result.result_text}")

        # Parse: check for no-update marker
        escalated = _NO_UPDATE_MARKER not in output_text.upper()

        if escalated:
            outcome = _extract_outcome_summary(output_text, tier=2)
        else:
            outcome = "No SA updates warranted"

        # Update heartbeat record
        store.update_heartbeat_tier(
            run_id, tier=2, escalated=escalated,
            outcome=outcome, agent_run_id=agent_run_id,
        )

        # Emit tier completed event
        await emitter.emit(
            HeartbeatTierCompleted(
                heartbeat_run_id=run_id,
                tier=2,
                outcome=outcome,
                escalated=escalated,
            )
        )

        return {"escalated": escalated, "output": output_text, "success": True}

    except Exception as exc:
        error_msg = str(exc)
        logger.error("Heartbeat Tier 2 failed: %s", error_msg)

        store.complete_agent_run(
            agent_run_id,
            success=False,
            error_message=error_msg,
        )

        store.update_heartbeat_tier(
            run_id, tier=2, escalated=False,
            outcome=f"Failed: {error_msg}", agent_run_id=agent_run_id,
        )

        await emitter.emit(
            HeartbeatTierCompleted(
                heartbeat_run_id=run_id,
                tier=2,
                outcome=f"Failed: {error_msg}",
                escalated=False,
            )
        )

        return {"escalated": False, "output": "", "success": False}


# ---------------------------------------------------------------------------
# Tier 3 — SA Update
# ---------------------------------------------------------------------------


async def _run_tier3(
    run_id: str,
    store: PolicyStore,
    emitter: EventEmitter,
    data_dir: Path,
    *,
    triage_assessment: str,
) -> dict[str, Any]:
    """Run Tier 3: SA update with Opus.

    Args:
        triage_assessment: The triage assessment text from Tier 2.

    Returns:
        Dict with 'escalated' (bool — always True on success),
        'output' (str), and 'success' (bool).
    """
    from policy_factory.agent.config import AgentConfig, resolve_model
    from policy_factory.agent.prompts import build_agent_prompt
    from policy_factory.agent.session import AgentSession
    from policy_factory.cascade.content import gather_layer_content
    from policy_factory.data.git import commit_changes
    from policy_factory.server.deps import get_anthropic_client

    # Gather SA layer content
    sa_content = gather_layer_content(data_dir, "situational-awareness")

    # Gather pending feedback memos targeting the SA layer
    pending_memos = store.get_pending_memos("situational-awareness")
    if pending_memos:
        memo_texts = []
        for memo in pending_memos:
            memo_texts.append(
                f"- From {memo.source_layer}: {memo.content}"
            )
        feedback_text = "\n".join(memo_texts)
    else:
        feedback_text = "(No pending feedback memos targeting the SA layer.)"

    # Build prompt
    prompt = build_agent_prompt(
        "heartbeat",
        "sa-update",
        triage_assessment=triage_assessment,
        sa_content=sa_content,
        feedback_memos=feedback_text,
    )

    # Resolve model
    model = resolve_model("heartbeat-sa-update")

    # Record agent run
    agent_run_id = store.create_agent_run(
        cascade_id=None,
        agent_type="heartbeat-sa-update",
        agent_label="Heartbeat — SA update",
        model=model,
        target_layer="situational-awareness",
    )

    try:
        # Get shared Anthropic client
        client = get_anthropic_client()

        # Create and run session
        config = AgentConfig(model=model)
        session = AgentSession(
            config=config,
            emitter=emitter,
            context_id=run_id,
            agent_label="Heartbeat — SA update",
            client=client,
            data_dir=data_dir,
        )
        result = await session.run(prompt)

        # Record completion
        output_text = result.full_output or result.result_text or ""
        store.complete_agent_run(
            agent_run_id,
            success=not result.is_error,
            error_message=result.result_text if result.is_error else None,
            cost=result.total_cost_usd,
            output_text=result.full_output,
        )

        if result.is_error:
            raise RuntimeError(f"Tier 3 agent error: {result.result_text}")

        # Auto-commit changes
        try:
            commit_changes(
                data_dir,
                "Heartbeat SA update — automated situational awareness update",
            )
        except Exception as git_exc:
            logger.warning(
                "Git commit failed after Tier 3 SA update: %s", git_exc
            )

        outcome = "SA layer updated successfully"

        # Tier 3 always escalates to Tier 4 on success
        store.update_heartbeat_tier(
            run_id, tier=3, escalated=True,
            outcome=outcome, agent_run_id=agent_run_id,
        )

        await emitter.emit(
            HeartbeatTierCompleted(
                heartbeat_run_id=run_id,
                tier=3,
                outcome=outcome,
                escalated=True,
            )
        )

        return {"escalated": True, "output": output_text, "success": True}

    except Exception as exc:
        error_msg = str(exc)
        logger.error("Heartbeat Tier 3 failed: %s", error_msg)

        store.complete_agent_run(
            agent_run_id,
            success=False,
            error_message=error_msg,
        )

        store.update_heartbeat_tier(
            run_id, tier=3, escalated=False,
            outcome=f"Failed: {error_msg}", agent_run_id=agent_run_id,
        )

        await emitter.emit(
            HeartbeatTierCompleted(
                heartbeat_run_id=run_id,
                tier=3,
                outcome=f"Failed: {error_msg}",
                escalated=False,
            )
        )

        return {"escalated": False, "output": "", "success": False}


# ---------------------------------------------------------------------------
# Tier 4 — Cascade + Idea Generation
# ---------------------------------------------------------------------------


async def _run_tier4(
    run_id: str,
    store: PolicyStore,
    emitter: EventEmitter,
    data_dir: Path,
    *,
    cascade_trigger: CascadeTriggerFn | None = None,
    idea_generator: IdeaGeneratorFn | None = None,
) -> dict[str, Any]:
    """Run Tier 4: trigger cascade and idea generation.

    Both cascade and idea generation run asynchronously — Tier 4
    does not wait for them to complete.

    Returns:
        Dict with 'escalated' (False — final tier), 'output' (str),
        and 'success' (bool).
    """
    outcome_parts: list[str] = []

    # Trigger cascade from SA layer
    if cascade_trigger is not None:
        try:
            result = await cascade_trigger(
                trigger_source="heartbeat",
                starting_layer="situational-awareness",
                store=store,
                emitter=emitter,
                data_dir=data_dir,
            )
            outcome_parts.append("Cascade triggered")
            logger.info(
                "Heartbeat Tier 4: cascade triggered (result=%s)", result
            )
        except Exception as exc:
            logger.error("Heartbeat Tier 4: cascade trigger failed: %s", exc)
            outcome_parts.append(f"Cascade trigger failed: {exc}")
    else:
        outcome_parts.append("Cascade trigger not available")

    # Trigger idea generation (as a background task)
    if idea_generator is not None:
        try:

            async def _generate() -> None:
                try:
                    await idea_generator(
                        store=store,
                        emitter=emitter,
                        data_dir=data_dir,
                    )
                except Exception:
                    logger.exception("Background idea generation failed")

            asyncio.create_task(_generate(), name="heartbeat-idea-gen")
            outcome_parts.append("Idea generation launched")
        except Exception as exc:
            logger.error(
                "Heartbeat Tier 4: idea generation launch failed: %s", exc
            )
            outcome_parts.append(f"Idea generation failed: {exc}")
    else:
        outcome_parts.append("Idea generator not available")

    outcome = "; ".join(outcome_parts)

    # Tier 4 is the final tier — never escalates
    store.update_heartbeat_tier(
        run_id, tier=4, escalated=False,
        outcome=outcome,
    )

    await emitter.emit(
        HeartbeatTierCompleted(
            heartbeat_run_id=run_id,
            tier=4,
            outcome=outcome,
            escalated=False,
        )
    )

    return {"escalated": False, "output": outcome, "success": True}


# ---------------------------------------------------------------------------
# Output parsing helpers
# ---------------------------------------------------------------------------


def _extract_outcome_summary(output: str, *, tier: int) -> str:
    """Extract a brief outcome summary from agent output.

    The summary is used in the structured log and events. It's kept
    brief (first meaningful line or a truncated excerpt).

    Args:
        output: The full agent output text.
        tier: Which tier produced this output (for context).

    Returns:
        A brief summary string (max ~200 chars).
    """
    if not output:
        return f"Tier {tier} completed"

    # Look for STATUS line
    for line in output.split("\n"):
        stripped = line.strip()
        if stripped.startswith("STATUS:"):
            status = stripped.replace("STATUS:", "").strip()
            if status:
                return status

    # Fallback: first non-empty, non-header line (max 200 chars)
    for line in output.split("\n"):
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith("```"):
            if len(stripped) > 200:
                return stripped[:197] + "..."
            return stripped

    return f"Tier {tier} completed"
