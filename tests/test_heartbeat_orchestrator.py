"""Tests for the heartbeat orchestrator — four-tier escalation chain.

All agent sessions are mocked; these tests verify the orchestration logic:
tier escalation, event emission, store recording, error handling.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from policy_factory.events import EventEmitter
from policy_factory.store import PolicyStore


@dataclass
class MockAgentResult:
    """Mock result matching AgentResult interface."""

    is_error: bool = False
    result_text: str = ""
    total_cost_usd: float | None = 0.01
    num_turns: int | None = 1
    full_output: str = ""
    session_id: str | None = None


# ---------------------------------------------------------------------------
# Mock helper for agent sessions
# ---------------------------------------------------------------------------


def create_mock_agent_patches(mock_run_fn):
    """Create a patch for AgentSession that mocks the entire agent execution flow.

    Args:
        mock_run_fn: Async function to use for AgentSession.run()

    Returns:
        A single patch context manager for AgentSession.
    """
    mock_session = MagicMock()
    mock_session.run = AsyncMock(side_effect=mock_run_fn)

    return patch("policy_factory.agent.session.AgentSession", return_value=mock_session)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """Create a minimal data directory structure for testing."""
    sa_dir = tmp_path / "situational-awareness"
    sa_dir.mkdir()
    (sa_dir / "README.md").write_text(
        "# Situational Awareness\nCurrent geopolitical situation summary.",
        encoding="utf-8",
    )
    # Create values directory so layer validation works
    values_dir = tmp_path / "values"
    values_dir.mkdir()
    (values_dir / "README.md").write_text("# Values", encoding="utf-8")
    # Other layer dirs
    for slug in ("strategic-objectives", "tactical-objectives", "policies"):
        d = tmp_path / slug
        d.mkdir()
        (d / "README.md").write_text(f"# {slug}", encoding="utf-8")
    return tmp_path


@pytest.fixture
def emitter() -> EventEmitter:
    """Create an EventEmitter for testing."""
    return EventEmitter()


# ---------------------------------------------------------------------------
# Helper to track emitted events
# ---------------------------------------------------------------------------


class EventCollector:
    """Subscribes to an emitter and collects all events."""

    def __init__(self, emitter: EventEmitter) -> None:
        self.events: list = []
        emitter.subscribe(self._handle)

    async def _handle(self, event) -> None:
        self.events.append(event)

    def of_type(self, event_type: str) -> list:
        return [e for e in self.events if e.event_type == event_type]


# ---------------------------------------------------------------------------
# Tier 1 tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tier1_nothing_noteworthy_stops(
    store: PolicyStore, emitter: EventEmitter, data_dir: Path
) -> None:
    """Tier 1 returning NOTHING_NOTEWORTHY stops the heartbeat at Tier 1."""
    collector = EventCollector(emitter)

    async def mock_run(prompt):
        return MockAgentResult(
            full_output="STATUS: NOTHING_NOTEWORTHY\nNo significant developments found.",
        )

    p = create_mock_agent_patches(mock_run)
    with p:
        from policy_factory.heartbeat.orchestrator import run_heartbeat

        run_id = await run_heartbeat(
            trigger="manual",
            store=store,
            emitter=emitter,
            data_dir=data_dir,
        )

    # Verify heartbeat run
    run = store.get_heartbeat_run(run_id)
    assert run is not None
    assert run.highest_tier == 1
    assert run.completed_at is not None
    assert len(run.structured_log) == 1
    assert run.structured_log[0].escalated is False

    # Verify events
    assert len(collector.of_type("heartbeat_started")) == 1
    assert len(collector.of_type("heartbeat_tier_completed")) == 1
    assert len(collector.of_type("heartbeat_completed")) == 1

    completed_event = collector.of_type("heartbeat_completed")[0]
    assert completed_event.highest_tier == 1


@pytest.mark.asyncio
async def test_tier1_flags_items_escalates_to_tier2(
    store: PolicyStore, emitter: EventEmitter, data_dir: Path
) -> None:
    """Tier 1 flagging items escalates to Tier 2."""
    collector = EventCollector(emitter)

    call_count = 0

    async def mock_run(prompt):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # Tier 1: flagged items
            return MockAgentResult(
                full_output=(
                    "STATUS: FLAGGED\nITEMS:\n"
                    "- EU AI Act enforcement begins\n"
                    "- Finland cyber report"
                ),
            )
        # Tier 2: no updates
        return MockAgentResult(
            full_output="STATUS: NO_UPDATE_NEEDED\nAnalysis complete.",
        )

    p = create_mock_agent_patches(mock_run)
    with p:
        from policy_factory.heartbeat.orchestrator import run_heartbeat

        run_id = await run_heartbeat(
            trigger="scheduled",
            store=store,
            emitter=emitter,
            data_dir=data_dir,
        )

    # Verify
    run = store.get_heartbeat_run(run_id)
    assert run is not None
    assert run.highest_tier == 2
    assert run.completed_at is not None
    assert len(run.structured_log) == 2
    assert run.structured_log[0].tier == 1
    assert run.structured_log[0].escalated is True
    assert run.structured_log[1].tier == 2
    assert run.structured_log[1].escalated is False

    # Should have 2 tier completed events
    assert len(collector.of_type("heartbeat_tier_completed")) == 2


@pytest.mark.asyncio
async def test_full_escalation_through_all_tiers(
    store: PolicyStore, emitter: EventEmitter, data_dir: Path
) -> None:
    """Full escalation: Tier 1 → 2 → 3 → 4."""
    collector = EventCollector(emitter)

    outputs = [
        # Tier 1: flagged
        "STATUS: FLAGGED\nITEMS:\n- Major item",
        # Tier 2: update recommended
        "STATUS: UPDATE_RECOMMENDED\nITEMS:\n- Update needed",
        # Tier 3: SA update (always escalates on success)
        "Updated SA files successfully",
    ]
    call_count = 0

    async def mock_run(prompt):
        nonlocal call_count
        result = MockAgentResult(full_output=outputs[call_count])
        call_count += 1
        return result

    mock_cascade = AsyncMock(return_value=("cascade-123", True))
    mock_idea_gen = AsyncMock(return_value=["idea-1"])

    p = create_mock_agent_patches(mock_run)
    with p, patch("policy_factory.data.git.commit_changes"):
        from policy_factory.heartbeat.orchestrator import run_heartbeat

        run_id = await run_heartbeat(
            trigger="scheduled",
            store=store,
            emitter=emitter,
            data_dir=data_dir,
            cascade_trigger=mock_cascade,
            idea_generator=mock_idea_gen,
        )

    # Verify full escalation
    run = store.get_heartbeat_run(run_id)
    assert run is not None
    assert run.highest_tier == 4
    assert run.completed_at is not None
    assert len(run.structured_log) == 4

    # Tier 3 should always escalate
    assert run.structured_log[2].tier == 3
    assert run.structured_log[2].escalated is True

    # Tier 4 should not escalate (final tier)
    assert run.structured_log[3].tier == 4
    assert run.structured_log[3].escalated is False

    # Cascade was triggered
    mock_cascade.assert_called_once()

    # Events
    assert len(collector.of_type("heartbeat_started")) == 1
    assert len(collector.of_type("heartbeat_tier_completed")) == 4
    assert len(collector.of_type("heartbeat_completed")) == 1

    completed = collector.of_type("heartbeat_completed")[0]
    assert completed.highest_tier == 4


@pytest.mark.asyncio
async def test_tier1_failure_stops_heartbeat(
    store: PolicyStore, emitter: EventEmitter, data_dir: Path
) -> None:
    """A failed Tier 1 agent stops the heartbeat at Tier 1."""
    _ = EventCollector(emitter)  # collector not used directly but sets up event handling

    async def mock_run(prompt):
        raise RuntimeError("API overloaded")

    p = create_mock_agent_patches(mock_run)
    with p:
        from policy_factory.heartbeat.orchestrator import run_heartbeat

        run_id = await run_heartbeat(
            trigger="manual",
            store=store,
            emitter=emitter,
            data_dir=data_dir,
        )

    run = store.get_heartbeat_run(run_id)
    assert run is not None
    assert run.completed_at is not None
    # The tier 1 entry is still recorded
    assert len(run.structured_log) == 1
    assert run.structured_log[0].escalated is False
    assert "Failed" in run.structured_log[0].outcome


@pytest.mark.asyncio
async def test_tier3_failure_prevents_tier4(
    store: PolicyStore, emitter: EventEmitter, data_dir: Path
) -> None:
    """A failed Tier 3 prevents Tier 4 from running."""
    _ = EventCollector(emitter)  # collector not used directly but sets up event handling

    outputs = [
        # Tier 1: flagged
        "STATUS: FLAGGED\nITEMS:\n- Something important",
        # Tier 2: update recommended
        "STATUS: UPDATE_RECOMMENDED\nITEMS:\n- Update this",
    ]
    call_count = 0

    async def mock_run(prompt):
        nonlocal call_count
        if call_count < len(outputs):
            result = MockAgentResult(full_output=outputs[call_count])
            call_count += 1
            return result
        # Tier 3 fails
        raise RuntimeError("Tier 3 agent failed")

    mock_cascade = AsyncMock()

    p = create_mock_agent_patches(mock_run)
    with p:
        from policy_factory.heartbeat.orchestrator import run_heartbeat

        run_id = await run_heartbeat(
            trigger="manual",
            store=store,
            emitter=emitter,
            data_dir=data_dir,
            cascade_trigger=mock_cascade,
        )

    # Tier 4 should NOT run
    mock_cascade.assert_not_called()

    run = store.get_heartbeat_run(run_id)
    assert run is not None
    assert run.completed_at is not None
    # Tier 3 recorded but failed
    assert len(run.structured_log) == 3
    assert run.structured_log[2].tier == 3
    assert run.structured_log[2].escalated is False
    assert "Failed" in run.structured_log[2].outcome


@pytest.mark.asyncio
async def test_tier4_cascade_queue_still_completes(
    store: PolicyStore, emitter: EventEmitter, data_dir: Path
) -> None:
    """If cascade trigger returns a queue entry, heartbeat still completes normally."""
    outputs = [
        "STATUS: FLAGGED\nITEMS:\n- Item",
        "STATUS: UPDATE_RECOMMENDED\nITEMS:\n- Do update",
        "SA files updated",
    ]
    call_count = 0

    async def mock_run(prompt):
        nonlocal call_count
        result = MockAgentResult(full_output=outputs[call_count])
        call_count += 1
        return result

    # Cascade returns queue entry (is_cascade=False)
    mock_cascade = AsyncMock(return_value=("queue-entry-id", False))

    p = create_mock_agent_patches(mock_run)
    with p, patch("policy_factory.data.git.commit_changes"):
        from policy_factory.heartbeat.orchestrator import run_heartbeat

        run_id = await run_heartbeat(
            trigger="scheduled",
            store=store,
            emitter=emitter,
            data_dir=data_dir,
            cascade_trigger=mock_cascade,
        )

    run = store.get_heartbeat_run(run_id)
    assert run is not None
    assert run.highest_tier == 4
    assert run.completed_at is not None


@pytest.mark.asyncio
async def test_heartbeat_records_agent_runs(
    store: PolicyStore, emitter: EventEmitter, data_dir: Path
) -> None:
    """Each tier's agent invocation is recorded in the agent_runs table."""
    async def mock_run(prompt):
        return MockAgentResult(
            full_output="STATUS: NOTHING_NOTEWORTHY\nNo news.",
        )

    p = create_mock_agent_patches(mock_run)
    with p:
        from policy_factory.heartbeat.orchestrator import run_heartbeat

        await run_heartbeat(
            trigger="manual",
            store=store,
            emitter=emitter,
            data_dir=data_dir,
        )

    # Should have at least 1 agent run (for tier 1)
    agent_runs = store.list_agent_runs(agent_type="heartbeat-skim")
    assert len(agent_runs) >= 1
    assert agent_runs[0].agent_type == "heartbeat-skim"
    assert agent_runs[0].success is True


