"""Tests for the critic runner and synthesis runner.

Uses mock agent sessions to test the orchestration logic without
actually calling the Anthropic SDK.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from policy_factory.cascade.critic_runner import (
    CriticRunnerResult,
    SingleCriticResult,
    parse_critic_assessment,
    run_critics,
)
from policy_factory.cascade.critics import CRITIC_ARCHETYPES, get_archetype_slugs
from policy_factory.cascade.synthesis_runner import (
    SynthesisRunnerResult,
    parse_synthesis_output,
    run_synthesis,
)
from policy_factory.events import EventEmitter
from policy_factory.store import PolicyStore

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """Create a data directory with sample layer content."""
    for layer in [
        "values",
        "situational-awareness",
        "strategic-objectives",
        "tactical-objectives",
        "policies",
    ]:
        layer_dir = tmp_path / layer
        layer_dir.mkdir()
        (layer_dir / "README.md").write_text(f"# {layer.title()}\n\nSummary for {layer}.")

    (tmp_path / "values" / "security.md").write_text(
        "---\ntitle: National Security\nstatus: active\n---\n"
        "Security is paramount."
    )
    return tmp_path


@pytest.fixture
def emitter() -> EventEmitter:
    """Provide a fresh EventEmitter."""
    return EventEmitter()


@dataclass
class MockAgentResult:
    """Mock result matching AgentResult interface."""
    is_error: bool = False
    result_text: str = ""
    total_cost_usd: float | None = 0.01
    num_turns: int | None = 1
    full_output: str = ""


# ---------------------------------------------------------------------------
# Mock helper for agent sessions with mocked Anthropic client
# ---------------------------------------------------------------------------


def create_mock_agent_patches(mock_run_fn):
    """Create patches for AgentSession and get_anthropic_client.

    This is needed because AgentSession requires an Anthropic client,
    and we want to mock the entire agent execution flow.

    Args:
        mock_run_fn: Async function to use for AgentSession.run()

    Returns:
        Tuple of patch contexts to use with ExitStack or nested with statements
    """
    mock_session = MagicMock()
    mock_session.run = AsyncMock(side_effect=mock_run_fn)
    mock_client = MagicMock()

    return (
        patch("policy_factory.agent.session.AgentSession", return_value=mock_session),
        patch("policy_factory.server.deps.get_anthropic_client", return_value=mock_client),
    )


# ---------------------------------------------------------------------------
# Assessment parsing tests
# ---------------------------------------------------------------------------


class TestParseCriticAssessment:
    """Test the structured assessment parser."""

    def test_parses_well_formatted_assessment(self):
        """Correctly parses a properly formatted critic assessment."""
        text = '''
## Assessment of "National Security"

**Agreement level**: Agree
**Score**: 8/10

**Analysis**: The security framework is comprehensive.

**Alternative recommendation**: Add supply chain considerations.

## Assessment of "Economic Policy"

**Agreement level**: Partially agree
**Score**: 6/10

**Analysis**: Needs more focus on technological sovereignty.

**Alternative recommendation**: Include tech sector protections.
'''
        result = parse_critic_assessment(text)
        assert result is not None
        assert "items" in result
        assert len(result["items"]) == 2

        item1 = result["items"][0]
        assert item1["title"] == "National Security"
        assert item1["agreement_level"] == "Agree"
        assert item1["score"] == 8

        item2 = result["items"][1]
        assert item2["title"] == "Economic Policy"
        assert item2["score"] == 6

    def test_calculates_average_score(self):
        """Calculates average score when scores are present."""
        text = '''
## Assessment of "Item A"

**Score**: 8/10

## Assessment of "Item B"

**Score**: 6/10
'''
        result = parse_critic_assessment(text)
        assert result is not None
        assert result["average_score"] == 7.0

    def test_returns_none_for_empty_text(self):
        """Returns None for empty or whitespace-only text."""
        assert parse_critic_assessment("") is None
        assert parse_critic_assessment("   ") is None
        assert parse_critic_assessment(None) is None

    def test_returns_none_for_unstructured_text(self):
        """Returns None when text doesn't follow the expected format."""
        text = "This is just a free-form paragraph without structure."
        result = parse_critic_assessment(text)
        assert result is None

    def test_lenient_with_missing_sections(self):
        """Parser extracts what it can even with missing sections."""
        text = '''
## Assessment of "Partial Item"

**Score**: 7/10
'''
        result = parse_critic_assessment(text)
        assert result is not None
        assert result["items"][0]["score"] == 7
        assert "agreement_level" not in result["items"][0]


