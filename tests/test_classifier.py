"""Tests for the input classifier agent.

Tests the classification output parsing, layer summary building,
and the full classify_input function (with mocked agent sessions).
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from policy_factory.cascade.classifier import (
    _build_layer_summaries,
    _parse_classification_output,
    classify_input,
)
from policy_factory.data.layers import LAYER_SLUGS

# ---------------------------------------------------------------------------
# Output parsing tests
# ---------------------------------------------------------------------------


class TestParseClassificationOutput:
    """Tests for _parse_classification_output."""

    def test_parses_valid_output(self) -> None:
        output = """
PRIMARY_LAYER: situational-awareness
SECONDARY_LAYERS: strategic-objectives, tactical-objectives
CONFIDENCE: high
EXPLANATION: The input describes a new development in Finland's landscape.
"""
        result = _parse_classification_output(output)
        assert result.target_layer == "situational-awareness"
        assert "strategic-objectives" in result.secondary_layers
        assert "tactical-objectives" in result.secondary_layers
        assert result.confidence == "high"
        assert "finland" in result.explanation.lower()

    def test_parses_no_secondary_layers(self) -> None:
        output = """
PRIMARY_LAYER: values
SECONDARY_LAYERS: none
CONFIDENCE: medium
EXPLANATION: This is about core national values.
"""
        result = _parse_classification_output(output)
        assert result.target_layer == "values"
        assert result.secondary_layers == []
        assert result.confidence == "medium"

    def test_falls_back_on_invalid_layer(self) -> None:
        output = """
PRIMARY_LAYER: invalid-layer
SECONDARY_LAYERS: none
CONFIDENCE: high
EXPLANATION: Testing invalid layer.
"""
        result = _parse_classification_output(output)
        assert result.target_layer == "situational-awareness"

    def test_falls_back_on_empty_output(self) -> None:
        result = _parse_classification_output("")
        assert result.target_layer == "situational-awareness"
        assert result.confidence == "medium"

    def test_parses_all_valid_layer_slugs(self) -> None:
        for slug in LAYER_SLUGS:
            output = (
                f"PRIMARY_LAYER: {slug}\n"
                "SECONDARY_LAYERS: none\n"
                "CONFIDENCE: high\n"
                "EXPLANATION: Test."
            )
            result = _parse_classification_output(output)
            assert result.target_layer == slug

    def test_handles_backtick_wrapped_slug(self) -> None:
        output = """
PRIMARY_LAYER: `policies`
SECONDARY_LAYERS: `tactical-objectives`
CONFIDENCE: high
EXPLANATION: Specific policy proposal.
"""
        result = _parse_classification_output(output)
        assert result.target_layer == "policies"
        assert "tactical-objectives" in result.secondary_layers

    def test_handles_mixed_case(self) -> None:
        output = """
primary_layer: values
Secondary_Layers: none
CONFIDENCE: Low
Explanation: Test.
"""
        result = _parse_classification_output(output)
        assert result.target_layer == "values"
        assert result.confidence == "low"

    def test_excludes_primary_from_secondary(self) -> None:
        output = """
