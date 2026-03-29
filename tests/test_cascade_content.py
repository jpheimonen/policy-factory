"""Tests for layer content gathering utilities."""

from pathlib import Path

import pytest

from policy_factory.cascade.content import (
    check_prerequisites,
    gather_context_below,
    gather_cross_layer_context,
    gather_layer_content,
)


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """Create a temporary data directory with layer subdirectories."""
    for layer in [
        "philosophy",
        "values",
        "situational-awareness",
        "strategic-objectives",
        "tactical-objectives",
        "policies",
    ]:
        (tmp_path / layer).mkdir()
    return tmp_path


@pytest.fixture
def populated_data_dir(data_dir: Path) -> Path:
    """Create a data directory with sample content."""
    # Values layer — narrative summary
    (data_dir / "values" / "README.md").write_text(
        "# Values Layer\n\nThis layer defines Finland's core national values."
    )

    # Values layer — items
    (data_dir / "values" / "national-security.md").write_text(
        "---\ntitle: National Security\nstatus: active\n---\n"
        "National security is Finland's paramount concern."
    )
    (data_dir / "values" / "economic-prosperity.md").write_text(
        "---\ntitle: Economic Prosperity\nstatus: active\n---\n"
        "Economic prosperity enables social welfare."
    )

    # Situational awareness — narrative summary only
    (data_dir / "situational-awareness" / "README.md").write_text(
        "# Situational Awareness\n\nCurrent geopolitical analysis."
    )

    return data_dir


class TestGatherLayerContent:
    """Test the gather_layer_content function."""

    def test_gathers_narrative_summary(self, populated_data_dir: Path):
        """The gathered content includes the narrative summary."""
        content = gather_layer_content(populated_data_dir, "values")
        assert "Finland's core national values" in content

    def test_gathers_all_items(self, populated_data_dir: Path):
        """The gathered content includes all items in the layer."""
        content = gather_layer_content(populated_data_dir, "values")
        assert "National Security" in content
        assert "Economic Prosperity" in content

    def test_items_include_body_content(self, populated_data_dir: Path):
        """Item body content is included in the gathered text."""
        content = gather_layer_content(populated_data_dir, "values")
        assert "paramount concern" in content
        assert "social welfare" in content

    def test_empty_layer_returns_fallback(self, data_dir: Path):
        """An empty layer returns a fallback message."""
        content = gather_layer_content(data_dir, "values")
        assert "No content available" in content

    def test_narrative_only_layer(self, data_dir: Path):
        """A layer with only a narrative (no items) is handled."""
        (data_dir / "values" / "README.md").write_text("# Summary\nJust a summary.")
        content = gather_layer_content(data_dir, "values")
        assert "Just a summary" in content

    def test_items_only_layer(self, data_dir: Path):
        """A layer with only items (no narrative) is handled."""
        (data_dir / "values" / "item1.md").write_text(
            "---\ntitle: Item One\n---\nContent here."
        )
        content = gather_layer_content(data_dir, "values")
        assert "Item One" in content
        assert "Content here" in content

    def test_formatted_as_single_text(self, populated_data_dir: Path):
        """The output is a single text string, not a list."""
        content = gather_layer_content(populated_data_dir, "values")
        assert isinstance(content, str)

    def test_includes_status_in_item_header(self, populated_data_dir: Path):
        """Item headers include the status from frontmatter."""
        content = gather_layer_content(populated_data_dir, "values")
        assert "Status: active" in content

    def test_includes_section_headers(self, populated_data_dir: Path):
        """The content uses markdown headers for structure."""
        content = gather_layer_content(populated_data_dir, "values")
        assert "## Narrative Summary" in content
        assert "## Items" in content