class TestParseSynthesisOutput:
    """Test the synthesis output parser."""

    def test_parses_well_formatted_synthesis(self):
        """Correctly parses a properly formatted synthesis."""
        text = '''
## Synthesis for values

### Areas of Consensus
Security and economic stability are universally important.

### Key Tensions
The Realist and Liberal-Institutionalist perspectives fundamentally disagree on NATO.

### Strongest Criticisms
Insufficient attention to digital sovereignty.

### Recommended Refinements
Add explicit cybersecurity provisions.

### Overall Score: 7/10
'''
        result = parse_synthesis_output(text)
        assert result is not None
        assert "consensus_points" in result
        assert "tension_points" in result
        assert "recommendations" in result
        assert result["overall_score"] == 7

    def test_returns_none_for_empty(self):
        """Returns None for empty text."""
        assert parse_synthesis_output("") is None
        assert parse_synthesis_output(None) is None

    def test_returns_none_for_unstructured(self):
        """Returns None for unstructured text."""
        assert parse_synthesis_output("Just a paragraph.") is None

    def test_partial_sections_extracted(self):
        """Extracts whatever sections are present."""
        text = '''
### Key Tensions
Realist vs Liberal disagreement on NATO.
'''
        result = parse_synthesis_output(text)
        assert result is not None
        assert "tension_points" in result
        assert "consensus_points" not in result


# ---------------------------------------------------------------------------
# Critic runner tests (with mocked agents)
# ---------------------------------------------------------------------------


