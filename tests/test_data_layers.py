"""Tests for the layer directory utilities (data/layers.py)."""

from pathlib import Path

import pytest

from policy_factory.data.layers import (
    LAYER_SLUGS,
    LAYERS,
    ItemSummary,
    LayerInfo,
    delete_item,
    get_layer,
    get_layer_path,
    list_items,
    read_item,
    read_narrative,
    resolve_references,
    validate_layer_slug,
    write_item,
    write_narrative,
)
from policy_factory.data.markdown import write_markdown

# ---------------------------------------------------------------------------
# Layer definitions
# ---------------------------------------------------------------------------


class TestLayerDefinitions:
    """Tests for layer metadata and validation."""

    def test_six_layers_defined(self) -> None:
        assert len(LAYERS) == 6

    def test_all_slugs_valid(self) -> None:
        expected = {
            "philosophy",
            "values",
            "situational-awareness",
            "strategic-objectives",
            "tactical-objectives",
            "policies",
        }
        assert LAYER_SLUGS == expected

    def test_get_layer_valid(self) -> None:
        layer = get_layer("philosophy")
        assert layer is not None
        assert isinstance(layer, LayerInfo)
        assert layer.slug == "philosophy"
        assert layer.display_name == "Philosophy"
        assert layer.position == 1

    def test_get_layer_values(self) -> None:
        layer = get_layer("values")
        assert layer is not None
        assert isinstance(layer, LayerInfo)
        assert layer.slug == "values"
        assert layer.display_name == "Values"
        assert layer.position == 2

    def test_get_layer_invalid(self) -> None:
        assert get_layer("nonexistent") is None

    def test_validate_layer_slug_valid(self) -> None:
        for slug in LAYER_SLUGS:
            info = validate_layer_slug(slug)
            assert info.slug == slug

    def test_validate_layer_slug_invalid(self) -> None:
        with pytest.raises(ValueError, match="Invalid layer slug"):
            validate_layer_slug("not-a-layer")

    def test_layer_ordering(self) -> None:
        """Layers should be ordered bottom (1) to top (6)."""
        positions = [layer.position for layer in LAYERS]
        assert positions == [1, 2, 3, 4, 5, 6]

    def test_get_layer_path(self, tmp_path: Path) -> None:
        path = get_layer_path(tmp_path, "values")
        assert path == tmp_path / "values"

    def test_get_layer_path_invalid(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            get_layer_path(tmp_path, "nope")


# ---------------------------------------------------------------------------
# Item listing
# ---------------------------------------------------------------------------


class TestListItems:
    """Tests for listing items in a layer directory."""

    def test_list_items_returns_md_files(self, tmp_path: Path) -> None:
        layer_dir = tmp_path / "values"
        layer_dir.mkdir()
        write_markdown(
            layer_dir / "item-a.md",
            {"title": "Item A", "status": "active", "last_modified": "2024-01-01T00:00:00"},
            "Body A.",
        )
        write_markdown(
            layer_dir / "item-b.md",
            {"title": "Item B", "status": "draft", "last_modified": "2024-01-02T00:00:00"},
            "Body B.",
        )

        items = list_items(tmp_path, "values")
        assert len(items) == 2
        assert all(isinstance(item, ItemSummary) for item in items)
        # Sorted by title
        assert items[0].title == "Item A"
        assert items[1].title == "Item B"

    def test_list_items_excludes_readme(self, tmp_path: Path) -> None:
        layer_dir = tmp_path / "values"
        layer_dir.mkdir()
        (layer_dir / "README.md").write_text("# Summary", encoding="utf-8")
        write_markdown(
            layer_dir / "item.md",
            {"title": "Item"},
            "Body.",
        )

        items = list_items(tmp_path, "values")
        assert len(items) == 1
        assert items[0].filename == "item.md"

    def test_list_items_empty_directory(self, tmp_path: Path) -> None:
        layer_dir = tmp_path / "values"
        layer_dir.mkdir()
        items = list_items(tmp_path, "values")
        assert items == []

    def test_list_items_nonexistent_directory(self, tmp_path: Path) -> None:
        """Listing a non-existent directory returns empty list (no error)."""
        items = list_items(tmp_path, "values")
        assert items == []


# ---------------------------------------------------------------------------
# Read / write / delete item
# ---------------------------------------------------------------------------


class TestItemCrud:
    """Tests for reading, writing, and deleting individual items."""

    def test_read_item(self, tmp_path: Path) -> None:
        layer_dir = tmp_path / "values"
        layer_dir.mkdir()
        write_markdown(
            layer_dir / "test.md",
            {"title": "Test"},
            "Body text.",
        )

        fm, body = read_item(tmp_path, "values", "test.md")
        assert fm["title"] == "Test"
        assert body == "Body text."

    def test_read_item_not_found(self, tmp_path: Path) -> None:
        (tmp_path / "values").mkdir()
        with pytest.raises(FileNotFoundError):
            read_item(tmp_path, "values", "missing.md")

    def test_read_item_invalid_slug(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            read_item(tmp_path, "invalid", "test.md")

    def test_write_item_sets_last_modified(self, tmp_path: Path) -> None:
        write_item(
            tmp_path,
            "values",
            "test.md",
            {"title": "Test"},
            "Body.",
            modified_by="user@test.com",
        )

        fm, body = read_item(tmp_path, "values", "test.md")
        assert fm["title"] == "Test"
        assert "last_modified" in fm
        assert fm["last_modified_by"] == "user@test.com"
        assert body == "Body."

    def test_write_item_creates_directory(self, tmp_path: Path) -> None:
        """Writing to a non-existent layer dir should create it."""
        write_item(tmp_path, "values", "test.md", {"title": "Test"}, "Body.")
        assert (tmp_path / "values" / "test.md").exists()

    def test_delete_item(self, tmp_path: Path) -> None:
        layer_dir = tmp_path / "values"
        layer_dir.mkdir()
        target = layer_dir / "test.md"
        target.write_text("content", encoding="utf-8")
        assert target.exists()

        delete_item(tmp_path, "values", "test.md")
        assert not target.exists()

    def test_delete_item_idempotent(self, tmp_path: Path) -> None:
        """Deleting a non-existent file should not raise."""
        (tmp_path / "values").mkdir()
        delete_item(tmp_path, "values", "nonexistent.md")  # Should not raise


# ---------------------------------------------------------------------------
# Narrative summary (README.md)
# ---------------------------------------------------------------------------


class TestNarrative:
    """Tests for reading and writing layer narrative summaries."""

    def test_read_narrative_exists(self, tmp_path: Path) -> None:
        layer_dir = tmp_path / "values"
        layer_dir.mkdir()
        (layer_dir / "README.md").write_text("# Summary\nContent.", encoding="utf-8")

        content = read_narrative(tmp_path, "values")
        assert content == "# Summary\nContent."

    def test_read_narrative_missing(self, tmp_path: Path) -> None:
        (tmp_path / "values").mkdir()
        content = read_narrative(tmp_path, "values")
        assert content == ""

    def test_write_narrative(self, tmp_path: Path) -> None:
        write_narrative(tmp_path, "values", "# Updated Summary\nNew content.")
        content = read_narrative(tmp_path, "values")
        assert content == "# Updated Summary\nNew content."

    def test_write_narrative_creates_dir(self, tmp_path: Path) -> None:
        write_narrative(tmp_path, "values", "# Summary")
        assert (tmp_path / "values" / "README.md").exists()


# ---------------------------------------------------------------------------
# Cross-layer reference resolution
# ---------------------------------------------------------------------------


class TestReferences:
    """Tests for cross-layer reference resolution."""

    def _setup_refs(self, tmp_path: Path) -> None:
        """Create a test scenario with cross-layer references."""
        # Value item
        write_markdown(
            tmp_path / "values" / "security.md",
            {"title": "National Security"},
            "Security body.",
        )
        write_markdown(
            tmp_path / "values" / "economy.md",
            {"title": "Economic Prosperity"},
            "Economy body.",
        )

        # Strategic objective referencing values
        write_markdown(
            tmp_path / "strategic-objectives" / "nato-integration.md",
            {
                "title": "NATO Integration",
                "references": [
                    "values/security.md",
                    "values/economy.md",
                ],
            },
            "NATO body.",
        )

        # Another strategic objective referencing security only
        write_markdown(
            tmp_path / "strategic-objectives" / "cyber-defence.md",
            {
                "title": "Cyber Defence",
                "references": [
                    "values/security.md",
                ],
            },
            "Cyber body.",
        )

    def test_forward_references(self, tmp_path: Path) -> None:
        self._setup_refs(tmp_path)
        forward, _backward = resolve_references(
            tmp_path, "strategic-objectives", "nato-integration.md"
        )
        assert len(forward) == 2
        slugs = {ref.layer_slug for ref in forward}
        assert slugs == {"values"}
        titles = {ref.title for ref in forward}
        assert "National Security" in titles
        assert "Economic Prosperity" in titles

    def test_backward_references(self, tmp_path: Path) -> None:
        self._setup_refs(tmp_path)
        _forward, backward = resolve_references(
            tmp_path, "values", "security.md"
        )
        assert len(backward) == 2
        titles = {ref.title for ref in backward}
        assert "NATO Integration" in titles
        assert "Cyber Defence" in titles

    def test_no_references(self, tmp_path: Path) -> None:
        self._setup_refs(tmp_path)
        forward, backward = resolve_references(
            tmp_path, "values", "economy.md"
        )
        # economy.md has no forward refs
        assert forward == []
        # but NATO integration references it (backward)
        assert len(backward) == 1
        assert backward[0].title == "NATO Integration"

    def test_empty_references(self, tmp_path: Path) -> None:
        """An item with no references field returns empty lists."""
        write_markdown(
            tmp_path / "policies" / "isolated.md",
            {"title": "Isolated Policy"},
            "No refs.",
        )
        forward, backward = resolve_references(tmp_path, "policies", "isolated.md")
        assert forward == []
        assert backward == []

    def test_nonexistent_item(self, tmp_path: Path) -> None:
        """Resolving references for a non-existent item returns empty lists."""
        forward, backward = resolve_references(tmp_path, "values", "missing.md")
        assert forward == []
        assert backward == []