@pytest.mark.asyncio
async def test_tier3_auto_commits(
    store: PolicyStore, emitter: EventEmitter, data_dir: Path
) -> None:
    """Tier 3 auto-commits data git repo changes on success."""
    outputs = [
        "STATUS: FLAGGED\nITEMS:\n- Item",
        "STATUS: UPDATE_RECOMMENDED\nITEMS:\n- Update",
        "SA updated",
    ]
    call_count = 0

    async def mock_run(prompt):
        nonlocal call_count
        result = MockAgentResult(full_output=outputs[call_count])
        call_count += 1
        return result

    p = create_mock_agent_patches(mock_run)
    with p, patch("policy_factory.data.git.commit_changes") as mock_commit:
        from policy_factory.heartbeat.orchestrator import run_heartbeat

        await run_heartbeat(
            trigger="manual",
            store=store,
            emitter=emitter,
            data_dir=data_dir,
        )

    # Verify git commit was called
    mock_commit.assert_called_once()
    args = mock_commit.call_args[0]
    assert args[0] == data_dir


@pytest.mark.asyncio
async def test_tier3_receives_feedback_memos(
    store: PolicyStore, emitter: EventEmitter, data_dir: Path
) -> None:
    """Tier 3 receives pending feedback memos targeting the SA layer."""
    # Create a feedback memo targeting SA
    store.create_feedback_memo(
        source_layer="strategic-objectives",
        target_layer="situational-awareness",
        cascade_id=None,
        content="Consider updating EU AI Act status",
    )

    outputs = [
        "STATUS: FLAGGED\nITEMS:\n- Item",
        "STATUS: UPDATE_RECOMMENDED\nITEMS:\n- Update",
        "SA updated with feedback",
    ]
    call_count = 0
    captured_prompts = []

    async def mock_run(prompt):
        nonlocal call_count
        captured_prompts.append(prompt)
        result = MockAgentResult(full_output=outputs[call_count])
        call_count += 1
        return result

    p = create_mock_agent_patches(mock_run)
    with p, patch("policy_factory.data.git.commit_changes"):
        from policy_factory.heartbeat.orchestrator import run_heartbeat

        await run_heartbeat(
            trigger="manual",
            store=store,
            emitter=emitter,
            data_dir=data_dir,
        )

    # The tier 3 prompt (3rd call) should contain the feedback memo
    assert len(captured_prompts) == 3
    tier3_prompt = captured_prompts[2]
    assert "Consider updating EU AI Act status" in tier3_prompt