PRIMARY_LAYER: values
SECONDARY_LAYERS: values, policies
CONFIDENCE: high
EXPLANATION: Test.
"""
        result = _parse_classification_output(output)
        assert result.target_layer == "values"
        assert "values" not in result.secondary_layers
        assert "policies" in result.secondary_layers


# ---------------------------------------------------------------------------
# Layer summary building tests
# ---------------------------------------------------------------------------


class TestBuildLayerSummaries:
    """Tests for _build_layer_summaries."""

    def test_builds_summaries_for_all_layers(self, tmp_path: Path) -> None:
        # Create minimal layer directories
        for slug in LAYER_SLUGS:
            layer_dir = tmp_path / slug
            layer_dir.mkdir(parents=True, exist_ok=True)

        summaries = _build_layer_summaries(tmp_path)
        assert "Values" in summaries
        assert "Situational Awareness" in summaries
        assert "Strategic Objectives" in summaries
        assert "Tactical Objectives" in summaries
        assert "Policies" in summaries

    def test_includes_item_counts(self, tmp_path: Path) -> None:
        # Create minimal values layer with 2 items
        values_dir = tmp_path / "values"
        values_dir.mkdir(parents=True, exist_ok=True)
        (values_dir / "item1.md").write_text("---\ntitle: Item 1\n---\nContent")
        (values_dir / "item2.md").write_text("---\ntitle: Item 2\n---\nContent")

        # Create other empty layer directories
        for slug in LAYER_SLUGS:
            if slug != "values":
                (tmp_path / slug).mkdir(parents=True, exist_ok=True)

        summaries = _build_layer_summaries(tmp_path)
        assert "2 items" in summaries


# ---------------------------------------------------------------------------
# classify_input integration tests (with mocked agent)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestClassifyInput:
    """Tests for the full classify_input function with mocked agent."""

    async def test_classifies_input_and_records_agent_run(
        self, tmp_path: Path
    ) -> None:
        """Test classification with a mocked agent session."""
        from policy_factory.events import EventEmitter
        from policy_factory.store import PolicyStore

        # Set up store and emitter
        store = PolicyStore(tmp_path / "test.db")
        emitter = EventEmitter()

        # Create minimal layer directories
        data_dir = tmp_path / "data"
        for slug in LAYER_SLUGS:
            (data_dir / slug).mkdir(parents=True, exist_ok=True)

        # Mock the agent session
        mock_result = MagicMock()
        mock_result.is_error = False
        mock_result.full_output = (
            "PRIMARY_LAYER: policies\n"
            "SECONDARY_LAYERS: tactical-objectives\n"
            "CONFIDENCE: high\n"
            "EXPLANATION: This is a specific policy proposal about semiconductor independence.\n"
        )
        mock_result.total_cost_usd = 0.01
        mock_result.result_text = ""

        mock_session_instance = MagicMock()
        mock_session_instance.run = AsyncMock(return_value=mock_result)

        with patch(
            "policy_factory.agent.session.AgentSession",
        ) as mock_session_class, patch(
            "policy_factory.agent.config.resolve_model",
            return_value="claude-sonnet-4-20250514",
        ), patch(
            "policy_factory.agent.prompts.build_agent_prompt",
            return_value="test prompt",
        ):
            mock_session_class.return_value = mock_session_instance
            result = await classify_input(
                user_input="Finland should prioritise semiconductor manufacturing independence",
                store=store,
                emitter=emitter,
                data_dir=data_dir,
            )

        assert result.target_layer == "policies"
        assert result.confidence == "high"
        assert "semiconductor" in result.explanation.lower()

        # Verify agent run was recorded
        runs = store.list_agent_runs(agent_type="classifier")
        assert len(runs) == 1
        assert runs[0].agent_type == "classifier"
        assert runs[0].success is True

    async def test_falls_back_on_agent_failure(self, tmp_path: Path) -> None:
        """Test graceful fallback when the agent fails."""
        from policy_factory.events import EventEmitter
        from policy_factory.store import PolicyStore

        store = PolicyStore(tmp_path / "test.db")
        emitter = EventEmitter()

        data_dir = tmp_path / "data"
        for slug in LAYER_SLUGS:
            (data_dir / slug).mkdir(parents=True, exist_ok=True)

        mock_session_instance = MagicMock()
        mock_session_instance.run = AsyncMock(side_effect=RuntimeError("Agent failed"))

        with patch(
            "policy_factory.agent.session.AgentSession",
        ) as mock_session_class, patch(
            "policy_factory.agent.config.resolve_model",
            return_value="claude-sonnet-4-20250514",
        ), patch(
            "policy_factory.agent.prompts.build_agent_prompt",
            return_value="test prompt",
        ):
            mock_session_class.return_value = mock_session_instance
            result = await classify_input(
                user_input="Some input",
                store=store,
                emitter=emitter,
                data_dir=data_dir,
            )

        # Falls back to situational-awareness
        assert result.target_layer == "situational-awareness"
        assert result.confidence == "low"

        # Agent run should be recorded as failed
        runs = store.list_agent_runs(agent_type="classifier")
        assert len(runs) == 1
        assert runs[0].success is False
