"""Tests for the PromptLoader and convenience functions."""

from pathlib import Path

import pytest

from policy_factory.prompts import PromptLoader, load_section, load_sections
from policy_factory.prompts.loader import get_prompt_loader

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_prompts(tmp_path: Path) -> Path:
    """Create a temporary prompts directory with test files."""
    # Create category directory
    (tmp_path / "generators").mkdir()
    (tmp_path / "generators" / "values.md").write_text(
        "Generate values for {layer_slug} with {context}."
    )
    (tmp_path / "generators" / "simple.md").write_text(
        "No variables here."
    )
    (tmp_path / "generators" / "braces.md").write_text(
        "Use {{literal_braces}} and {variable}."
    )

    # Create sections directory
    (tmp_path / "sections").mkdir()
    (tmp_path / "sections" / "anti-slop.md").write_text(
        "Anti-slop preamble content."
    )
    (tmp_path / "sections" / "core.md").write_text(
        "Core section content."
    )

    return tmp_path


@pytest.fixture
def loader(tmp_prompts: Path) -> PromptLoader:
    """Provide a PromptLoader pointing at the temporary prompts directory."""
    return PromptLoader(tmp_prompts)


# ---------------------------------------------------------------------------
# PromptLoader.load()
# ---------------------------------------------------------------------------


class TestPromptLoaderLoad:
    """Tests for PromptLoader.load()."""

    def test_load_returns_content(self, loader: PromptLoader) -> None:
        result = loader.load("generators", "simple")
        assert result == "No variables here."

    def test_load_substitutes_variables(self, loader: PromptLoader) -> None:
        result = loader.load(
            "generators", "values", layer_slug="values", context="test context"
        )
        assert "values" in result
        assert "test context" in result
        assert "{layer_slug}" not in result
        assert "{context}" not in result

    def test_load_escapes_double_braces(self, loader: PromptLoader) -> None:
        result = loader.load("generators", "braces", variable="injected")
        assert "{literal_braces}" in result
        assert "injected" in result

    def test_load_nonexistent_raises_file_not_found(self, loader: PromptLoader) -> None:
        with pytest.raises(FileNotFoundError, match="Prompt not found"):
            loader.load("generators", "nonexistent")

    def test_load_nonexistent_category_raises_file_not_found(self, loader: PromptLoader) -> None:
        with pytest.raises(FileNotFoundError):
            loader.load("nonexistent_category", "values")

    def test_load_no_variables_returns_raw_content(self, loader: PromptLoader) -> None:
        result = loader.load("generators", "simple")
        assert result == "No variables here."


# ---------------------------------------------------------------------------
# PromptLoader.load_section()
# ---------------------------------------------------------------------------


class TestPromptLoaderLoadSection:
    """Tests for PromptLoader.load_section()."""

    def test_load_section_returns_content(self, loader: PromptLoader) -> None:
        result = loader.load_section("anti-slop")
        assert result == "Anti-slop preamble content."

    def test_load_section_nonexistent_raises_file_not_found(self, loader: PromptLoader) -> None:
        with pytest.raises(FileNotFoundError, match="Prompt section not found"):
            loader.load_section("nonexistent")


# ---------------------------------------------------------------------------
# PromptLoader.load_sections()
# ---------------------------------------------------------------------------


class TestPromptLoaderLoadSections:
    """Tests for PromptLoader.load_sections()."""

    def test_load_sections_concatenates_with_double_newlines(self, loader: PromptLoader) -> None:
        result = loader.load_sections(["anti-slop", "core"])
        assert "Anti-slop preamble content." in result
        assert "Core section content." in result
        assert "\n\n" in result

    def test_load_sections_preserves_order(self, loader: PromptLoader) -> None:
        result = loader.load_sections(["anti-slop", "core"])
        slop_idx = result.index("Anti-slop")
        core_idx = result.index("Core section")
        assert slop_idx < core_idx

    def test_load_sections_empty_list_returns_empty_string(self, loader: PromptLoader) -> None:
        result = loader.load_sections([])
        assert result == ""

    def test_load_sections_single_item_no_separator(self, loader: PromptLoader) -> None:
        result = loader.load_sections(["anti-slop"])
        assert result == "Anti-slop preamble content."

    def test_load_sections_nonexistent_raises_file_not_found(self, loader: PromptLoader) -> None:
        with pytest.raises(FileNotFoundError):
            loader.load_sections(["anti-slop", "nonexistent"])


# ---------------------------------------------------------------------------
# Module-level convenience functions
# ---------------------------------------------------------------------------


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_get_prompt_loader_returns_singleton(self) -> None:
        loader1 = get_prompt_loader()
        loader2 = get_prompt_loader()
        assert loader1 is loader2

    def test_get_prompt_loader_has_default_prompts_dir(self) -> None:
        loader = get_prompt_loader()
        # The default directory should be the package prompts directory
        assert loader.prompts_dir.exists()

    def test_load_prompt_loads_from_default_loader(self) -> None:
        # This tests against the real prompts directory
        # The anti-slop section should exist
        result = load_section("anti-slop")
        assert "Analytical Standards" in result

    def test_load_sections_from_default_loader(self) -> None:
        result = load_sections(["anti-slop"])
        assert len(result) > 0


# ---------------------------------------------------------------------------
# Default prompts directory — verify all expected files exist
# ---------------------------------------------------------------------------


class TestAllPromptFilesExist:
    """Verify that all expected prompt files are present in the package."""

    @pytest.fixture
    def prompts_dir(self) -> Path:
        """Get the default prompts directory."""
        return Path(__file__).parent.parent / "src" / "policy_factory" / "prompts"

    @pytest.mark.parametrize(
        "path",
        [
            "sections/anti-slop.md",
            "generators/values.md",
            "generators/situational-awareness.md",
            "generators/strategic.md",
            "generators/tactical.md",
            "generators/policies.md",
            "critics/realist.md",
            "critics/liberal-institutionalist.md",
            "critics/nationalist-conservative.md",
            "critics/social-democratic.md",
            "critics/libertarian.md",
            "critics/green-ecological.md",
            "synthesis/synthesis.md",
            "heartbeat/skim.md",
            "heartbeat/triage.md",
            "heartbeat/sa-update.md",
            "classifier/classifier.md",
            "ideas/evaluate.md",
            "ideas/generate.md",
            "seed/seed.md",
        ],
    )
    def test_prompt_file_exists(self, prompts_dir: Path, path: str) -> None:
        full_path = prompts_dir / path
        assert full_path.exists(), f"Missing prompt file: {path}"
        content = full_path.read_text()
        assert len(content) > 0, f"Empty prompt file: {path}"