class TestGatherCrossLayerContext:
    """Test the gather_cross_layer_context function."""

    def test_includes_layer_below(self, populated_data_dir: Path):
        """Cross-layer context includes the layer below."""
        context = gather_cross_layer_context(
            populated_data_dir, "situational-awareness"
        )
        assert "Values" in context

    def test_includes_layer_above(self, populated_data_dir: Path):
        """Cross-layer context includes the layer above."""
        # Add strategic objectives narrative
        (populated_data_dir / "strategic-objectives" / "README.md").write_text(
            "# Strategic Objectives\n\nStrategic goals for Finland."
        )
        context = gather_cross_layer_context(
            populated_data_dir, "situational-awareness"
        )
        assert "Strategic Objectives" in context

    def test_bottom_layer_has_no_below(self, populated_data_dir: Path):
        """The bottom layer (philosophy) has no layer below."""
        context = gather_cross_layer_context(populated_data_dir, "philosophy")
        # Should still mention the layer above
        assert "Layer Above" in context
        assert "Layer Below" not in context

    def test_top_layer_has_no_above(self, populated_data_dir: Path):
        """The top layer (policies) has no layer above."""
        (populated_data_dir / "tactical-objectives" / "README.md").write_text(
            "# Tactical\n\nTactical objectives."
        )
        context = gather_cross_layer_context(populated_data_dir, "policies")
        assert "Layer Below" in context
        assert "Layer Above" not in context

    def test_invalid_layer_returns_fallback(self, populated_data_dir: Path):
        """An invalid layer slug returns a fallback message."""
        context = gather_cross_layer_context(populated_data_dir, "nonexistent")
        assert "No cross-layer context available" in context


class TestGatherContextBelow:
    """Test the gather_context_below function."""

    def test_values_returns_empty_string(self, data_dir: Path):
        """Values is the bottom layer — no layers below, returns empty string."""
        result = gather_context_below(data_dir, "philosophy")
        assert result == ""

    def test_values_includes_philosophy_content(self, populated_data_dir: Path):
        """Values layer context includes content from the philosophy layer below."""
        # Add philosophy content
        (populated_data_dir / "philosophy" / "README.md").write_text(
            "# Philosophy\n\nEpistemological commitments for policy reasoning."
        )
        result = gather_context_below(populated_data_dir, "values")
        assert "Philosophy" in result

    def test_sa_includes_values_content(self, populated_data_dir: Path):
        """SA layer context includes content from the values layer below."""
        result = gather_context_below(populated_data_dir, "situational-awareness")
        assert "Values" in result
        assert "National Security" in result
        assert "Economic Prosperity" in result

    def test_strategic_includes_values_and_sa(self, populated_data_dir: Path):
        """Strategic objectives context includes values and SA content."""
        result = gather_context_below(
            populated_data_dir, "strategic-objectives"
        )
        # Values content
        assert "Values" in result
        assert "National Security" in result
        # SA content
        assert "Situational Awareness" in result

    def test_policies_includes_all_five_layers(self, populated_data_dir: Path):
        """Policies context includes content from all 5 layers below."""
        # Add philosophy content
        (populated_data_dir / "philosophy" / "README.md").write_text(
            "# Philosophy\n\nEpistemological commitments."
        )
        (populated_data_dir / "philosophy" / "axiom-1.md").write_text(
            "---\ntitle: Axiom One\nstatus: active\n---\nFirst normative axiom."
        )
        # Add strategic and tactical content
        (populated_data_dir / "strategic-objectives" / "README.md").write_text(
            "# Strategic\n\nStrategic goals."
        )
        (populated_data_dir / "strategic-objectives" / "goal-1.md").write_text(
            "---\ntitle: Goal One\nstatus: active\n---\nFirst strategic goal."
        )
        (populated_data_dir / "tactical-objectives" / "README.md").write_text(
            "# Tactical\n\nTactical objectives."
        )
        (populated_data_dir / "tactical-objectives" / "tactic-1.md").write_text(
            "---\ntitle: Tactic One\nstatus: active\n---\nFirst tactical objective."
        )

        result = gather_context_below(populated_data_dir, "policies")
        assert "Philosophy" in result
        assert "Values" in result
        assert "Situational Awareness" in result
        assert "Strategic Objectives" in result
        assert "Tactical Objectives" in result
        assert "Axiom One" in result
        assert "Goal One" in result
        assert "Tactic One" in result

    def test_layer_sections_have_display_name_headings(
        self, populated_data_dir: Path
    ):
        """Each layer section has a heading with the layer's display name."""
        result = gather_context_below(
            populated_data_dir, "situational-awareness"
        )
        assert "## Values Layer" in result

    def test_empty_layers_below_produce_no_errors(self, data_dir: Path):
        """Empty layers below do not cause errors — they just produce no content."""
        # SA layer with empty values below (no items, no narrative)
        result = gather_context_below(data_dir, "situational-awareness")
        # Should not raise, should produce some output (the layer heading is still there)
        assert isinstance(result, str)

    def test_invalid_layer_slug_raises_value_error(self, data_dir: Path):
        """An invalid layer slug raises ValueError."""
        with pytest.raises(ValueError, match="Invalid layer slug"):
            gather_context_below(data_dir, "nonexistent-layer")

    def test_content_includes_narratives_and_items(
        self, populated_data_dir: Path
    ):
        """Context includes both narrative summaries and items when they exist."""
        result = gather_context_below(
            populated_data_dir, "situational-awareness"
        )
        # Values layer has both narrative and items
        assert "Finland's core national values" in result
        assert "National Security" in result
        assert "paramount concern" in result


