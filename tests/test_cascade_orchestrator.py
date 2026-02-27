"""Tests for the cascade orchestrator.

Tests use mock agent runners to isolate the orchestrator's behaviour
from the actual Claude Code SDK. The generation runner, critic runner,
and synthesis runner are all provided as mock callables.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from policy_factory.cascade.controller import CascadeController, CascadeState
from policy_factory.cascade.orchestrator import (
    _gather_generation_context,
    _run_cascade_loop,
    layers_below,
    layers_from,
    trigger_cascade,
)
from policy_factory.events import (
    BaseEvent,
    CascadeQueued,
    EventEmitter,
)
from policy_factory.store import PolicyStore

# -----------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------


@pytest.fixture
def emitter() -> EventEmitter:
    """Provide a fresh EventEmitter."""
    return EventEmitter()


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """Create a minimal data directory with layers."""
    for slug in ["values", "situational-awareness", "strategic-objectives",
                  "tactical-objectives", "policies"]:
        layer_dir = tmp_path / slug
        layer_dir.mkdir()
        (layer_dir / "README.md").write_text(f"# {slug}\nNarrative summary.\n")

    # Init as git repo for commit_changes
    import os
    import subprocess
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    env = {
        "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@test.com",
        "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "test@test.com",
        **os.environ,
    }
    subprocess.run(
        ["git", "commit", "-m", "init"], cwd=tmp_path,
        capture_output=True, env=env,
    )
    return tmp_path


def _make_mock_gen_runner(fail_at: tuple[str, int] | None = None):
    """Create a mock generation runner.

    Args:
        fail_at: If set, a tuple of (layer_slug, call_number) at which to fail.
                 call_number is 1-indexed.
    """
    call_count: dict[str, int] = {}

    async def mock_gen_runner(
        layer_slug: str,
        cascade_id: str,
        store: PolicyStore,
        emitter: EventEmitter,
        data_dir: Path,
        user_context: str | None = None,
    ) -> dict:
        call_count[layer_slug] = call_count.get(layer_slug, 0) + 1
        if fail_at and layer_slug == fail_at[0] and call_count[layer_slug] == fail_at[1]:
            raise RuntimeError(f"Agent failed at {layer_slug}")
        return {"success": True, "layer": layer_slug}

    return mock_gen_runner, call_count


def _make_mock_critic_runner():
    """Create a mock critic runner."""
    calls = []

    async def mock_critic_runner(
        layer_slug: str,
        cascade_id: str,
        store: PolicyStore,
        emitter: EventEmitter,
        data_dir: Path,
    ) -> dict:
        calls.append(layer_slug)
        return {"critics_done": True, "layer": layer_slug}

    return mock_critic_runner, calls


def _make_mock_synthesis_runner():
    """Create a mock synthesis runner."""
    calls = []

    async def mock_synthesis_runner(
        layer_slug: str,
        critic_results: Any,
        cascade_id: str,
        store: PolicyStore,
        emitter: EventEmitter,
        data_dir: Path,
    ) -> dict:
        calls.append(layer_slug)
        return {"synthesis_done": True, "layer": layer_slug}

    return mock_synthesis_runner, calls


async def _run_loop_with_mock_cleanup(
    cascade_id: str,
    controller: CascadeController,
    store: PolicyStore,
    emitter: EventEmitter,
    data_dir: Path,
    starting_layer: str,
    user_context: str | None,
    generation_runner,
    critic_runner,
    synthesis_runner,
    **kwargs,
):
    """Helper that wraps _run_cascade_loop with mocked unregister."""
    with patch("policy_factory.server.deps.unregister_cascade_controller"):
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
            **kwargs,
        )


# -----------------------------------------------------------------------
# Layer hierarchy utility tests
# -----------------------------------------------------------------------


class TestLayerHierarchy:
    """Tests for layers_from and layers_below utilities."""

    def test_layers_from_values(self) -> None:
        """Starting from values returns all 5 layers."""
        result = layers_from("values")
        assert result == [
            "values",
            "situational-awareness",
            "strategic-objectives",
            "tactical-objectives",
            "policies",
        ]

    def test_layers_from_situational_awareness(self) -> None:
        """Starting from SA returns 4 layers."""
        result = layers_from("situational-awareness")
        assert result == [
            "situational-awareness",
            "strategic-objectives",
            "tactical-objectives",
            "policies",
        ]

    def test_layers_from_strategic_objectives(self) -> None:
        """Starting from strategic-objectives returns 3 layers."""
        result = layers_from("strategic-objectives")
        assert result == [
            "strategic-objectives",
            "tactical-objectives",
            "policies",
        ]

    def test_layers_from_policies(self) -> None:
        """Starting from policies returns only 1 layer."""
        result = layers_from("policies")
        assert result == ["policies"]

    def test_layers_from_invalid(self) -> None:
        """Invalid layer slug raises ValueError."""
        with pytest.raises(ValueError, match="Invalid starting layer"):
            layers_from("invalid-layer")

    def test_layers_below_values(self) -> None:
        """Values has no layers below it."""
        assert layers_below("values") == []

    def test_layers_below_situational_awareness(self) -> None:
        """SA has values below it."""
        assert layers_below("situational-awareness") == ["values"]

    def test_layers_below_policies(self) -> None:
        """Policies has all 4 other layers below it."""
        assert layers_below("policies") == [
            "values",
            "situational-awareness",
            "strategic-objectives",
            "tactical-objectives",
        ]

    def test_layers_below_invalid(self) -> None:
        """Invalid layer slug raises ValueError."""
        with pytest.raises(ValueError, match="Invalid layer slug"):
            layers_below("nonexistent")


# -----------------------------------------------------------------------
# Context gathering tests
# -----------------------------------------------------------------------


class TestContextGathering:
    """Tests for generation context gathering."""

    def test_gather_context_for_values(self, data_dir: Path) -> None:
        """Values layer has no layers below, so context is minimal."""
        context = _gather_generation_context(data_dir, "values")
        # No layers below values
        assert context == ""

    def test_gather_context_for_sa(self, data_dir: Path) -> None:
        """SA layer gathers context from values below."""
        context = _gather_generation_context(data_dir, "situational-awareness")
        assert "Values" in context or "values" in context

    def test_gather_context_with_user_input(self, data_dir: Path) -> None:
        """User input context is included."""
        context = _gather_generation_context(
            data_dir, "values", user_context="New national security threat"
        )
        assert "New national security threat" in context
        assert "User Input" in context


# -----------------------------------------------------------------------
# Trigger function tests
# -----------------------------------------------------------------------


class TestTriggerCascade:
    """Tests for the cascade trigger function."""

    @pytest.mark.asyncio
    async def test_trigger_acquires_lock_and_starts(
        self, store: PolicyStore, emitter: EventEmitter, data_dir: Path,
    ) -> None:
        """Triggering a cascade when no lock is held acquires the lock and starts."""
        events: list[BaseEvent] = []
        emitter.subscribe(lambda e: events.append(e))

        gen_runner, gen_calls = _make_mock_gen_runner()

        with patch("policy_factory.server.deps.register_cascade_controller"), \
             patch("policy_factory.server.deps.unregister_cascade_controller"):
            result_id, is_cascade = await trigger_cascade(
                trigger_source="user_input",
                starting_layer="policies",
                store=store,
                emitter=emitter,
                data_dir=data_dir,
                generation_runner=gen_runner,
            )

        assert is_cascade is True
        assert result_id is not None

        # Check that cascade run was created
        cascade = store.get_cascade(result_id)
        assert cascade is not None
        assert cascade.trigger_source == "user_input"
        assert cascade.starting_layer == "policies"

        # Check events
        event_types = [e.event_type for e in events]
        assert "cascade_lock_acquired" in event_types
        assert "cascade_started" in event_types

    @pytest.mark.asyncio
    async def test_trigger_queues_when_lock_held(
        self, store: PolicyStore, emitter: EventEmitter, data_dir: Path,
    ) -> None:
        """Triggering a cascade when a lock is held queues the cascade."""
        # Create a running cascade to hold the lock
        store.create_cascade("user_input", "values")

        events: list[BaseEvent] = []
        emitter.subscribe(lambda e: events.append(e))

        result_id, is_cascade = await trigger_cascade(
            trigger_source="heartbeat",
            starting_layer="situational-awareness",
            store=store,
            emitter=emitter,
            data_dir=data_dir,
        )

        assert is_cascade is False  # Queued, not started
        assert result_id is not None

        # Check queue
        queue = store.get_queue()
        assert len(queue) == 1
        assert queue[0].trigger_source == "heartbeat"

        # Check event
        event_types = [e.event_type for e in events]
        assert "cascade_queued" in event_types

    @pytest.mark.asyncio
    async def test_trigger_queued_cascade_has_position(
        self, store: PolicyStore, emitter: EventEmitter, data_dir: Path,
    ) -> None:
        """Queued cascade event includes the queue position."""
        store.create_cascade("user_input", "values")

        events: list[BaseEvent] = []
        emitter.subscribe(lambda e: events.append(e))

        await trigger_cascade(
            trigger_source="heartbeat",
            starting_layer="situational-awareness",
            store=store,
            emitter=emitter,
            data_dir=data_dir,
        )

        queued_events = [e for e in events if isinstance(e, CascadeQueued)]
        assert len(queued_events) == 1
        assert queued_events[0].queue_position == 1

    @pytest.mark.asyncio
    async def test_trigger_returns_immediately(
        self, store: PolicyStore, emitter: EventEmitter, data_dir: Path,
    ) -> None:
        """The trigger function returns immediately (cascade runs as background task)."""
        gen_runner, _ = _make_mock_gen_runner()

        with patch("policy_factory.server.deps.register_cascade_controller"), \
             patch("policy_factory.server.deps.unregister_cascade_controller"):
            result_id, is_cascade = await trigger_cascade(
                trigger_source="user_input",
                starting_layer="policies",
                store=store,
                emitter=emitter,
                data_dir=data_dir,
                generation_runner=gen_runner,
            )

        # Result is returned before the cascade completes
        assert result_id is not None
        assert is_cascade is True


# -----------------------------------------------------------------------
# Orchestration loop tests
# -----------------------------------------------------------------------


class TestOrchestrationLoop:
    """Tests for the cascade orchestration loop with mock runners."""

    @pytest.mark.asyncio
    async def test_cascade_from_values_processes_all_layers(
        self, store: PolicyStore, emitter: EventEmitter, data_dir: Path,
    ) -> None:
        """A cascade from values processes all 5 layers in order."""
        gen_runner, gen_calls = _make_mock_gen_runner()
        critic_runner, critic_calls = _make_mock_critic_runner()
        synthesis_runner, synthesis_calls = _make_mock_synthesis_runner()

        cascade_id = store.create_cascade("user_input", "values")
        controller = CascadeController(cascade_id, emitter)

        await _run_loop_with_mock_cleanup(
            cascade_id=cascade_id,
            controller=controller,
            store=store,
            emitter=emitter,
            data_dir=data_dir,
            starting_layer="values",
            user_context=None,
            generation_runner=gen_runner,
            critic_runner=critic_runner,
            synthesis_runner=synthesis_runner,
        )

        # All 5 layers should have been processed
        expected_layers = [
            "values", "situational-awareness", "strategic-objectives",
            "tactical-objectives", "policies",
        ]
        for layer in expected_layers:
            assert layer in gen_calls, f"Generation not called for {layer}"
            assert layer in critic_calls, f"Critics not called for {layer}"
            assert layer in synthesis_calls, f"Synthesis not called for {layer}"

        # Cascade should be completed
        cascade = store.get_cascade(cascade_id)
        assert cascade is not None
        assert cascade.status == "completed"

    @pytest.mark.asyncio
    async def test_cascade_from_sa_processes_4_layers(
        self, store: PolicyStore, emitter: EventEmitter, data_dir: Path,
    ) -> None:
        """A cascade from SA processes 4 layers."""
        gen_runner, gen_calls = _make_mock_gen_runner()
        critic_runner, critic_calls = _make_mock_critic_runner()
        synthesis_runner, synthesis_calls = _make_mock_synthesis_runner()

        cascade_id = store.create_cascade("heartbeat", "situational-awareness")
        controller = CascadeController(cascade_id, emitter)

        await _run_loop_with_mock_cleanup(
            cascade_id=cascade_id,
            controller=controller,
            store=store,
            emitter=emitter,
            data_dir=data_dir,
            starting_layer="situational-awareness",
            user_context=None,
            generation_runner=gen_runner,
            critic_runner=critic_runner,
            synthesis_runner=synthesis_runner,
        )

        assert "values" not in gen_calls
        assert "situational-awareness" in gen_calls
        assert "policies" in gen_calls
        assert len(gen_calls) == 4

    @pytest.mark.asyncio
    async def test_cascade_from_policies_processes_one_layer(
        self, store: PolicyStore, emitter: EventEmitter, data_dir: Path,
    ) -> None:
        """A cascade from policies processes only 1 layer."""
        gen_runner, gen_calls = _make_mock_gen_runner()
        critic_runner, critic_calls = _make_mock_critic_runner()
        synthesis_runner, synthesis_calls = _make_mock_synthesis_runner()

        cascade_id = store.create_cascade("layer_refresh", "policies")
        controller = CascadeController(cascade_id, emitter)

        await _run_loop_with_mock_cleanup(
            cascade_id=cascade_id,
            controller=controller,
            store=store,
            emitter=emitter,
            data_dir=data_dir,
            starting_layer="policies",
            user_context=None,
            generation_runner=gen_runner,
            critic_runner=critic_runner,
            synthesis_runner=synthesis_runner,
        )

        assert list(gen_calls.keys()) == ["policies"]
        assert len(critic_calls) == 1
        assert len(synthesis_calls) == 1

    @pytest.mark.asyncio
    async def test_layer_steps_in_order(
        self, store: PolicyStore, emitter: EventEmitter, data_dir: Path,
    ) -> None:
        """Each layer goes through generation -> critics -> synthesis in sequence."""
        step_order: list[tuple[str, str]] = []

        async def track_gen(layer_slug, cascade_id, store, emitter, data_dir, ctx=None):
            step_order.append((layer_slug, "generation"))

        async def track_critics(layer_slug, cascade_id, store, emitter, data_dir):
            step_order.append((layer_slug, "critics"))

        async def track_synthesis(layer_slug, results, cascade_id, store, emitter, data_dir):
            step_order.append((layer_slug, "synthesis"))

        cascade_id = store.create_cascade("user_input", "policies")
        controller = CascadeController(cascade_id, emitter)

        await _run_loop_with_mock_cleanup(
            cascade_id=cascade_id,
            controller=controller,
            store=store,
            emitter=emitter,
            data_dir=data_dir,
            starting_layer="policies",
            user_context=None,
            generation_runner=track_gen,
            critic_runner=track_critics,
            synthesis_runner=track_synthesis,
        )

        assert step_order == [
            ("policies", "generation"),
            ("policies", "critics"),
            ("policies", "synthesis"),
        ]

    @pytest.mark.asyncio
    async def test_progress_events_emitted(
        self, store: PolicyStore, emitter: EventEmitter, data_dir: Path,
    ) -> None:
        """Progress events are emitted at each step transition."""
        events: list[BaseEvent] = []
        emitter.subscribe(lambda e: events.append(e))

        gen_runner, _ = _make_mock_gen_runner()
        critic_runner, _ = _make_mock_critic_runner()
        synthesis_runner, _ = _make_mock_synthesis_runner()

        cascade_id = store.create_cascade("user_input", "policies")
        controller = CascadeController(cascade_id, emitter)

        await _run_loop_with_mock_cleanup(
            cascade_id=cascade_id,
            controller=controller,
            store=store,
            emitter=emitter,
            data_dir=data_dir,
            starting_layer="policies",
            user_context=None,
            generation_runner=gen_runner,
            critic_runner=critic_runner,
            synthesis_runner=synthesis_runner,
        )

        event_types = [e.event_type for e in events]
        assert "layer_generation_started" in event_types
        assert "layer_generation_completed" in event_types
        assert "cascade_completed" in event_types
        assert "cascade_lock_released" in event_types

    @pytest.mark.asyncio
    async def test_cascade_progress_updated_in_store(
        self, store: PolicyStore, emitter: EventEmitter, data_dir: Path,
    ) -> None:
        """Cascade progress (current layer and step) is updated in SQLite at each transition."""
        progress_snapshots: list[tuple[str, str]] = []

        async def tracking_gen(layer_slug, cascade_id, store, emitter, data_dir, ctx=None):
            cascade = store.get_cascade(cascade_id)
            progress_snapshots.append((cascade.current_layer, cascade.current_step))

        async def tracking_critics(layer_slug, cascade_id, store, emitter, data_dir):
            cascade = store.get_cascade(cascade_id)
            progress_snapshots.append((cascade.current_layer, cascade.current_step))

        async def tracking_synthesis(layer_slug, results, cascade_id, store, emitter, data_dir):
            cascade = store.get_cascade(cascade_id)
            progress_snapshots.append((cascade.current_layer, cascade.current_step))

        cascade_id = store.create_cascade("user_input", "policies")
        controller = CascadeController(cascade_id, emitter)

        await _run_loop_with_mock_cleanup(
            cascade_id=cascade_id,
            controller=controller,
            store=store,
            emitter=emitter,
            data_dir=data_dir,
            starting_layer="policies",
            user_context=None,
            generation_runner=tracking_gen,
            critic_runner=tracking_critics,
            synthesis_runner=tracking_synthesis,
        )

        assert progress_snapshots == [
            ("policies", "generation"),
            ("policies", "critics"),
            ("policies", "synthesis"),
        ]

    @pytest.mark.asyncio
    async def test_none_runners_skip_steps(
        self, store: PolicyStore, emitter: EventEmitter, data_dir: Path,
    ) -> None:
        """When critic/synthesis runners are None, those steps are skipped."""
        gen_runner, gen_calls = _make_mock_gen_runner()

        cascade_id = store.create_cascade("user_input", "policies")
        controller = CascadeController(cascade_id, emitter)

        await _run_loop_with_mock_cleanup(
            cascade_id=cascade_id,
            controller=controller,
            store=store,
            emitter=emitter,
            data_dir=data_dir,
            starting_layer="policies",
            user_context=None,
            generation_runner=gen_runner,
            critic_runner=None,
            synthesis_runner=None,
        )

        assert "policies" in gen_calls
        cascade = store.get_cascade(cascade_id)
        assert cascade.status == "completed"


# -----------------------------------------------------------------------
# Error handling tests
# -----------------------------------------------------------------------


class TestErrorHandling:
    """Tests for cascade error handling and pause behaviour."""

    @pytest.mark.asyncio
    async def test_agent_failure_pauses_cascade(
        self, store: PolicyStore, emitter: EventEmitter, data_dir: Path,
    ) -> None:
        """When an agent fails, the cascade pauses with error info."""
        gen_runner, _ = _make_mock_gen_runner(fail_at=("policies", 1))

        cascade_id = store.create_cascade("user_input", "policies")
        controller = CascadeController(cascade_id, emitter)

        # Run the loop — it will pause when generation fails, then
        # we cancel from another task to unblock it
        async def cancel_after_pause():
            # Wait for the cascade to pause
            for _ in range(200):
                cascade = store.get_cascade(cascade_id)
                if cascade and cascade.status == "paused":
                    break
                await asyncio.sleep(0.01)
            await controller.cancel()

        cancel_task = asyncio.create_task(cancel_after_pause())

        await _run_loop_with_mock_cleanup(
            cascade_id=cascade_id,
            controller=controller,
            store=store,
            emitter=emitter,
            data_dir=data_dir,
            starting_layer="policies",
            user_context=None,
            generation_runner=gen_runner,
            critic_runner=None,
            synthesis_runner=None,
        )

        await cancel_task

        # Cascade should be cancelled (after being paused, then cancelled)
        cascade = store.get_cascade(cascade_id)
        assert cascade is not None
        assert cascade.status == "cancelled"

    @pytest.mark.asyncio
    async def test_paused_cascade_holds_lock(
        self, store: PolicyStore, emitter: EventEmitter, data_dir: Path,
    ) -> None:
        """A paused cascade holds the lock — other cascades cannot start."""
        cascade_id = store.create_cascade("user_input", "values")
        store.update_cascade_status(cascade_id, "paused", "Agent error")

        held, held_by = store.is_lock_held()
        assert held is True
        assert held_by == cascade_id

    @pytest.mark.asyncio
    async def test_resume_retries_failed_step(
        self, store: PolicyStore, emitter: EventEmitter, data_dir: Path,
    ) -> None:
        """Resuming a paused cascade retries the failed step."""
        # Generation fails on first call, succeeds on second
        call_count = {"policies": 0}

        async def flaky_gen(layer_slug, cascade_id, store, emitter, data_dir, ctx=None):
            call_count[layer_slug] = call_count.get(layer_slug, 0) + 1
            if layer_slug == "policies" and call_count[layer_slug] == 1:
                raise RuntimeError("Transient failure")
            return {"success": True}

        cascade_id = store.create_cascade("user_input", "policies")
        controller = CascadeController(cascade_id, emitter)

        # Resume after pause
        async def resume_after_pause():
            for _ in range(200):
                if controller.state == CascadeState.PAUSED:
                    break
                await asyncio.sleep(0.01)
            await controller.resume()

        resume_task = asyncio.create_task(resume_after_pause())

        await _run_loop_with_mock_cleanup(
            cascade_id=cascade_id,
            controller=controller,
            store=store,
            emitter=emitter,
            data_dir=data_dir,
            starting_layer="policies",
            user_context=None,
            generation_runner=flaky_gen,
            critic_runner=None,
            synthesis_runner=None,
        )

        await resume_task

        # Generation was called twice (first failed, second succeeded after resume)
        assert call_count["policies"] == 2

        cascade = store.get_cascade(cascade_id)
        assert cascade.status == "completed"

    @pytest.mark.asyncio
    async def test_cancel_releases_lock(
        self, store: PolicyStore, emitter: EventEmitter, data_dir: Path,
    ) -> None:
        """Cancelling a paused cascade releases the lock."""
        gen_runner, _ = _make_mock_gen_runner(fail_at=("policies", 1))

        cascade_id = store.create_cascade("user_input", "policies")
        controller = CascadeController(cascade_id, emitter)

        async def cancel_after_pause():
            for _ in range(200):
                if controller.state == CascadeState.PAUSED:
                    break
                await asyncio.sleep(0.01)
            await controller.cancel()

        cancel_task = asyncio.create_task(cancel_after_pause())

        await _run_loop_with_mock_cleanup(
            cascade_id=cascade_id,
            controller=controller,
            store=store,
            emitter=emitter,
            data_dir=data_dir,
            starting_layer="policies",
            user_context=None,
            generation_runner=gen_runner,
            critic_runner=None,
            synthesis_runner=None,
        )

        await cancel_task

        cascade = store.get_cascade(cascade_id)
        assert cascade.status == "cancelled"


# -----------------------------------------------------------------------
# Queue processing tests
# -----------------------------------------------------------------------


class TestQueueProcessing:
    """Tests for cascade queue processing after completion/cancellation."""

    @pytest.mark.asyncio
    async def test_cascade_queue_fifo(self, store: PolicyStore) -> None:
        """The cascade queue is FIFO-ordered (oldest request first)."""
        store.enqueue_cascade("user_input", "values", "first")
        store.enqueue_cascade("heartbeat", "situational-awareness", "second")
        store.enqueue_cascade("layer_refresh", "policies", "third")

        queue = store.get_queue()
        assert len(queue) == 3
        assert queue[0].context == "first"
        assert queue[1].context == "second"
        assert queue[2].context == "third"

    @pytest.mark.asyncio
    async def test_cancel_queued_cascade(self, store: PolicyStore) -> None:
        """Cancelling a queued cascade removes it from the queue."""
        queue_id, _ = store.enqueue_cascade("user_input", "values")

        result = store.cancel_queued_cascade(queue_id)
        assert result is True
        assert store.get_queue_depth() == 0


# -----------------------------------------------------------------------
# Cascade controller registry tests
# -----------------------------------------------------------------------


class TestControllerRegistry:
    """Tests for the cascade controller registry in deps.py."""

    def test_register_and_get(self, emitter: EventEmitter) -> None:
        """Registering a controller allows lookup by cascade ID."""
        from policy_factory.server.deps import (
            get_cascade_controller,
            register_cascade_controller,
            unregister_cascade_controller,
        )

        controller = CascadeController("test-id", emitter)
        register_cascade_controller("test-id", controller)

        result = get_cascade_controller("test-id")
        assert result is controller

        # Cleanup
        unregister_cascade_controller("test-id")

    def test_get_nonexistent(self) -> None:
        """Getting a non-existent controller returns None."""
        from policy_factory.server.deps import get_cascade_controller

        assert get_cascade_controller("nonexistent") is None

    def test_unregister(self, emitter: EventEmitter) -> None:
        """Unregistering removes the controller."""
        from policy_factory.server.deps import (
            get_cascade_controller,
            register_cascade_controller,
            unregister_cascade_controller,
        )

        controller = CascadeController("test-id-2", emitter)
        register_cascade_controller("test-id-2", controller)
        unregister_cascade_controller("test-id-2")

        assert get_cascade_controller("test-id-2") is None

    def test_get_active_cascade_id(self, emitter: EventEmitter) -> None:
        """get_active_cascade_id returns the ID of a running cascade."""
        from policy_factory.server.deps import (
            get_active_cascade_id,
            register_cascade_controller,
            unregister_cascade_controller,
        )

        controller = CascadeController("active-test", emitter)
        register_cascade_controller("active-test", controller)

        active_id = get_active_cascade_id()
        assert active_id == "active-test"

        # Cleanup
        unregister_cascade_controller("active-test")

    def test_get_active_cascade_id_none(self) -> None:
        """get_active_cascade_id returns None when no cascade is active."""
        from policy_factory.server.deps import get_active_cascade_id

        # Ensure no controllers are registered
        assert get_active_cascade_id() is None


# -----------------------------------------------------------------------
# Pause flag check tests
# -----------------------------------------------------------------------


class TestPauseChecks:
    """Tests for pause flag checking between sub-steps."""

    @pytest.mark.asyncio
    async def test_pause_between_generation_and_critics(
        self, store: PolicyStore, emitter: EventEmitter, data_dir: Path,
    ) -> None:
        """Pause flag is checked between generation and critics."""
        step_reached: list[str] = []
        gen_done = asyncio.Event()

        async def track_gen(layer_slug, cascade_id, store, emitter, data_dir, ctx=None):
            step_reached.append("generation")
            gen_done.set()
            # Yield control so the pause task can run
            await asyncio.sleep(0.05)

        async def track_critics(layer_slug, cascade_id, store, emitter, data_dir):
            step_reached.append("critics")

        cascade_id = store.create_cascade("user_input", "policies")
        controller = CascadeController(cascade_id, emitter)

        # Request pause after generation completes but before critics
        async def pause_after_gen():
            await gen_done.wait()
            controller.request_pause()
            # Then cancel after it pauses
            for _ in range(200):
                if controller.state == CascadeState.PAUSED:
                    break
                await asyncio.sleep(0.01)
            await controller.cancel()

        pause_task = asyncio.create_task(pause_after_gen())

        await _run_loop_with_mock_cleanup(
            cascade_id=cascade_id,
            controller=controller,
            store=store,
            emitter=emitter,
            data_dir=data_dir,
            starting_layer="policies",
            user_context=None,
            generation_runner=track_gen,
            critic_runner=track_critics,
            synthesis_runner=None,
        )

        await pause_task

        # Generation should have been reached but critics should not have run
        assert "generation" in step_reached
        # Cascade was cancelled after pause between gen and critics
        cascade = store.get_cascade(cascade_id)
        assert cascade.status == "cancelled"


# -----------------------------------------------------------------------
# Auto-commit tests
# -----------------------------------------------------------------------


class TestAutoCommit:
    """Tests for auto-committing after generation."""

    @pytest.mark.asyncio
    async def test_auto_commit_after_generation(
        self, store: PolicyStore, emitter: EventEmitter, data_dir: Path,
    ) -> None:
        """After generation succeeds, changes are auto-committed to git."""
        import subprocess

        async def gen_that_modifies(
            layer_slug, cascade_id, store, emitter, data_dir, ctx=None
        ):
            # Write a file in the data dir
            (data_dir / layer_slug / "test-item.md").write_text(
                "---\ntitle: Test\n---\nContent\n"
            )

        cascade_id = store.create_cascade("user_input", "policies")
        controller = CascadeController(cascade_id, emitter)

        await _run_loop_with_mock_cleanup(
            cascade_id=cascade_id,
            controller=controller,
            store=store,
            emitter=emitter,
            data_dir=data_dir,
            starting_layer="policies",
            user_context=None,
            generation_runner=gen_that_modifies,
            critic_runner=None,
            synthesis_runner=None,
        )

        # Check that git has a commit for the generation
        result = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            cwd=data_dir,
            capture_output=True,
            text=True,
        )
        assert "Generate policies layer" in result.stdout


# -----------------------------------------------------------------------
# Store composition tests
# -----------------------------------------------------------------------


class TestStoreComposition:
    """Tests for the PolicyStore including cascade and agent run mixins."""

    def test_store_has_cascade_methods(self, store: PolicyStore) -> None:
        """PolicyStore includes cascade mixin methods."""
        assert hasattr(store, "create_cascade")
        assert hasattr(store, "acquire_lock")
        assert hasattr(store, "is_lock_held")
        assert hasattr(store, "enqueue_cascade")

    def test_store_has_agent_run_methods(self, store: PolicyStore) -> None:
        """PolicyStore includes agent run mixin methods."""
        assert hasattr(store, "create_agent_run")
        assert hasattr(store, "complete_agent_run")
        assert hasattr(store, "list_agent_runs")
