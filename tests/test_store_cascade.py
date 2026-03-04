"""Tests for the CascadeStoreMixin and AgentRunStoreMixin."""

from datetime import datetime

import pytest

from policy_factory.store import PolicyStore

# -----------------------------------------------------------------------
# CascadeStoreMixin tests
# -----------------------------------------------------------------------


class TestCascadeRunCRUD:
    """Tests for cascade run CRUD operations."""

    def test_create_cascade(self, store: PolicyStore) -> None:
        """Creating a cascade stores trigger source, starting layer, and sets status to running."""
        cascade_id = store.create_cascade("user_input", "values", "test context")
        cascade = store.get_cascade(cascade_id)

        assert cascade is not None
        assert cascade.id == cascade_id
        assert cascade.trigger_source == "user_input"
        assert cascade.starting_layer == "values"
        assert cascade.current_layer == "values"
        assert cascade.current_step == "generation"
        assert cascade.status == "running"
        assert cascade.context == "test context"
        assert cascade.error_message is None
        assert cascade.error_layer is None
        assert cascade.completed_at is None
        assert isinstance(cascade.created_at, datetime)

    def test_create_cascade_without_context(self, store: PolicyStore) -> None:
        """Creating a cascade without context works."""
        cascade_id = store.create_cascade("layer_refresh", "situational-awareness")
        cascade = store.get_cascade(cascade_id)

        assert cascade is not None
        assert cascade.context is None

    def test_get_cascade_not_found(self, store: PolicyStore) -> None:
        """Getting a non-existent cascade returns None."""
        assert store.get_cascade("nonexistent") is None

    def test_update_cascade_progress(self, store: PolicyStore) -> None:
        """Updating cascade progress changes the current layer and step."""
        cascade_id = store.create_cascade("user_input", "values")
        store.update_cascade_progress(cascade_id, "situational-awareness", "critics")

        cascade = store.get_cascade(cascade_id)
        assert cascade is not None
        assert cascade.current_layer == "situational-awareness"
        assert cascade.current_step == "critics"

    def test_update_cascade_status_completed(self, store: PolicyStore) -> None:
        """Completing a cascade sets status and completed_at."""
        cascade_id = store.create_cascade("user_input", "values")
        store.update_cascade_status(cascade_id, "completed")

        cascade = store.get_cascade(cascade_id)
        assert cascade is not None
        assert cascade.status == "completed"
        assert cascade.completed_at is not None

    def test_update_cascade_status_paused_with_error(self, store: PolicyStore) -> None:
        """Pausing a cascade records error message and layer."""
        cascade_id = store.create_cascade("user_input", "values")
        store.update_cascade_status(
            cascade_id, "paused", "Agent failed", "strategic-objectives"
        )

        cascade = store.get_cascade(cascade_id)
        assert cascade is not None
        assert cascade.status == "paused"
        assert cascade.error_message == "Agent failed"
        assert cascade.error_layer == "strategic-objectives"
        assert cascade.completed_at is None  # Paused doesn't set completed_at

    def test_update_cascade_status_failed(self, store: PolicyStore) -> None:
        """Failing a cascade sets completed_at."""
        cascade_id = store.create_cascade("user_input", "values")
        store.update_cascade_status(cascade_id, "failed", "Fatal error", "policies")

        cascade = store.get_cascade(cascade_id)
        assert cascade is not None
        assert cascade.status == "failed"
        assert cascade.completed_at is not None

    def test_update_cascade_status_cancelled(self, store: PolicyStore) -> None:
        """Cancelling a cascade sets completed_at."""
        cascade_id = store.create_cascade("user_input", "values")
        store.update_cascade_status(cascade_id, "cancelled")

        cascade = store.get_cascade(cascade_id)
        assert cascade is not None
        assert cascade.status == "cancelled"
        assert cascade.completed_at is not None

    def test_list_cascades(self, store: PolicyStore) -> None:
        """Listing cascades returns records in reverse chronological order."""
        id1 = store.create_cascade("user_input", "values")
        store.update_cascade_status(id1, "completed")

        id2 = store.create_cascade("heartbeat", "situational-awareness")
        store.update_cascade_status(id2, "completed")

        id3 = store.create_cascade("layer_refresh", "policies")

        cascades = store.list_cascades()
        assert len(cascades) == 3
        assert cascades[0].id == id3  # Most recent first
        assert cascades[2].id == id1  # Oldest last

    def test_list_cascades_with_limit(self, store: PolicyStore) -> None:
        """Listing cascades respects limit."""
        for i in range(5):
            cid = store.create_cascade("user_input", "values")
            store.update_cascade_status(cid, "completed")

        cascades = store.list_cascades(limit=2)
        assert len(cascades) == 2

    def test_list_cascades_with_offset(self, store: PolicyStore) -> None:
        """Listing cascades respects offset."""
        ids = []
        for i in range(5):
            cid = store.create_cascade("user_input", "values")
            store.update_cascade_status(cid, "completed")
            ids.append(cid)

        cascades = store.list_cascades(limit=2, offset=2)
        assert len(cascades) == 2


