"""Tests for the idea pipeline helpers (stack summary and score parsing)."""

from pathlib import Path

import pytest

from policy_factory.ideas.helpers import (
    gather_stack_summary,
    gather_stack_summary_text,
    get_default_scores,
    parse_evaluation_scores,
    parse_generated_ideas,
)


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """Create a temporary data directory with layer subdirectories."""
    layer_slugs = [
        "philosophy",
        "values",
        "situational-awareness",
        "strategic-objectives",
        "tactical-objectives",
        "policies",
    ]
    for slug in layer_slugs:
        layer_dir = tmp_path / slug
        layer_dir.mkdir()
        # Write a README for each
        (layer_dir / "README.md").write_text(
            f"# {slug.replace('-', ' ').title()}\n\nNarrative summary for {slug}."
        )
        # Write a sample item
        (layer_dir / "sample-item.md").write_text(
            f"---\ntitle: Sample {slug} item\nstatus: active\n---\n\n"
            f"Content for {slug} sample item."
        )

    return tmp_path


class TestGatherStackSummary:
    """Tests for gather_stack_summary()."""

    def test_returns_all_six_layers(self, data_dir: Path) -> None:
        summaries = gather_stack_summary(data_dir)
        assert "philosophy_summary" in summaries
        assert "values_summary" in summaries
        assert "sa_summary" in summaries
        assert "strategic_summary" in summaries
        assert "tactical_summary" in summaries
        assert "policies_summary" in summaries

    def test_includes_narrative_content(self, data_dir: Path) -> None:
        summaries = gather_stack_summary(data_dir)
        assert "Narrative summary for values" in summaries["values_summary"]

    def test_includes_item_titles(self, data_dir: Path) -> None:
        summaries = gather_stack_summary(data_dir)
        assert "Sample values item" in summaries["values_summary"]

    def test_handles_empty_layers(self, tmp_path: Path) -> None:
        # Create minimal data dir with only directory structure
        for slug in ["values", "situational-awareness", "strategic-objectives",
                      "tactical-objectives", "policies"]:
            (tmp_path / slug).mkdir()

        summaries = gather_stack_summary(tmp_path)
        # Should return placeholder text for layers without content
        assert "No content" in summaries.get("values_summary", "")


class TestGatherStackSummaryText:
    """Tests for gather_stack_summary_text()."""

    def test_returns_combined_text(self, data_dir: Path) -> None:
        text = gather_stack_summary_text(data_dir)
        assert "Values" in text
        assert "Situational Awareness" in text
        assert "Strategic Objectives" in text
        assert "Tactical Objectives" in text
        assert "Policies" in text


class TestParseEvaluationScores:
    """Tests for parse_evaluation_scores()."""

    def test_parses_standard_format(self) -> None:
        text = """
## Idea Evaluation

### Scores
- Feasibility: 7/10
- Alignment with values: 8/10
- Political viability: 6/10
- Evidence basis: 5/10
- Implementation complexity: 4/10
- Innovation: 9/10

### Overall Assessment
This is a good idea.
"""
        scores = parse_evaluation_scores(text)
        assert scores is not None
        assert scores["feasibility"] == 7.0
        assert scores["strategic_fit"] == 8.0
        assert scores["public_acceptance"] == 6.0
        assert scores["cost"] == 5.0
        assert scores["risk"] == 4.0
        assert scores["international_impact"] == 9.0

    def test_returns_none_for_empty_text(self) -> None:
        assert parse_evaluation_scores("") is None
        assert parse_evaluation_scores("  ") is None

    def test_returns_none_for_no_scores(self) -> None:
        text = "This is just a paragraph with no scores."
        assert parse_evaluation_scores(text) is None

    def test_fills_missing_with_defaults(self) -> None:
        text = """
- Feasibility: 7/10
- Alignment with values: 8/10
- Political viability: 6/10
"""
        scores = parse_evaluation_scores(text)
        assert scores is not None
        assert scores["feasibility"] == 7.0
        assert scores["strategic_fit"] == 8.0
        assert scores["public_acceptance"] == 6.0
        # Missing fields get 5.0 default
        assert scores["cost"] == 5.0
        assert scores["risk"] == 5.0
        assert scores["international_impact"] == 5.0

    def test_handles_bold_formatting(self) -> None:
        text = """
- **Feasibility**: 7/10
- **Alignment with values**: 8/10
- **Political viability**: 6/10
- **Evidence basis**: 5/10
- **Implementation complexity**: 4/10
- **Innovation**: 9/10
"""
        scores = parse_evaluation_scores(text)
        assert scores is not None
        assert scores["feasibility"] == 7.0


class TestGetDefaultScores:
    """Tests for get_default_scores()."""

    def test_all_zeros(self) -> None:
        scores = get_default_scores()
        assert scores["strategic_fit"] == 0.0
        assert scores["feasibility"] == 0.0
        assert scores["cost"] == 0.0
        assert scores["risk"] == 0.0
        assert scores["public_acceptance"] == 0.0
        assert scores["international_impact"] == 0.0

    def test_has_all_keys(self) -> None:
        scores = get_default_scores()
        expected_keys = {
            "strategic_fit", "feasibility", "cost",
            "risk", "public_acceptance", "international_impact",
        }
        assert set(scores.keys()) == expected_keys


class TestParseGeneratedIdeas:
    """Tests for parse_generated_ideas()."""

    def test_parses_standard_format(self) -> None:
        text = """
Here are some ideas:

## Idea: AI Tax Holiday

**Summary**: Finland should offer a 5-year tax holiday for AI companies.

**Rationale**: To attract talent.

## Idea: Sovereign Compute Fund

**Summary**: Create a national fund for compute resources.

**Rationale**: To ensure sovereignty.

## Idea: Ethics Board

**Summary**: Establish a national AI ethics board.

**Rationale**: To build trust.
"""
        ideas = parse_generated_ideas(text)
        assert len(ideas) == 3
        assert ideas[0]["title"] == "AI Tax Holiday"
        assert "tax holiday" in ideas[0]["text"].lower()
        assert ideas[1]["title"] == "Sovereign Compute Fund"
        assert ideas[2]["title"] == "Ethics Board"

    def test_returns_empty_for_no_ideas(self) -> None:
        assert parse_generated_ideas("") == []
        assert parse_generated_ideas("Just a paragraph.") == []

    def test_returns_empty_for_none_text(self) -> None:
        assert parse_generated_ideas("") == []
