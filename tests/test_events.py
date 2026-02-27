"""Tests for the event system — typed event dataclasses and EventEmitter."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from policy_factory.events import (
    AgentTextChunk,
    BaseEvent,
    CascadeCancelled,
    CascadeCompleted,
    CascadeFailed,
    CascadeLockAcquired,
    CascadeLockReleased,
    CascadePaused,
    CascadeQueued,
    CascadeResumed,
    CascadeStarted,
    CriticCompleted,
    CriticStarted,
    EventEmitter,
    HeartbeatCompleted,
    HeartbeatStarted,
    HeartbeatTierCompleted,
    IdeaEvaluationCompleted,
    IdeaEvaluationStarted,
    IdeaGenerationCompleted,
    IdeaGenerationStarted,
    IdeaSubmitted,
    LayerGenerationCompleted,
    LayerGenerationStarted,
    SynthesisCompleted,
    SynthesisStarted,
    UserCreated,
    UserLogin,
    get_event_category,
)

# ---------------------------------------------------------------------------
# Event dataclass tests
# ---------------------------------------------------------------------------


class TestBaseEvent:
    """Tests for BaseEvent and its shared behaviour."""

    def test_auto_generates_id(self) -> None:
        """Each event gets a unique UUID on creation."""
        e1 = CascadeStarted(cascade_id="c1")
        e2 = CascadeStarted(cascade_id="c1")
        assert e1.id != e2.id
        assert len(e1.id) == 36  # UUID format

    def test_auto_generates_timestamp(self) -> None:
        """Timestamp defaults to UTC now."""
        before = datetime.now(timezone.utc)
        e = CascadeStarted(cascade_id="c1")
        after = datetime.now(timezone.utc)
        assert before <= e.timestamp <= after

    def test_to_dict_has_required_fields(self) -> None:
        """to_dict includes id, event_type, timestamp."""
        e = CascadeStarted(cascade_id="c1")
        d = e.to_dict()
        assert "id" in d
        assert "event_type" in d
        assert "timestamp" in d

    def test_datetime_serialised_as_iso8601(self) -> None:
        """Timestamp is serialised to ISO 8601."""
        ts = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        e = CascadeStarted(cascade_id="c1", timestamp=ts)
        d = e.to_dict()
        assert d["timestamp"] == "2024-06-15T12:00:00+00:00"


class TestCascadeLifecycleEvents:
    """Tests for the 7 cascade lifecycle event types."""

    def test_cascade_started(self) -> None:
        e = CascadeStarted(
            cascade_id="c1",
            trigger_source="user_input",
            starting_layer="values",
        )
        assert e.event_type == "cascade_started"
        d = e.to_dict()
        assert d["cascade_id"] == "c1"
        assert d["trigger_source"] == "user_input"
        assert d["starting_layer"] == "values"

    def test_cascade_completed(self) -> None:
        e = CascadeCompleted(cascade_id="c1", success=True)
        assert e.event_type == "cascade_completed"
        d = e.to_dict()
        assert d["success"] is True

    def test_cascade_failed(self) -> None:
        e = CascadeFailed(
            cascade_id="c1",
            error="Agent timeout",
            failed_layer="strategic-objectives",
            failed_step="generation",
        )
        assert e.event_type == "cascade_failed"
        d = e.to_dict()
        assert d["error"] == "Agent timeout"
        assert d["failed_layer"] == "strategic-objectives"
        assert d["failed_step"] == "generation"

    def test_cascade_paused(self) -> None:
        e = CascadePaused(
            cascade_id="c1",
            error="API overloaded",
            paused_layer="values",
            paused_step="critics",
        )
        assert e.event_type == "cascade_paused"
        d = e.to_dict()
        assert d["paused_layer"] == "values"
        assert d["paused_step"] == "critics"

    def test_cascade_resumed(self) -> None:
        e = CascadeResumed(cascade_id="c1")
        assert e.event_type == "cascade_resumed"
        assert e.to_dict()["cascade_id"] == "c1"

    def test_cascade_cancelled(self) -> None:
        e = CascadeCancelled(cascade_id="c1")
        assert e.event_type == "cascade_cancelled"
        assert e.to_dict()["cascade_id"] == "c1"

    def test_cascade_queued(self) -> None:
        e = CascadeQueued(cascade_id="c1", queue_position=2)
        assert e.event_type == "cascade_queued"
        assert e.to_dict()["queue_position"] == 2


class TestLayerProcessingEvents:
    """Tests for the 6 layer processing event types."""

    def test_layer_generation_started(self) -> None:
        e = LayerGenerationStarted(cascade_id="c1", layer_slug="values")
        assert e.event_type == "layer_generation_started"
        d = e.to_dict()
        assert d["layer_slug"] == "values"

    def test_layer_generation_completed(self) -> None:
        e = LayerGenerationCompleted(cascade_id="c1", layer_slug="values")
        assert e.event_type == "layer_generation_completed"

    def test_critic_started(self) -> None:
        e = CriticStarted(
            cascade_id="c1",
            layer_slug="values",
            critic_archetype="realist",
        )
        assert e.event_type == "critic_started"
        assert e.to_dict()["critic_archetype"] == "realist"

    def test_critic_completed(self) -> None:
        e = CriticCompleted(
            cascade_id="c1",
            layer_slug="values",
            critic_archetype="liberal-institutionalist",
        )
        assert e.event_type == "critic_completed"

    def test_synthesis_started(self) -> None:
        e = SynthesisStarted(cascade_id="c1", layer_slug="values")
        assert e.event_type == "synthesis_started"

    def test_synthesis_completed(self) -> None:
        e = SynthesisCompleted(cascade_id="c1", layer_slug="values")
        assert e.event_type == "synthesis_completed"


class TestAgentStreamingEvents:
    """Tests for the agent text chunk event."""

    def test_agent_text_chunk(self) -> None:
        e = AgentTextChunk(
            cascade_id="c1",
            agent_label="Realist critic",
            text="Analyzing strategic objectives...",
        )
        assert e.event_type == "agent_text_chunk"
        d = e.to_dict()
        assert d["agent_label"] == "Realist critic"
        assert d["text"] == "Analyzing strategic objectives..."


class TestHeartbeatEvents:
    """Tests for the 3 heartbeat event types."""

    def test_heartbeat_started(self) -> None:
        e = HeartbeatStarted(heartbeat_run_id="hb1")
        assert e.event_type == "heartbeat_started"
        assert e.to_dict()["heartbeat_run_id"] == "hb1"

    def test_heartbeat_tier_completed(self) -> None:
        e = HeartbeatTierCompleted(
            heartbeat_run_id="hb1",
            tier=2,
            outcome="Flagged 3 items for triage",
            escalated=True,
        )
        assert e.event_type == "heartbeat_tier_completed"
        d = e.to_dict()
        assert d["tier"] == 2
        assert d["escalated"] is True

    def test_heartbeat_completed(self) -> None:
        e = HeartbeatCompleted(heartbeat_run_id="hb1", highest_tier=3)
        assert e.event_type == "heartbeat_completed"
        assert e.to_dict()["highest_tier"] == 3


class TestIdeaEvents:
    """Tests for the 5 idea event types."""

    def test_idea_submitted(self) -> None:
        e = IdeaSubmitted(idea_id="i1", source="human")
        assert e.event_type == "idea_submitted"
        d = e.to_dict()
        assert d["idea_id"] == "i1"
        assert d["source"] == "human"

    def test_idea_evaluation_started(self) -> None:
        e = IdeaEvaluationStarted(idea_id="i1")
        assert e.event_type == "idea_evaluation_started"

    def test_idea_evaluation_completed(self) -> None:
        e = IdeaEvaluationCompleted(idea_id="i1")
        assert e.event_type == "idea_evaluation_completed"

    def test_idea_generation_started(self) -> None:
        e = IdeaGenerationStarted()
        assert e.event_type == "idea_generation_started"

    def test_idea_generation_completed(self) -> None:
        e = IdeaGenerationCompleted(count=5)
        assert e.event_type == "idea_generation_completed"
        assert e.to_dict()["count"] == 5


class TestSystemEvents:
    """Tests for the 4 system event types."""

    def test_user_login(self) -> None:
        e = UserLogin(email="user@example.com")
        assert e.event_type == "user_login"
        assert e.to_dict()["email"] == "user@example.com"

    def test_user_created(self) -> None:
        e = UserCreated(email="new@example.com", role="admin")
        assert e.event_type == "user_created"
        d = e.to_dict()
        assert d["role"] == "admin"

    def test_cascade_lock_acquired(self) -> None:
        e = CascadeLockAcquired(cascade_id="c1")
        assert e.event_type == "cascade_lock_acquired"

    def test_cascade_lock_released(self) -> None:
        e = CascadeLockReleased(cascade_id="c1")
        assert e.event_type == "cascade_lock_released"


class TestEventCategoryMapping:
    """Tests for the event category lookup."""

    def test_cascade_events_map_to_cascade(self) -> None:
        assert get_event_category("cascade_started") == "cascade"
        assert get_event_category("layer_generation_started") == "cascade"
        assert get_event_category("critic_started") == "cascade"
        assert get_event_category("agent_text_chunk") == "cascade"

    def test_heartbeat_events_map_to_heartbeat(self) -> None:
        assert get_event_category("heartbeat_started") == "heartbeat"
        assert get_event_category("heartbeat_tier_completed") == "heartbeat"

    def test_idea_events_map_to_idea(self) -> None:
        assert get_event_category("idea_submitted") == "idea"

    def test_system_events_map_to_system(self) -> None:
        assert get_event_category("user_login") == "system"

    def test_unknown_event_returns_none(self) -> None:
        assert get_event_category("totally_unknown") is None


class TestEventTypeCounts:
    """Verify all 26 event types are defined."""

    def test_cascade_lifecycle_count(self) -> None:
        """7 cascade lifecycle event types."""
        types = [
            CascadeStarted,
            CascadeCompleted,
            CascadeFailed,
            CascadePaused,
            CascadeResumed,
            CascadeCancelled,
            CascadeQueued,
        ]
        assert len(types) == 7

    def test_layer_processing_count(self) -> None:
        """6 layer processing event types."""
        types = [
            LayerGenerationStarted,
            LayerGenerationCompleted,
            CriticStarted,
            CriticCompleted,
            SynthesisStarted,
            SynthesisCompleted,
        ]
        assert len(types) == 6

    def test_agent_streaming_count(self) -> None:
        """1 agent streaming event type."""
        assert AgentTextChunk(text="x").event_type == "agent_text_chunk"

    def test_heartbeat_count(self) -> None:
        """3 heartbeat event types."""
        types = [HeartbeatStarted, HeartbeatTierCompleted, HeartbeatCompleted]
        assert len(types) == 3

    def test_idea_count(self) -> None:
        """5 idea event types."""
        types = [
            IdeaSubmitted,
            IdeaEvaluationStarted,
            IdeaEvaluationCompleted,
            IdeaGenerationStarted,
            IdeaGenerationCompleted,
        ]
        assert len(types) == 5

    def test_system_count(self) -> None:
        """4 system event types."""
        types = [UserLogin, UserCreated, CascadeLockAcquired, CascadeLockReleased]
        assert len(types) == 4


# ---------------------------------------------------------------------------
# EventEmitter tests
# ---------------------------------------------------------------------------


class TestEventEmitter:
    """Tests for the async EventEmitter."""

    @pytest.mark.asyncio
    async def test_subscribe_and_emit(self) -> None:
        """Subscribing a handler makes it receive emitted events."""
        received: list[BaseEvent] = []
        emitter = EventEmitter()
        emitter.subscribe(lambda e: received.append(e))

        event = CascadeStarted(cascade_id="c1")
        await emitter.emit(event)

        assert len(received) == 1
        assert received[0] is event

    @pytest.mark.asyncio
    async def test_multiple_handlers(self) -> None:
        """Multiple handlers all receive the same event."""
        received_a: list[BaseEvent] = []
        received_b: list[BaseEvent] = []
        emitter = EventEmitter()
        emitter.subscribe(lambda e: received_a.append(e))
        emitter.subscribe(lambda e: received_b.append(e))

        event = CascadeStarted(cascade_id="c1")
        await emitter.emit(event)

        assert len(received_a) == 1
        assert len(received_b) == 1

    @pytest.mark.asyncio
    async def test_unsubscribe(self) -> None:
        """Unsubscribing prevents the handler from receiving events."""
        received: list[BaseEvent] = []
        handler = lambda e: received.append(e)  # noqa: E731
        emitter = EventEmitter()
        emitter.subscribe(handler)

        await emitter.emit(CascadeStarted(cascade_id="c1"))
        assert len(received) == 1

        emitter.unsubscribe(handler)
        await emitter.emit(CascadeStarted(cascade_id="c2"))
        assert len(received) == 1  # No new event received

    @pytest.mark.asyncio
    async def test_unsubscribe_nonexistent_handler_noop(self) -> None:
        """Unsubscribing a handler that was never subscribed is a no-op."""
        emitter = EventEmitter()
        emitter.unsubscribe(lambda e: None)  # Should not raise

    @pytest.mark.asyncio
    async def test_async_handler(self) -> None:
        """Async handlers are properly awaited."""
        received: list[BaseEvent] = []

        async def async_handler(event: BaseEvent) -> None:
            await asyncio.sleep(0)  # Simulate async work
            received.append(event)

        emitter = EventEmitter()
        emitter.subscribe(async_handler)

        await emitter.emit(CascadeStarted(cascade_id="c1"))
        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_failing_handler_does_not_stop_others(self) -> None:
        """A handler that raises does not prevent other handlers from running."""
        received: list[BaseEvent] = []

        def failing_handler(event: BaseEvent) -> None:
            raise ValueError("Handler failed!")

        emitter = EventEmitter()
        emitter.subscribe(failing_handler)
        emitter.subscribe(lambda e: received.append(e))

        await emitter.emit(CascadeStarted(cascade_id="c1"))
        assert len(received) == 1  # Second handler still ran

    @pytest.mark.asyncio
    async def test_failing_async_handler_does_not_stop_others(self) -> None:
        """An async handler that raises does not stop other handlers."""
        received: list[BaseEvent] = []

        async def failing_handler(event: BaseEvent) -> None:
            raise RuntimeError("Async handler failed!")

        emitter = EventEmitter()
        emitter.subscribe(failing_handler)
        emitter.subscribe(lambda e: received.append(e))

        await emitter.emit(CascadeStarted(cascade_id="c1"))
        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_emit_to_zero_handlers(self) -> None:
        """Emitting with no subscribers doesn't error."""
        emitter = EventEmitter()
        await emitter.emit(CascadeStarted(cascade_id="c1"))  # Should not raise