class TestCascadeLock:
    """Tests for the cascade lock management."""

    def test_lock_not_held_initially(self, store: PolicyStore) -> None:
        """The lock is not held when no cascades are running."""
        held, cascade_id = store.is_lock_held()
        assert held is False
        assert cascade_id is None

    def test_acquire_lock_success(self, store: PolicyStore) -> None:
        """Acquiring the lock succeeds when no lock is held."""
        cascade_id = store.create_cascade("user_input", "values")
        assert store.acquire_lock(cascade_id) is True

    def test_acquire_lock_fails_when_held(self, store: PolicyStore) -> None:
        """Acquiring the lock fails when another cascade is running."""
        id1 = store.create_cascade("user_input", "values")
        # id1 is now running — lock is held

        id2 = store.create_cascade("heartbeat", "situational-awareness")
        # Before acquire_lock, we need to set id2 back to non-running
        # Actually, create_cascade sets status to "running", so now both are running
        # Let's cancel id2 first and try properly
        store.update_cascade_status(id2, "cancelled")
        id2 = store.create_cascade("heartbeat", "situational-awareness")
        store.update_cascade_status(id2, "cancelled")

        # id1 is still running
        held, held_by = store.is_lock_held()
        assert held is True
        assert held_by == id1

    def test_lock_held_by_running_cascade(self, store: PolicyStore) -> None:
        """A running cascade holds the lock."""
        cascade_id = store.create_cascade("user_input", "values")

        held, held_by = store.is_lock_held()
        assert held is True
        assert held_by == cascade_id

    def test_lock_held_by_paused_cascade(self, store: PolicyStore) -> None:
        """A paused cascade holds the lock."""
        cascade_id = store.create_cascade("user_input", "values")
        store.update_cascade_status(cascade_id, "paused", "Agent error")

        held, held_by = store.is_lock_held()
        assert held is True
        assert held_by == cascade_id

    def test_lock_released_after_completion(self, store: PolicyStore) -> None:
        """Completing a cascade releases the lock."""
        cascade_id = store.create_cascade("user_input", "values")
        store.update_cascade_status(cascade_id, "completed")

        held, held_by = store.is_lock_held()
        assert held is False
        assert held_by is None

    def test_lock_released_after_cancel(self, store: PolicyStore) -> None:
        """Cancelling a cascade releases the lock."""
        cascade_id = store.create_cascade("user_input", "values")
        store.update_cascade_status(cascade_id, "cancelled")

        held, held_by = store.is_lock_held()
        assert held is False

    def test_lock_released_after_failure(self, store: PolicyStore) -> None:
        """Failing a cascade releases the lock."""
        cascade_id = store.create_cascade("user_input", "values")
        store.update_cascade_status(cascade_id, "failed", "error")

        held, held_by = store.is_lock_held()
        assert held is False

    def test_get_active_cascade(self, store: PolicyStore) -> None:
        """get_active_cascade returns the running cascade."""
        cascade_id = store.create_cascade("user_input", "values")

        active = store.get_active_cascade()
        assert active is not None
        assert active.id == cascade_id

    def test_get_active_cascade_none(self, store: PolicyStore) -> None:
        """get_active_cascade returns None when no cascade is running."""
        assert store.get_active_cascade() is None

    def test_get_active_cascade_paused(self, store: PolicyStore) -> None:
        """get_active_cascade returns a paused cascade."""
        cascade_id = store.create_cascade("user_input", "values")
        store.update_cascade_status(cascade_id, "paused")

        active = store.get_active_cascade()
        assert active is not None
        assert active.id == cascade_id


