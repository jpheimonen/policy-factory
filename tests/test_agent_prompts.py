"""Tests for the prompt construction helper."""

from pathlib import Path

import pytest

from policy_factory.agent.prompts import build_agent_prompt
from policy_factory.prompts.loader import PromptLoader


class TestBuildAgentPrompt:
    """Tests for the build_agent_prompt() function."""

    @pytest.fixture(autouse=True)
    def setup_tmp_prompts(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Set up temporary prompts directory with test files."""
        import policy_factory.prompts.loader as loader_mod

        # Create section
        (tmp_path / "sections").mkdir()
        (tmp_path / "sections" / "meditation.md").write_text(
            "Meditation: Count down 10 to 1."
        )

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

    def test_prepends_meditation_preamble(self) -> None:
        result = build_agent_prompt("generators", "values", layer_slug="values")
        assert result.startswith("Meditation: Count down 10 to 1.")

    def test_includes_agent_template(self) -> None:
        result = build_agent_prompt("generators", "values", layer_slug="values")
        assert "Generate values for values." in result

    def test_separator_between_sections(self) -> None:
        result = build_agent_prompt("generators", "values", layer_slug="values")
        assert "\n\n---\n\n" in result

    def test_substitutes_template_variables(self) -> None:
        result = build_agent_prompt("generators", "values", layer_slug="my-layer")
        assert "my-layer" in result
        assert "{layer_slug}" not in result

    def test_no_variables_template(self) -> None:
        result = build_agent_prompt("generators", "no_vars")
        assert "Static generator content." in result
        assert "Meditation" in result

    def test_nonexistent_template_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            build_agent_prompt("generators", "nonexistent")

    def test_meditation_always_first(self) -> None:
        result = build_agent_prompt("generators", "values", layer_slug="values")
        med_pos = result.index("Meditation")
        gen_pos = result.index("Generate values")
        assert med_pos < gen_pos


class TestBuildAgentPromptWithRealPrompts:
    """Tests using the real prompt files to verify integration."""

    def test_real_generator_prompt_includes_meditation(self) -> None:
        """Verify real prompt files work with build_agent_prompt."""
        # Reset singleton to use real prompts
        import policy_factory.prompts.loader as loader_mod
        original = loader_mod._default_loader
        loader_mod._default_loader = None
        try:
            result = build_agent_prompt(
                "generators",
                "values",
                layer_content="test content",
                feedback_memos="no memos",
                cross_layer_context="no context",
            )
            # Should contain meditation content
            assert "10" in result
            assert "bias" in result.lower() or "Bias" in result
            # Should contain generator content
            assert "Values" in result
        finally:
            loader_mod._default_loader = original

    def test_real_critic_prompt_includes_meditation(self) -> None:
        """Verify critic prompts work with build_agent_prompt."""
        import policy_factory.prompts.loader as loader_mod
        original = loader_mod._default_loader
        loader_mod._default_loader = None
        try:
            result = build_agent_prompt(
                "critics",
                "realist",
                layer_slug="strategic-objectives",
                layer_content="test content",
                cross_layer_context="no context",
            )
            assert "Realist" in result
            assert "security" in result.lower()
        finally:
            loader_mod._default_loader = original