class TestCriticRunner:
    """Test the critic runner with mocked agent sessions."""

    @pytest.mark.asyncio
    async def test_runs_all_six_critics(
        self, store: PolicyStore, emitter: EventEmitter, data_dir: Path,
    ):
        """The critic runner launches all 6 critic agents."""
        call_count = 0

        async def mock_run(prompt):
            nonlocal call_count
            call_count += 1
            return MockAgentResult(full_output=f"Assessment {call_count}")

        p1, p2 = create_mock_agent_patches(mock_run)
        with p1, p2:
            result = await run_critics(
                layer_slug="values",
                cascade_id="cascade-test",
                store=store,
                emitter=emitter,
                data_dir=data_dir,
            )

        assert call_count == 6
        assert isinstance(result, CriticRunnerResult)
        assert result.successful_count == 6
        assert result.failed_count == 0

    @pytest.mark.asyncio
    async def test_all_critics_receive_same_content(
        self, store: PolicyStore, emitter: EventEmitter, data_dir: Path,
    ):
        """All 6 critics receive the same layer content."""
        prompts_received = []

        async def mock_run(prompt):
            prompts_received.append(prompt)
            return MockAgentResult(full_output="Assessment")

        p1, p2 = create_mock_agent_patches(mock_run)
        with p1, p2:
            await run_critics(
                layer_slug="values",
                cascade_id="cascade-test",
                store=store,
                emitter=emitter,
                data_dir=data_dir,
            )

        assert len(prompts_received) == 6
        # All prompts should contain "Security is paramount" (from the test data)
        for prompt in prompts_received:
            assert "Security is paramount" in prompt

    @pytest.mark.asyncio
    async def test_each_critic_uses_archetype_prompt(
        self, store: PolicyStore, emitter: EventEmitter, data_dir: Path,
    ):
        """Each critic uses its archetype-specific prompt template."""
        prompts_received = []

        async def mock_run(prompt):
            prompts_received.append(prompt)
            return MockAgentResult(full_output="Assessment")

        p1, p2 = create_mock_agent_patches(mock_run)
        with p1, p2:
            await run_critics(
                layer_slug="values",
                cascade_id="cascade-test",
                store=store,
                emitter=emitter,
                data_dir=data_dir,
            )

        # Each prompt should be different (archetype-specific)
        assert len(set(prompts_received)) == 6

    @pytest.mark.asyncio
    async def test_emits_started_and_completed_events(
        self, store: PolicyStore, emitter: EventEmitter, data_dir: Path,
    ):
        """CriticStarted and CriticCompleted events are emitted for each critic."""
        events_received = []

        async def capture_event(event):
            events_received.append(event)

        emitter.subscribe(capture_event)

        async def mock_run(prompt):
            return MockAgentResult(full_output="Assessment")

        p1, p2 = create_mock_agent_patches(mock_run)
        with p1, p2:
            await run_critics(
                layer_slug="values",
                cascade_id="cascade-test",
                store=store,
                emitter=emitter,
                data_dir=data_dir,
            )

        started_events = [e for e in events_received if e.event_type == "critic_started"]
        completed_events = [e for e in events_received if e.event_type == "critic_completed"]

        assert len(started_events) == 6
        assert len(completed_events) == 6

        # Check archetypes are present
        started_archetypes = {e.critic_archetype for e in started_events}
        assert started_archetypes == set(get_archetype_slugs())

    @pytest.mark.asyncio
    async def test_records_agent_runs(
        self, store: PolicyStore, emitter: EventEmitter, data_dir: Path,
    ):
        """Each critic invocation is recorded as an agent run."""
        async def mock_run(prompt):
            return MockAgentResult(full_output="Assessment")

        p1, p2 = create_mock_agent_patches(mock_run)
        with p1, p2:
            await run_critics(
                layer_slug="values",
                cascade_id="cascade-test",
                store=store,
                emitter=emitter,
                data_dir=data_dir,
            )

        agent_runs = store.list_agent_runs(cascade_id="cascade-test", agent_type="critic")
        assert len(agent_runs) == 6

    @pytest.mark.asyncio
    async def test_results_stored_in_database(
        self, store: PolicyStore, emitter: EventEmitter, data_dir: Path,
    ):
        """Critic results are stored in the critic_results table."""
        async def mock_run(prompt):
            return MockAgentResult(full_output="Detailed assessment text")

        p1, p2 = create_mock_agent_patches(mock_run)
        with p1, p2:
            await run_critics(
                layer_slug="values",
                cascade_id="cascade-test",
                store=store,
                emitter=emitter,
                data_dir=data_dir,
            )

        db_results = store.get_critic_results("cascade-test", "values")
        assert len(db_results) == 6

    @pytest.mark.asyncio
    async def test_partial_failure_handling(
        self, store: PolicyStore, emitter: EventEmitter, data_dir: Path,
    ):
        """If one critic fails, the remaining 5 still complete."""
        call_count = 0

        async def mock_run(prompt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("API error")
            return MockAgentResult(full_output="Assessment")

        p1, p2 = create_mock_agent_patches(mock_run)
        with p1, p2:
            result = await run_critics(
                layer_slug="values",
                cascade_id="cascade-test",
                store=store,
                emitter=emitter,
                data_dir=data_dir,
            )

        assert result.overall_success is True
        assert result.successful_count == 5
        assert result.failed_count == 1

    @pytest.mark.asyncio
    async def test_all_critics_fail_reports_failure(
        self, store: PolicyStore, emitter: EventEmitter, data_dir: Path,
    ):
        """If all 6 critics fail, the overall result reports failure."""
        async def mock_run(prompt):
            raise RuntimeError("All broken")

        p1, p2 = create_mock_agent_patches(mock_run)
        with p1, p2:
            result = await run_critics(
                layer_slug="values",
                cascade_id="cascade-test",
                store=store,
                emitter=emitter,
                data_dir=data_dir,
            )

        assert result.overall_success is False
        assert result.successful_count == 0
        assert result.failed_count == 6

    @pytest.mark.asyncio
    async def test_at_least_one_success_reports_overall_success(
        self, store: PolicyStore, emitter: EventEmitter, data_dir: Path,
    ):
        """If at least one critic succeeds, overall success is True."""
        call_count = 0

        async def mock_run(prompt):
            nonlocal call_count
            call_count += 1
            if call_count <= 5:
                raise RuntimeError("Failed")
            return MockAgentResult(full_output="Last one works")

        p1, p2 = create_mock_agent_patches(mock_run)
        with p1, p2:
            result = await run_critics(
                layer_slug="values",
                cascade_id="cascade-test",
                store=store,
                emitter=emitter,
                data_dir=data_dir,
            )

        assert result.overall_success is True
        assert result.successful_count == 1
        assert result.failed_count == 5

    @pytest.mark.asyncio
    async def test_critics_run_concurrently(
        self, store: PolicyStore, emitter: EventEmitter, data_dir: Path,
    ):
        """Critics run concurrently (not sequentially)."""
        import time

        start_times: list[float] = []

        async def mock_run(prompt):
            start_times.append(time.monotonic())
            await asyncio.sleep(0.05)  # Simulate work
            return MockAgentResult(full_output="Assessment")

        p1, p2 = create_mock_agent_patches(mock_run)
        with p1, p2:
            start = time.monotonic()
            await run_critics(
                layer_slug="values",
                cascade_id="cascade-test",
                store=store,
                emitter=emitter,
                data_dir=data_dir,
            )
            elapsed = time.monotonic() - start

        # If sequential: 6 * 0.05 = 0.3s minimum
        # If concurrent: ~0.05s
        assert len(start_times) == 6
        assert elapsed < 0.25, f"Critics appear sequential: {elapsed:.2f}s"

    @pytest.mark.asyncio
    async def test_custom_layer_content(
        self, store: PolicyStore, emitter: EventEmitter, data_dir: Path,
    ):
        """Pre-gathered layer content is used when provided."""
        prompts_received = []

        async def mock_run(prompt):
            prompts_received.append(prompt)
            return MockAgentResult(full_output="Assessment")

        p1, p2 = create_mock_agent_patches(mock_run)
        with p1, p2:
            await run_critics(
                layer_slug="values",
                cascade_id="cascade-test",
                store=store,
                emitter=emitter,
                data_dir=data_dir,
                layer_content="Custom content to critique",
            )

        for prompt in prompts_received:
            assert "Custom content to critique" in prompt

    @pytest.mark.asyncio
    async def test_critic_runner_result_helpers(
        self, store: PolicyStore, emitter: EventEmitter, data_dir: Path,
    ):
        """CriticRunnerResult helper methods work correctly."""
        async def mock_run(prompt):
            return MockAgentResult(full_output="Assessment")

        p1, p2 = create_mock_agent_patches(mock_run)
        with p1, p2:
            result = await run_critics(
                layer_slug="values",
                cascade_id="cascade-test",
                store=store,
                emitter=emitter,
                data_dir=data_dir,
            )

        successful = result.get_successful_results()
        assert len(successful) == 6

        realist = result.get_result_by_archetype("realist")
        assert realist is not None
        assert realist.archetype == "realist"

        nonexistent = result.get_result_by_archetype("nonexistent")
        assert nonexistent is None


# ---------------------------------------------------------------------------
# Synthesis runner tests
# ---------------------------------------------------------------------------


class TestSynthesisRunner:
    """Test the synthesis runner with mocked agent sessions."""

    def _make_critic_results(self, successful: int = 6) -> CriticRunnerResult:
        """Create a mock CriticRunnerResult."""
        results = []
        for i, archetype in enumerate(CRITIC_ARCHETYPES):
            if i < successful:
                results.append(
                    SingleCriticResult(
                        archetype=archetype.slug,
                        success=True,
                        assessment_text=f"Assessment from {archetype.display_name}",
                        agent_run_id=f"run-{archetype.slug}",
                    )
                )
            else:
                results.append(
                    SingleCriticResult(
                        archetype=archetype.slug,
                        success=False,
                        error="Failed",
                        agent_run_id=f"run-{archetype.slug}",
                    )
                )
        return CriticRunnerResult(
            results=results,
            successful_count=successful,
            failed_count=6 - successful,
        )

    @pytest.mark.asyncio
    async def test_synthesis_runs_with_full_critic_results(
        self, store: PolicyStore, emitter: EventEmitter, data_dir: Path,
    ):
        """Synthesis runs when all 6 critics succeeded."""
        critic_results = self._make_critic_results(6)

        async def mock_run(prompt):
            return MockAgentResult(full_output="Synthesis output")

        p1, p2 = create_mock_agent_patches(mock_run)
        with p1, p2:
            result = await run_synthesis(
                layer_slug="values",
                critic_results=critic_results,
                cascade_id="cascade-test",
                store=store,
                emitter=emitter,
                data_dir=data_dir,
            )

        assert isinstance(result, SynthesisRunnerResult)
        assert result.success is True
        assert result.synthesis_text == "Synthesis output"

    @pytest.mark.asyncio
    async def test_synthesis_receives_all_critic_outputs(
        self, store: PolicyStore, emitter: EventEmitter, data_dir: Path,
    ):
        """The synthesis prompt includes all 6 critic assessments."""
        critic_results = self._make_critic_results(6)
        prompts_received = []

        async def mock_run(prompt):
            prompts_received.append(prompt)
            return MockAgentResult(full_output="Synthesis")

        p1, p2 = create_mock_agent_patches(mock_run)
        with p1, p2:
            await run_synthesis(
                layer_slug="values",
                critic_results=critic_results,
                cascade_id="cascade-test",
                store=store,
                emitter=emitter,
                data_dir=data_dir,
            )

        assert len(prompts_received) == 1
        prompt = prompts_received[0]
        # All critic assessments should be in the prompt
        for archetype in CRITIC_ARCHETYPES:
            assert f"Assessment from {archetype.display_name}" in prompt

    @pytest.mark.asyncio
    async def test_synthesis_notes_missing_critics(
        self, store: PolicyStore, emitter: EventEmitter, data_dir: Path,
    ):
        """The synthesis prompt notes which critics failed."""
        critic_results = self._make_critic_results(4)  # 4 success, 2 failure
        prompts_received = []

        async def mock_run(prompt):
            prompts_received.append(prompt)
            return MockAgentResult(full_output="Synthesis")

        p1, p2 = create_mock_agent_patches(mock_run)
        with p1, p2:
            await run_synthesis(
                layer_slug="values",
                critic_results=critic_results,
                cascade_id="cascade-test",
                store=store,
                emitter=emitter,
                data_dir=data_dir,
            )

        prompt = prompts_received[0]
        assert "not available" in prompt

    @pytest.mark.asyncio
    async def test_synthesis_skips_when_zero_critics(
        self, store: PolicyStore, emitter: EventEmitter, data_dir: Path,
    ):
        """Synthesis does not run when zero critics succeeded."""
        critic_results = self._make_critic_results(0)

        result = await run_synthesis(
            layer_slug="values",
            critic_results=critic_results,
            cascade_id="cascade-test",
            store=store,
            emitter=emitter,
            data_dir=data_dir,
        )

        assert result.success is False
        assert "No successful critic" in result.error

    @pytest.mark.asyncio
    async def test_synthesis_runs_with_partial_critics(
        self, store: PolicyStore, emitter: EventEmitter, data_dir: Path,
    ):
        """Synthesis runs even with only some critics successful."""
        critic_results = self._make_critic_results(3)

        async def mock_run(prompt):
            return MockAgentResult(full_output="Partial synthesis")

        p1, p2 = create_mock_agent_patches(mock_run)
        with p1, p2:
            result = await run_synthesis(
                layer_slug="values",
                critic_results=critic_results,
                cascade_id="cascade-test",
                store=store,
                emitter=emitter,
                data_dir=data_dir,
            )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_emits_synthesis_events(
        self, store: PolicyStore, emitter: EventEmitter, data_dir: Path,
    ):
        """SynthesisStarted and SynthesisCompleted events are emitted."""
        critic_results = self._make_critic_results(6)
        events_received = []

        async def capture_event(event):
            events_received.append(event)

        emitter.subscribe(capture_event)

        async def mock_run(prompt):
            return MockAgentResult(full_output="Synthesis")

        p1, p2 = create_mock_agent_patches(mock_run)
        with p1, p2:
            await run_synthesis(
                layer_slug="values",
                critic_results=critic_results,
                cascade_id="cascade-test",
                store=store,
                emitter=emitter,
                data_dir=data_dir,
            )

        started = [e for e in events_received if e.event_type == "synthesis_started"]
        completed = [e for e in events_received if e.event_type == "synthesis_completed"]

        assert len(started) == 1
        assert len(completed) == 1

    @pytest.mark.asyncio
    async def test_synthesis_records_agent_run(
        self, store: PolicyStore, emitter: EventEmitter, data_dir: Path,
    ):
        """Synthesis invocation is recorded as an agent run."""
        critic_results = self._make_critic_results(6)

        async def mock_run(prompt):
            return MockAgentResult(full_output="Synthesis")

        p1, p2 = create_mock_agent_patches(mock_run)
        with p1, p2:
            await run_synthesis(
                layer_slug="values",
                critic_results=critic_results,
                cascade_id="cascade-test",
                store=store,
                emitter=emitter,
                data_dir=data_dir,
            )

        runs = store.list_agent_runs(cascade_id="cascade-test", agent_type="synthesis")
        assert len(runs) == 1

    @pytest.mark.asyncio
    async def test_synthesis_stored_in_database(
        self, store: PolicyStore, emitter: EventEmitter, data_dir: Path,
    ):
        """Synthesis result is stored in the synthesis_results table."""
        critic_results = self._make_critic_results(6)

        async def mock_run(prompt):
            return MockAgentResult(full_output="Stored synthesis")

        p1, p2 = create_mock_agent_patches(mock_run)
        with p1, p2:
            await run_synthesis(
                layer_slug="values",
                critic_results=critic_results,
                cascade_id="cascade-test",
                store=store,
                emitter=emitter,
                data_dir=data_dir,
            )

        db_result = store.get_synthesis_result("cascade-test", "values")
        assert db_result is not None
        assert db_result.synthesis_text == "Stored synthesis"

    @pytest.mark.asyncio
    async def test_synthesis_failure_returns_error(
        self, store: PolicyStore, emitter: EventEmitter, data_dir: Path,
    ):
        """Synthesis agent failure returns a failure result."""
        critic_results = self._make_critic_results(6)

        async def mock_run(prompt):
            raise RuntimeError("Synthesis crashed")

        p1, p2 = create_mock_agent_patches(mock_run)
        with p1, p2:
            result = await run_synthesis(
                layer_slug="values",
                critic_results=critic_results,
                cascade_id="cascade-test",
                store=store,
                emitter=emitter,
                data_dir=data_dir,
            )

        assert result.success is False
        assert "crashed" in result.error

    @pytest.mark.asyncio
    async def test_synthesis_with_none_critic_results_and_db(
        self, store: PolicyStore, emitter: EventEmitter, data_dir: Path,
    ):
        """When critic_results is None, synthesis fetches from database."""
        # Pre-store some critic results in the database
        for archetype in get_archetype_slugs():
            store.store_critic_result(
                cascade_id="cascade-test",
                layer_slug="values",
                idea_id=None,
                archetype=archetype,
                assessment_text=f"DB assessment from {archetype}",
                structured_assessment=None,
                agent_run_id=f"run-{archetype}",
            )

        async def mock_run(prompt):
            return MockAgentResult(full_output="Synthesis from DB results")

        p1, p2 = create_mock_agent_patches(mock_run)
        with p1, p2:
            result = await run_synthesis(
                layer_slug="values",
                critic_results=None,
                cascade_id="cascade-test",
                store=store,
                emitter=emitter,
                data_dir=data_dir,
            )

        assert result.success is True