class TestCascadeQueue:
    """Tests for the cascade queue management."""

    def test_enqueue_cascade(self, store: PolicyStore) -> None:
        """Enqueueing a cascade creates a queue entry."""
        queue_id, position = store.enqueue_cascade("user_input", "values", "test")

        assert queue_id is not None
        assert position == 1

    def test_enqueue_multiple(self, store: PolicyStore) -> None:
        """Enqueueing multiple cascades returns correct positions."""
        _, pos1 = store.enqueue_cascade("user_input", "values")
        _, pos2 = store.enqueue_cascade("heartbeat", "situational-awareness")
        _, pos3 = store.enqueue_cascade("layer_refresh", "policies")

        assert pos1 == 1
        assert pos2 == 2
        assert pos3 == 3

    def test_dequeue_cascade_fifo(self, store: PolicyStore) -> None:
        """Dequeue returns entries in FIFO order."""
        store.enqueue_cascade("user_input", "values", "first")
        store.enqueue_cascade("heartbeat", "situational-awareness", "second")

        entry1 = store.dequeue_cascade()
        assert entry1 is not None
        assert entry1.trigger_source == "user_input"
        assert entry1.starting_layer == "values"
        assert entry1.context == "first"

        entry2 = store.dequeue_cascade()
        assert entry2 is not None
        assert entry2.trigger_source == "heartbeat"
        assert entry2.context == "second"

    def test_dequeue_empty_queue(self, store: PolicyStore) -> None:
        """Dequeue returns None on empty queue."""
        assert store.dequeue_cascade() is None

    def test_get_queue(self, store: PolicyStore) -> None:
        """get_queue returns all entries in FIFO order."""
        store.enqueue_cascade("user_input", "values")
        store.enqueue_cascade("heartbeat", "situational-awareness")

        queue = store.get_queue()
        assert len(queue) == 2
        assert queue[0].trigger_source == "user_input"
        assert queue[1].trigger_source == "heartbeat"

    def test_get_queue_empty(self, store: PolicyStore) -> None:
        """get_queue returns empty list when queue is empty."""
        assert store.get_queue() == []

    def test_cancel_queued_cascade(self, store: PolicyStore) -> None:
        """Cancelling a queued cascade removes it from the queue."""
        queue_id, _ = store.enqueue_cascade("user_input", "values")

        result = store.cancel_queued_cascade(queue_id)
        assert result is True
        assert store.get_queue_depth() == 0

    def test_cancel_nonexistent_queued_cascade(self, store: PolicyStore) -> None:
        """Cancelling a non-existent queue entry returns False."""
        result = store.cancel_queued_cascade("nonexistent")
        assert result is False

    def test_get_queue_depth(self, store: PolicyStore) -> None:
        """get_queue_depth returns the correct count."""
        assert store.get_queue_depth() == 0

        store.enqueue_cascade("user_input", "values")
        assert store.get_queue_depth() == 1

        store.enqueue_cascade("heartbeat", "situational-awareness")
        assert store.get_queue_depth() == 2

        store.dequeue_cascade()
        assert store.get_queue_depth() == 1


# -----------------------------------------------------------------------
# AgentRunStoreMixin tests
# -----------------------------------------------------------------------


