"""Cascade orchestrator — drives the layer-by-layer update sequence.

The cascade orchestrator is a pure async function (not a class), following
cc-runner's pipeline orchestrator pattern. It receives all dependencies
as arguments and stores mutable state in the SQLite cascade record.

The orchestrator:
1. Acquires the single-writer lock (or queues the cascade).
2. Iterates through layers from starting layer to topmost (policies).
3. For each layer: runs generation → critics → synthesis in sequence.
4. Checks for pause requests between each sub-step.
5. On error: pauses the cascade with error info, waits for resume/cancel.
6. On completion: releases the lock, processes the queue.

The critic runner and synthesis runner are black-box callables provided by
the caller (implemented in step 016). This step defines the interface and
uses them opaquely.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Awaitable, Callable, Protocol

from policy_factory.data.git import commit_changes
from policy_factory.data.layers import LAYERS, list_items, read_item, read_narrative
from policy_factory.events import (
    CascadeLockAcquired,
    CascadeLockReleased,
    CascadeQueued,
    CascadeStarted,
    EventEmitter,
    LayerGenerationCompleted,
    LayerGenerationStarted,
)
from policy_factory.store import PolicyStore

from .controller import CascadeController, CascadeState

logger = logging.getLogger(__name__)

# Layer slugs in hierarchical order (bottom to top)
_LAYER_ORDER: list[str] = [layer.slug for layer in LAYERS]


# ---------------------------------------------------------------------------
# Layer hierarchy utilities
# ---------------------------------------------------------------------------


def layers_from(starting_layer: str) -> list[str]:
    """Return ordered list of layer slugs from starting layer to topmost.

    Args:
        starting_layer: Layer slug to start from.

    Returns:
        List of slugs from starting_layer upward through the hierarchy.

    Raises:
        ValueError: If the starting layer is not a valid layer slug.
    """
    if starting_layer not in _LAYER_ORDER:
        valid = ", ".join(_LAYER_ORDER)
        raise ValueError(
            f"Invalid starting layer: {starting_layer!r}. Valid: {valid}"
        )
    start_idx = _LAYER_ORDER.index(starting_layer)
    return _LAYER_ORDER[start_idx:]


def layers_below(layer_slug: str) -> list[str]:
    """Return the list of layers below the given layer in the hierarchy.

    Args:
        layer_slug: Layer slug.

    Returns:
        List of slugs below this layer (empty for the bottom layer).

    Raises:
        ValueError: If the layer slug is not valid.
    """
    if layer_slug not in _LAYER_ORDER:
        valid = ", ".join(_LAYER_ORDER)
        raise ValueError(
            f"Invalid layer slug: {layer_slug!r}. Valid: {valid}"
        )
    idx = _LAYER_ORDER.index(layer_slug)
    return _LAYER_ORDER[:idx]


# ---------------------------------------------------------------------------
# Callable protocols for critic/synthesis runners
# ---------------------------------------------------------------------------


class CriticRunnerFn(Protocol):
    """Interface for the critic runner (implemented in step 016)."""

    async def __call__(
        self,
        layer_slug: str,
        cascade_id: str,
        store: PolicyStore,
        emitter: EventEmitter,
        data_dir: Path,
    ) -> Any:
        """Run all 6 critics against the given layer.

        Returns critic results (opaque to the orchestrator).
        """
        ...


class SynthesisRunnerFn(Protocol):
    """Interface for the synthesis runner (implemented in step 016)."""

    async def __call__(
        self,
        layer_slug: str,
        critic_results: Any,
        cascade_id: str,
        store: PolicyStore,
        emitter: EventEmitter,
        data_dir: Path,
    ) -> Any:
        """Run synthesis integrating all critic outputs.

        Returns synthesis results (opaque to the orchestrator).
        """
        ...


# Type for the generation agent runner callable
GenerationRunnerFn = Callable[
    [str, str, PolicyStore, EventEmitter, Path, str | None],
    Awaitable[Any],
]


# ---------------------------------------------------------------------------
# Context gathering for generation prompts
# ---------------------------------------------------------------------------


def _gather_generation_context(
    data_dir: Path,
    layer_slug: str,
    user_context: str | None = None,
) -> str:
    """Gather context for the generation agent.

    Collects content from layers below the current layer and any
    user-provided context.

    Args:
        data_dir: Root data directory.
        layer_slug: The layer being generated.
        user_context: Optional user input context.

    Returns:
        A formatted context string for the generation prompt.
    """
    parts: list[str] = []

    # Content from layers below
    below = layers_below(layer_slug)
    for below_slug in below:
        narrative = read_narrative(data_dir, below_slug)
        items = list_items(data_dir, below_slug)

        layer_display = below_slug.replace("-", " ").title()
        parts.append(f"## {layer_display} Layer\n")

        if narrative:
            parts.append(f"### Narrative Summary\n{narrative}\n")

        if items:
            parts.append("### Items\n")
            for item_summary in items:
                try:
                    fm, body = read_item(data_dir, below_slug, item_summary.filename)
                    title = fm.get("title", item_summary.filename)
                    parts.append(f"#### {title}\n{body}\n")
                except Exception:
                    logger.warning(
                        "Failed to read item %s/%s for context",
                        below_slug,
                        item_summary.filename,
                    )
                    continue

    # User input context
    if user_context:
        parts.append(f"## User Input\n{user_context}\n")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Default generation runner (uses AgentSession from step 014)
# ---------------------------------------------------------------------------


async def _default_generation_runner(
    layer_slug: str,
    cascade_id: str,
    store: PolicyStore,
    emitter: EventEmitter,
    data_dir: Path,
    user_context: str | None = None,
) -> Any:
    """Default generation runner using the agent framework (step 014).

    This runs the actual Claude Code agent to generate/update a layer.
    It creates an AgentSession, builds the prompt, records the agent
    run, and returns the result.
    """
    from policy_factory.agent.config import AgentConfig, resolve_model
    from policy_factory.agent.prompts import build_agent_prompt
    from policy_factory.agent.session import AgentSession

    # Gather context from lower layers
    context = _gather_generation_context(data_dir, layer_slug, user_context)

    # Resolve model for the generator role
    model = resolve_model("generator")

    # Build the generation prompt
    layer_name = layer_slug.replace("-", "_")
    prompt = build_agent_prompt(
        "generators",
        layer_name,
        context=context,
        layer_slug=layer_slug,
    )

    # Create agent config
    config = AgentConfig(
        cwd=data_dir,
        model=model,
    )

    # Record agent run start
    agent_label = f"{layer_slug.replace('-', ' ').title()} layer generator"
    agent_run_id = store.create_agent_run(
        cascade_id=cascade_id,
        agent_type="generator",
        agent_label=agent_label,
        model=model,
        target_layer=layer_slug,
    )

    # Create and run the session
    session = AgentSession(
        config=config,
        emitter=emitter,
        context_id=cascade_id,
        agent_label=agent_label,
    )

    try:
        result = await session.run(prompt)
        store.complete_agent_run(
            agent_run_id,
            success=not result.is_error,
            error_message=result.result_text if result.is_error else None,
            cost=result.total_cost_usd,
            output_text=result.full_output,
        )
        if result.is_error:
            raise RuntimeError(f"Generation agent failed: {result.result_text}")
        return result
    except Exception as exc:
        store.complete_agent_run(
            agent_run_id,
            success=False,
            error_message=str(exc),
        )
        raise


# ---------------------------------------------------------------------------
# Orchestration loop
# ---------------------------------------------------------------------------


async def _run_cascade_loop(
    cascade_id: str,
    controller: CascadeController,
    store: PolicyStore,
    emitter: EventEmitter,
    data_dir: Path,
    starting_layer: str,
    user_context: str | None,
    generation_runner: GenerationRunnerFn | None,
    critic_runner: CriticRunnerFn | None,
    synthesis_runner: SynthesisRunnerFn | None,
    resume_layer: str | None = None,
    resume_step: str | None = None,
) -> None:
    """Drive the cascade through all layers from starting to topmost.

    This function is launched as a background task by the trigger function.
    It manages the lifecycle of each layer's sub-steps and handles
    pause/resume/cancel.

    Args:
        cascade_id: The cascade run ID.
        controller: The cascade controller for state management.
        store: The PolicyStore for persistence.
        emitter: EventEmitter for broadcasting progress.
        data_dir: Root data directory.
        starting_layer: Layer slug where the cascade starts.
        user_context: Optional user input context for the first layer.
        generation_runner: Callable for running generation. Uses default if None.
        critic_runner: Callable for running critics (step 016). No-ops if None.
        synthesis_runner: Callable for running synthesis (step 016). No-ops if None.
        resume_layer: Layer to resume from (if resuming a paused cascade).
        resume_step: Step to resume from (if resuming a paused cascade).
    """
    gen_runner = generation_runner or _default_generation_runner

    try:
        layer_list = layers_from(starting_layer)
    except ValueError as exc:
        await controller.fail(str(exc), starting_layer, "generation")
        store.update_cascade_status(cascade_id, "failed", str(exc), starting_layer)
        return

    for layer_slug in layer_list:
        # Determine which step to start from (for resume)
        steps = ["generation", "critics", "synthesis"]
        start_step_idx = 0

        if resume_layer and resume_step and layer_slug == resume_layer:
            # Resume from the specified step
            if resume_step in steps:
                start_step_idx = steps.index(resume_step)
            resume_layer = None  # Only apply resume on the first matching layer
            resume_step = None
        elif resume_layer and layer_slug != resume_layer:
            # Skip layers before the resume layer
            continue

        for step_idx in range(start_step_idx, len(steps)):
            step = steps[step_idx]

            # --- Pause check ---
            if controller.is_pause_requested():
                if controller.state == CascadeState.RUNNING:
                    await controller.pause(
                        error="Pause requested by user",
                        error_layer=layer_slug,
                        error_step=step,
                    )
                store.update_cascade_status(
                    cascade_id,
                    "paused",
                    "Pause requested by user",
                    layer_slug,
                )
                store.update_cascade_progress(cascade_id, layer_slug, step)

                # Wait for resume or cancel
                new_state = await controller.wait_for_resume_or_cancel()
                if new_state == CascadeState.CANCELLED:
                    store.update_cascade_status(cascade_id, "cancelled")
                    await emitter.emit(
                        CascadeLockReleased(cascade_id=cascade_id)
                    )
                    await _process_queue(
                        store, emitter, data_dir,
                        generation_runner, critic_runner, synthesis_runner,
                    )
                    return
                # Resumed — continue from current position
                store.update_cascade_status(cascade_id, "running")

            # Update progress
            controller.current_layer = layer_slug
            controller.current_step = step
            store.update_cascade_progress(cascade_id, layer_slug, step)

            # --- Execute the step ---
            try:
                if step == "generation":
                    await emitter.emit(
                        LayerGenerationStarted(
                            cascade_id=cascade_id,
                            layer_slug=layer_slug,
                        )
                    )

                    # Provide user context only for the first layer
                    ctx = user_context if layer_slug == starting_layer else None
                    await gen_runner(
                        layer_slug, cascade_id, store, emitter, data_dir, ctx
                    )

                    # Auto-commit after generation
                    try:
                        commit_changes(
                            data_dir,
                            f"Generate {layer_slug} layer [cascade {cascade_id[:8]}]",
                        )
                    except Exception as git_exc:
                        logger.warning(
                            "Git commit failed after generation for %s: %s",
                            layer_slug,
                            git_exc,
                        )

                    await emitter.emit(
                        LayerGenerationCompleted(
                            cascade_id=cascade_id,
                            layer_slug=layer_slug,
                        )
                    )

                elif step == "critics":
                    if critic_runner is not None:
                        await critic_runner(
                            layer_slug, cascade_id, store, emitter, data_dir,
                        )
                    # If critic_runner is None, skip (step 016 not yet implemented)

                elif step == "synthesis":
                    if synthesis_runner is not None:
                        # Pass critic results = None for now; step 016 handles internals
                        await synthesis_runner(
                            layer_slug, None, cascade_id, store, emitter, data_dir,
                        )
                    # If synthesis_runner is None, skip (step 016 not yet implemented)

            except Exception as exc:
                # Agent failure — pause the cascade with error info
                error_msg = str(exc)
                logger.error(
                    "Cascade %s failed at %s/%s: %s",
                    cascade_id[:8],
                    layer_slug,
                    step,
                    error_msg,
                )

                await controller.pause(
                    error=error_msg,
                    error_layer=layer_slug,
                    error_step=step,
                )
                store.update_cascade_status(
                    cascade_id, "paused", error_msg, layer_slug,
                )

                # Wait for user to resume or cancel
                new_state = await controller.wait_for_resume_or_cancel()
                if new_state == CascadeState.CANCELLED:
                    store.update_cascade_status(cascade_id, "cancelled")
                    await emitter.emit(
                        CascadeLockReleased(cascade_id=cascade_id)
                    )
                    await _process_queue(
                        store, emitter, data_dir,
                        generation_runner, critic_runner, synthesis_runner,
                    )
                    return

                # Resumed — retry the failed step
                store.update_cascade_status(cascade_id, "running")
                # Decrement step_idx to retry this step
                # We do this by recursively entering the loop at the same position
                try:
                    if step == "generation":
                        await emitter.emit(
                            LayerGenerationStarted(
                                cascade_id=cascade_id,
                                layer_slug=layer_slug,
                            )
                        )
                        ctx = user_context if layer_slug == starting_layer else None
                        await gen_runner(
                            layer_slug, cascade_id, store, emitter, data_dir, ctx
                        )
                        try:
                            commit_changes(
                                data_dir,
                                f"Generate {layer_slug} layer [cascade {cascade_id[:8]}]",
                            )
                        except Exception:
                            pass
                        await emitter.emit(
                            LayerGenerationCompleted(
                                cascade_id=cascade_id,
                                layer_slug=layer_slug,
                            )
                        )
                    elif step == "critics" and critic_runner is not None:
                        await critic_runner(
                            layer_slug, cascade_id, store, emitter, data_dir,
                        )
                    elif step == "synthesis" and synthesis_runner is not None:
                        await synthesis_runner(
                            layer_slug, None, cascade_id, store, emitter, data_dir,
                        )
                except Exception as retry_exc:
                    # Second failure — transition to failed
                    error_msg = f"Retry failed: {retry_exc}"
                    await controller.fail(error_msg, layer_slug, step)
                    store.update_cascade_status(
                        cascade_id, "failed", error_msg, layer_slug,
                    )
                    await emitter.emit(
                        CascadeLockReleased(cascade_id=cascade_id)
                    )
                    await _process_queue(
                        store, emitter, data_dir,
                        generation_runner, critic_runner, synthesis_runner,
                    )
                    return

    # --- Cascade completed ---
    await controller.complete()
    store.update_cascade_status(cascade_id, "completed")
    await emitter.emit(CascadeLockReleased(cascade_id=cascade_id))

    # Process the queue
    await _process_queue(
        store, emitter, data_dir,
        generation_runner, critic_runner, synthesis_runner,
    )


# ---------------------------------------------------------------------------
# Queue processing
# ---------------------------------------------------------------------------


async def _process_queue(
    store: PolicyStore,
    emitter: EventEmitter,
    data_dir: Path,
    generation_runner: GenerationRunnerFn | None,
    critic_runner: CriticRunnerFn | None,
    synthesis_runner: SynthesisRunnerFn | None,
) -> None:
    """Dequeue and start the next cascade if the queue is non-empty."""
    entry = store.dequeue_cascade()
    if entry is None:
        return

    logger.info(
        "Starting queued cascade: trigger=%s, layer=%s",
        entry.trigger_source,
        entry.starting_layer,
    )

    await trigger_cascade(
        trigger_source=entry.trigger_source,
        starting_layer=entry.starting_layer,
        context=entry.context,
        store=store,
        emitter=emitter,
        data_dir=data_dir,
        generation_runner=generation_runner,
        critic_runner=critic_runner,
        synthesis_runner=synthesis_runner,
    )


# ---------------------------------------------------------------------------
# Public API — trigger function
# ---------------------------------------------------------------------------


async def trigger_cascade(
    trigger_source: str,
    starting_layer: str,
    store: PolicyStore,
    emitter: EventEmitter,
    data_dir: Path,
    context: str | None = None,
    generation_runner: GenerationRunnerFn | None = None,
    critic_runner: CriticRunnerFn | None = None,
    synthesis_runner: SynthesisRunnerFn | None = None,
) -> tuple[str, bool]:
    """Trigger a cascade — the public API entry point.

    If the lock is free, creates a cascade run, acquires the lock, creates
    a controller, registers it, and launches the orchestration loop as a
    background task. Returns the cascade ID immediately.

    If the lock is held, enqueues the cascade request, emits a
    ``CascadeQueued`` event, and returns the queue entry ID.

    Args:
        trigger_source: What triggered the cascade (user_input, layer_refresh,
            heartbeat, seed).
        starting_layer: Layer slug where the cascade starts.
        store: The PolicyStore for persistence.
        emitter: EventEmitter for broadcasting events.
        data_dir: Root data directory.
        context: Optional context data (e.g. user input text).
        generation_runner: Optional callable for running generation.
        critic_runner: Optional callable for running critics.
        synthesis_runner: Optional callable for running synthesis.

    Returns:
        Tuple of (id_string, is_cascade). If is_cascade is True, the ID
        is a cascade run ID. If False, it's a queue entry ID.
    """
    # Import here to avoid circular imports at module level
    from policy_factory.server.deps import (
        register_cascade_controller,
    )

    # Check lock
    held, held_by = store.is_lock_held()
    if held:
        # Queue the cascade
        queue_id, position = store.enqueue_cascade(
            trigger_source, starting_layer, context,
        )
        await emitter.emit(
            CascadeQueued(cascade_id=queue_id, queue_position=position)
        )
        logger.info(
            "Cascade queued (position %d): trigger=%s, layer=%s",
            position,
            trigger_source,
            starting_layer,
        )
        return queue_id, False

    # Lock is free — create cascade run and acquire lock
    cascade_id = store.create_cascade(trigger_source, starting_layer, context)
    if not store.acquire_lock(cascade_id):
        # Race condition — another cascade acquired the lock between check and acquire
        store.update_cascade_status(cascade_id, "cancelled")
        queue_id, position = store.enqueue_cascade(
            trigger_source, starting_layer, context,
        )
        await emitter.emit(
            CascadeQueued(cascade_id=queue_id, queue_position=position)
        )
        return queue_id, False

    # Create and register controller
    controller = CascadeController(cascade_id, emitter)
    register_cascade_controller(cascade_id, controller)

    # Emit lifecycle events
    await emitter.emit(CascadeLockAcquired(cascade_id=cascade_id))
    await emitter.emit(
        CascadeStarted(
            cascade_id=cascade_id,
            trigger_source=trigger_source,
            starting_layer=starting_layer,
        )
    )

    # Launch orchestration loop as background task
    asyncio.create_task(
        _run_cascade_with_cleanup(
            cascade_id=cascade_id,
            controller=controller,
            store=store,
            emitter=emitter,
            data_dir=data_dir,
            starting_layer=starting_layer,
            user_context=context,
            generation_runner=generation_runner,
            critic_runner=critic_runner,
            synthesis_runner=synthesis_runner,
        ),
        name=f"cascade-{cascade_id[:8]}",
    )

    return cascade_id, True


async def _run_cascade_with_cleanup(
    cascade_id: str,
    controller: CascadeController,
    store: PolicyStore,
    emitter: EventEmitter,
    data_dir: Path,
    starting_layer: str,
    user_context: str | None,
    generation_runner: GenerationRunnerFn | None,
    critic_runner: CriticRunnerFn | None,
    synthesis_runner: SynthesisRunnerFn | None,
) -> None:
    """Wrapper around the cascade loop that ensures cleanup on unexpected errors."""
    from policy_factory.server.deps import unregister_cascade_controller

    try:
        await _run_cascade_loop(
            cascade_id=cascade_id,
            controller=controller,
            store=store,
            emitter=emitter,
            data_dir=data_dir,
            starting_layer=starting_layer,
            user_context=user_context,
            generation_runner=generation_runner,
            critic_runner=critic_runner,
            synthesis_runner=synthesis_runner,
        )
    except Exception as exc:
        logger.exception("Cascade %s crashed unexpectedly", cascade_id[:8])
        store.update_cascade_status(
            cascade_id, "failed", f"Unexpected error: {exc}", None,
        )
        await emitter.emit(CascadeLockReleased(cascade_id=cascade_id))
    finally:
        unregister_cascade_controller(cascade_id)
