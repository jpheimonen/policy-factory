"""Tests for layer content gathering utilities."""

from pathlib import Path

import pytest

from policy_factory.cascade.content import (
    gather_cross_layer_context,
    gather_layer_content,
)


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """Create a temporary data directory with layer subdirectories."""
    for layer in [
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
        """The bottom layer (values) has no layer below."""
        context = gather_cross_layer_context(populated_data_dir, "values")
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