class TestAgentRunCRUD:
    """Tests for agent run CRUD operations."""

    def test_create_agent_run(self, store: PolicyStore) -> None:
        """Creating an agent run stores all fields correctly."""
        run_id = store.create_agent_run(
            cascade_id="cascade-123",
            agent_type="generator",
            agent_label="Values layer generator",
            model="claude-opus-4-0-20250514",
            target_layer="values",
        )

        run = store.get_agent_run(run_id)
        assert run is not None
        assert run.id == run_id
        assert run.cascade_id == "cascade-123"
        assert run.agent_type == "generator"
        assert run.agent_label == "Values layer generator"
        assert run.model == "claude-opus-4-0-20250514"
        assert run.target_layer == "values"
        assert isinstance(run.started_at, datetime)
        assert run.completed_at is None
        assert run.success is None
        assert run.error_message is None
        assert run.cost_usd is None
        assert run.output_text is None

    def test_create_agent_run_without_cascade(self, store: PolicyStore) -> None:
        """Creating an agent run without a cascade ID works."""
        run_id = store.create_agent_run(
            cascade_id=None,
            agent_type="idea-evaluator",
            agent_label="Idea evaluator",
            model="claude-sonnet-4-20250514",
        )

        run = store.get_agent_run(run_id)
        assert run is not None
        assert run.cascade_id is None
        assert run.target_layer is None

    def test_complete_agent_run_success(self, store: PolicyStore) -> None:
        """Completing an agent run with success records all data."""
        run_id = store.create_agent_run(
            cascade_id="cascade-123",
            agent_type="generator",
            agent_label="Values generator",
            model="claude-opus-4-0-20250514",
            target_layer="values",
        )

        store.complete_agent_run(
            run_id,
            success=True,
            cost=0.05,
            output_text="10. I reflect on my biases...\nAnalysis here.",
        )

        run = store.get_agent_run(run_id)
        assert run is not None
        assert run.success is True
        assert run.completed_at is not None
        assert run.cost_usd == pytest.approx(0.05)
        assert run.output_text == "10. I reflect on my biases...\nAnalysis here."
        assert run.error_message is None

    def test_complete_agent_run_failure(self, store: PolicyStore) -> None:
        """Completing an agent run with failure records error message."""
        run_id = store.create_agent_run(
            cascade_id="cascade-123",
            agent_type="critic",
            agent_label="Realist critic",
            model="claude-sonnet-4-20250514",
            target_layer="values",
        )

        store.complete_agent_run(
            run_id,
            success=False,
            error_message="API error 503",
        )

        run = store.get_agent_run(run_id)
        assert run is not None
        assert run.success is False
        assert run.error_message == "API error 503"
        assert run.completed_at is not None

    def test_get_agent_run_not_found(self, store: PolicyStore) -> None:
        """Getting a non-existent agent run returns None."""
        assert store.get_agent_run("nonexistent") is None

    def test_list_agent_runs_all(self, store: PolicyStore) -> None:
        """Listing all agent runs returns them in reverse chronological order."""
        id1 = store.create_agent_run(
            cascade_id="c1", agent_type="generator",
            agent_label="Gen 1", model="opus",
        )
        id2 = store.create_agent_run(
            cascade_id="c1", agent_type="critic",
            agent_label="Critic 1", model="sonnet",
        )

        runs = store.list_agent_runs()
        assert len(runs) == 2
        # Most recent first
        assert runs[0].id == id2
        assert runs[1].id == id1

    def test_list_agent_runs_by_cascade(self, store: PolicyStore) -> None:
        """Listing agent runs filtered by cascade ID."""
        store.create_agent_run(
            cascade_id="c1", agent_type="generator",
            agent_label="Gen", model="opus",
        )
        store.create_agent_run(
            cascade_id="c2", agent_type="generator",
            agent_label="Gen", model="opus",
        )

        runs = store.list_agent_runs(cascade_id="c1")
        assert len(runs) == 1
        assert runs[0].cascade_id == "c1"

    def test_list_agent_runs_by_type(self, store: PolicyStore) -> None:
        """Listing agent runs filtered by agent type."""
        store.create_agent_run(
            cascade_id="c1", agent_type="generator",
            agent_label="Gen", model="opus",
        )
        store.create_agent_run(
            cascade_id="c1", agent_type="critic",
            agent_label="Critic", model="sonnet",
        )

        runs = store.list_agent_runs(agent_type="critic")
        assert len(runs) == 1
        assert runs[0].agent_type == "critic"

    def test_list_agent_runs_by_layer(self, store: PolicyStore) -> None:
        """Listing agent runs filtered by target layer."""
        store.create_agent_run(
            cascade_id="c1", agent_type="generator",
            agent_label="Gen", model="opus", target_layer="values",
        )
        store.create_agent_run(
            cascade_id="c1", agent_type="generator",
            agent_label="Gen", model="opus", target_layer="policies",
        )

        runs = store.list_agent_runs(target_layer="values")
        assert len(runs) == 1
        assert runs[0].target_layer == "values"

    def test_list_agent_runs_with_limit(self, store: PolicyStore) -> None:
        """Listing agent runs respects limit."""
        for i in range(5):
            store.create_agent_run(
                cascade_id="c1", agent_type="generator",
                agent_label=f"Gen {i}", model="opus",
            )

        runs = store.list_agent_runs(limit=2)
        assert len(runs) == 2

    def test_agent_run_includes_full_output(self, store: PolicyStore) -> None:
        """Agent run records include the full unfiltered output text."""
        run_id = store.create_agent_run(
            cascade_id="c1", agent_type="generator",
            agent_label="Gen", model="opus", target_layer="values",
        )
        full_output = "10. I acknowledge my potential bias...\n1. Done.\n\nActual analysis here."
        store.complete_agent_run(
            run_id, success=True, output_text=full_output,
        )

        run = store.get_agent_run(run_id)
        assert run is not None
        assert run.output_text == full_output

    def test_create_agent_run_with_none_model(self, store: PolicyStore) -> None:
        """Creating an agent run with model=None succeeds (CLI-default roles)."""
        run_id = store.create_agent_run(
            cascade_id=None,
            agent_type="strategic-seed",
            agent_label="Strategic objectives seed",
            model=None,
            target_layer="strategic-objectives",
        )

        run = store.get_agent_run(run_id)
        assert run is not None
        assert run.id == run_id
        assert run.agent_type == "strategic-seed"
        assert run.model is None
        assert run.target_layer == "strategic-objectives"

    def test_agent_run_with_none_model_round_trips(self, store: PolicyStore) -> None:
        """An agent run created with model=None can be retrieved with model=None."""
        run_id = store.create_agent_run(
            cascade_id=None,
            agent_type="tactical-seed",
            agent_label="Tactical objectives seed",
            model=None,
        )
        store.complete_agent_run(run_id, success=True, cost=0.10)

        run = store.get_agent_run(run_id)
        assert run is not None
        assert run.model is None
        assert run.success is True
        assert run.cost_usd == pytest.approx(0.10)

    def test_agent_run_with_string_model_still_works(self, store: PolicyStore) -> None:
        """Existing agent runs with string model values still work after the type change."""
        run_id = store.create_agent_run(
            cascade_id="c1",
            agent_type="generator",
            agent_label="Generator",
            model="claude-opus-4-0-20250514",
            target_layer="values",
        )

        run = store.get_agent_run(run_id)
        assert run is not None
        assert run.model == "claude-opus-4-0-20250514"


class TestSchemaInitialization:
    """Tests for schema initialization of cascade and agent run tables."""

    def test_cascade_tables_created(self, store: PolicyStore) -> None:
        """Cascade runs and queue tables exist after store initialization."""
        # This should not raise
        store.conn.execute("SELECT * FROM cascade_runs LIMIT 1")
        store.conn.execute("SELECT * FROM cascade_queue LIMIT 1")
        store.conn.execute("SELECT * FROM agent_runs LIMIT 1")

    def test_schema_idempotent(self, tmp_db_path) -> None:
        """Creating a store twice with the same db doesn't error."""
        store1 = PolicyStore(tmp_db_path)
        store2 = PolicyStore(tmp_db_path)
        # Both should work
        store1.create_cascade("user_input", "values")
        cascades = store2.list_cascades()
        assert len(cascades) >= 1
