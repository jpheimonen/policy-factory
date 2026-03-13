"""Tests for the prompt construction helper."""

from pathlib import Path

import pytest

from policy_factory.agent.prompts import build_agent_prompt
from policy_factory.prompts.loader import PromptLoader

ANTI_SLOP_CONTENT = "Anti-slop preamble for tests."


class TestBuildAgentPrompt:
    """Tests for the build_agent_prompt() function."""

    @pytest.fixture(autouse=True)
    def setup_tmp_prompts(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Set up temporary prompts directory with test files."""
        import policy_factory.prompts.loader as loader_mod

        # Create anti-slop section
        (tmp_path / "sections").mkdir()
        (tmp_path / "sections" / "anti-slop.md").write_text(ANTI_SLOP_CONTENT)

        # Create category
        (tmp_path / "generators").mkdir()
        (tmp_path / "generators" / "values.md").write_text(
            "Generate values for {layer_slug}."
        )
        (tmp_path / "generators" / "no_vars.md").write_text(
            "Static generator content."
        )

        # Create a custom loader and patch the singleton
        test_loader = PromptLoader(tmp_path)
        monkeypatch.setattr(loader_mod, "_default_loader", test_loader)

    def test_prepends_anti_slop_preamble(self) -> None:
        """The anti-slop preamble is prepended to every prompt."""
        result = build_agent_prompt("generators", "values", layer_slug="values")
        assert result.startswith(ANTI_SLOP_CONTENT)

    def test_template_content_follows_preamble(self) -> None:
        """Template content appears after the preamble."""
        result = build_agent_prompt("generators", "values", layer_slug="values")
        assert "Generate values for values." in result
        preamble_end = result.index(ANTI_SLOP_CONTENT) + len(ANTI_SLOP_CONTENT)
        template_start = result.index("Generate values for values.")
        assert template_start > preamble_end

    def test_double_newline_separator(self) -> None:
        """Preamble and template body are separated by a double newline."""
        result = build_agent_prompt("generators", "values", layer_slug="values")
        expected = ANTI_SLOP_CONTENT + "\n\n" + "Generate values for values."
        assert result == expected

    def test_substitutes_template_variables(self) -> None:
        """Template variables are substituted in the body."""
        result = build_agent_prompt("generators", "values", layer_slug="my-layer")
        assert "my-layer" in result
        assert "{layer_slug}" not in result

    def test_preamble_not_subject_to_variable_substitution(self) -> None:
        """The anti-slop preamble is loaded without variable substitution."""
        # The preamble content should appear exactly as written,
        # even if the template has variables
        result = build_agent_prompt("generators", "values", layer_slug="test")
        assert result.startswith(ANTI_SLOP_CONTENT)

    def test_no_variables_template(self) -> None:
        """Templates without variables still get the preamble."""
        result = build_agent_prompt("generators", "no_vars")
        assert result.startswith(ANTI_SLOP_CONTENT)
        assert "Static generator content." in result

    def test_nonexistent_template_raises(self) -> None:
        """FileNotFoundError raised when the template file is missing."""
        with pytest.raises(FileNotFoundError):
            build_agent_prompt("generators", "nonexistent")

    def test_result_structure(self) -> None:
        """Result is exactly: preamble + double newline + substituted body."""
        result = build_agent_prompt("generators", "values", layer_slug="test")
        assert result == ANTI_SLOP_CONTENT + "\n\n" + "Generate values for test."


class TestBuildAgentPromptMissingSection:
    """Tests for missing anti-slop section file."""

    @pytest.fixture(autouse=True)
    def setup_tmp_prompts_no_section(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Set up temporary prompts directory WITHOUT anti-slop section."""
        import policy_factory.prompts.loader as loader_mod

        # Create category but NO sections directory
        (tmp_path / "generators").mkdir()
        (tmp_path / "generators" / "values.md").write_text(
            "Generate values for {layer_slug}."
        )

        test_loader = PromptLoader(tmp_path)
        monkeypatch.setattr(loader_mod, "_default_loader", test_loader)

    def test_missing_anti_slop_section_raises(self) -> None:
        """FileNotFoundError raised when anti-slop section file is missing."""
        with pytest.raises(FileNotFoundError):
            build_agent_prompt("generators", "values", layer_slug="test")


class TestBuildAgentPromptWithRealPrompts:
    """Tests using the real prompt files to verify integration."""

    @pytest.fixture(autouse=True)
    def reset_loader(self) -> None:
        """Reset the singleton loader to use real prompt files."""
        import policy_factory.prompts.loader as loader_mod

        original = loader_mod._default_loader
        loader_mod._default_loader = None
        yield
        loader_mod._default_loader = original

    def _get_real_preamble(self) -> str:
        """Load the real anti-slop preamble content for assertions."""
        from policy_factory.prompts import load_section

        return load_section("anti-slop")

    def test_real_generator_prompt_loads_with_preamble(self) -> None:
        """Real generator prompt loads successfully with anti-slop preamble."""
        result = build_agent_prompt(
            "generators",
            "values",
            layer_content="test content",
            feedback_memos="no memos",
            cross_layer_context="no context",
        )
        preamble = self._get_real_preamble()
        assert result.startswith(preamble)
        assert "\n\n" in result[len(preamble):]

    def test_real_critic_prompt_loads_with_preamble(self) -> None:
        """Real critic prompt loads successfully with anti-slop preamble."""
        result = build_agent_prompt(
            "critics",
            "realist",
            layer_slug="strategic-objectives",
            layer_content="test content",
            cross_layer_context="no context",
        )
        preamble = self._get_real_preamble()
        assert result.startswith(preamble)
        assert "Realist" in result

    def test_real_heartbeat_prompt_loads_with_preamble(self) -> None:
        """Real heartbeat prompt loads successfully with anti-slop preamble."""
        result = build_agent_prompt(
            "heartbeat",
            "skim",
            current_date="2025-01-01",
            sa_summary="test sa summary",
            news_headlines="test headlines",
        )
        preamble = self._get_real_preamble()
        assert result.startswith(preamble)

    def test_real_seed_prompt_loads_with_preamble(self) -> None:
        """Real seed prompt loads successfully with anti-slop preamble."""
        result = build_agent_prompt("seed", "values")
        preamble = self._get_real_preamble()
        assert result.startswith(preamble)

    def test_anti_slop_section_exists_and_nonempty(self) -> None:
        """The anti-slop section file exists and has content."""
        preamble = self._get_real_preamble()
        assert len(preamble) > 0

    def test_anti_slop_has_no_template_variables(self) -> None:
        """The anti-slop preamble has no {variable} placeholders."""
        import re

        preamble = self._get_real_preamble()
        # Match single { followed by word chars and }, but not {{ or }}
        placeholders = re.findall(r"(?<!\{)\{(\w+)\}(?!\})", preamble)
        assert placeholders == [], (
            f"Found placeholders in anti-slop preamble: {placeholders}"
        )