class TestCheckPrerequisites:
    """Test the check_prerequisites function."""

    def test_philosophy_returns_empty_list(self, data_dir: Path):
        """Philosophy is the bottom layer — no prerequisites, returns empty list."""
        result = check_prerequisites(data_dir, "philosophy")
        assert result == []

    def test_values_returns_empty_when_philosophy_has_items(
        self, populated_data_dir: Path
    ):
        """Values prerequisites are met when the philosophy layer has items."""
        # Add philosophy item
        (populated_data_dir / "philosophy" / "epistemology.md").write_text(
            "---\ntitle: Epistemology\nstatus: active\n---\nHow we know things."
        )
        result = check_prerequisites(populated_data_dir, "values")
        assert result == []

    def test_values_returns_philosophy_when_empty(self, data_dir: Path):
        """Values returns ['philosophy'] when the philosophy layer has no items."""
        result = check_prerequisites(data_dir, "values")
        assert result == ["philosophy"]

    def test_sa_returns_empty_when_philosophy_and_values_have_items(
        self, populated_data_dir: Path
    ):
        """SA prerequisites are met when the philosophy and values layers have items."""
        # Add philosophy item
        (populated_data_dir / "philosophy" / "epistemology.md").write_text(
            "---\ntitle: Epistemology\nstatus: active\n---\nHow we know things."
        )
        result = check_prerequisites(populated_data_dir, "situational-awareness")
        assert result == []

    def test_sa_returns_philosophy_and_values_when_empty(self, data_dir: Path):
        """SA returns ['philosophy', 'values'] when both layers have no items."""
        result = check_prerequisites(data_dir, "situational-awareness")
        assert result == ["philosophy", "values"]

    def test_strategic_returns_all_empty_layers(self, data_dir: Path):
        """Strategic-objectives returns all empty layers below when none are populated."""
        result = check_prerequisites(data_dir, "strategic-objectives")
        assert "philosophy" in result
        assert "values" in result
        assert "situational-awareness" in result

    def test_strategic_returns_empty_when_all_populated(
        self, populated_data_dir: Path
    ):
        """Strategic-objectives returns empty list when all layers below have items."""
        # Add philosophy item
        (populated_data_dir / "philosophy" / "epistemology.md").write_text(
            "---\ntitle: Epistemology\nstatus: active\n---\nHow we know things."
        )
        # values already has items; add SA items
        (populated_data_dir / "situational-awareness" / "threat-1.md").write_text(
            "---\ntitle: Threat One\nstatus: active\n---\nA geopolitical threat."
        )
        result = check_prerequisites(
            populated_data_dir, "strategic-objectives"
        )
        assert result == []

    def test_policies_with_partial_population(self, populated_data_dir: Path):
        """Policies with only some layers populated returns the empty slugs."""
        # values has items, philosophy/SA/strategic/tactical are empty
        result = check_prerequisites(populated_data_dir, "policies")
        # values is populated, others are NOT
        assert "philosophy" in result
        assert "values" not in result
        assert "situational-awareness" in result
        assert "strategic-objectives" in result
        assert "tactical-objectives" in result

    def test_invalid_layer_slug_raises_value_error(self, data_dir: Path):
        """An invalid layer slug raises ValueError."""
        with pytest.raises(ValueError, match="Invalid layer slug"):
            check_prerequisites(data_dir, "nonexistent-layer")
