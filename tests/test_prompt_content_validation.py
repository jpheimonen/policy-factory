"""Prompt content validation tests — regression guard for the anti-slop overhaul.

These tests scan all prompt files under src/policy_factory/prompts/ to verify:
1. No prompt contains "tech policy" or "technology policy" (case-insensitive)
2. The anti-slop section file exists and is non-empty
3. Every prompt file loads successfully via build_agent_prompt() with its
   required template variables (guards against syntax errors in placeholders)
"""

from pathlib import Path

import pytest

from policy_factory.agent.prompts import build_agent_prompt
from policy_factory.prompts import load_section

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PROMPTS_DIR = Path(__file__).parent.parent / "src" / "policy_factory" / "prompts"

# All prompt markdown files (excluding sections/) with their categories
_ALL_PROMPT_FILES: list[tuple[str, str]] = []

for md_file in sorted(PROMPTS_DIR.rglob("*.md")):
    rel = md_file.relative_to(PROMPTS_DIR)
    parts = rel.parts
    # Skip sections/ — those are preambles, not full prompts
    if parts[0] == "sections":
        continue
    category = parts[0]
    name = rel.stem
    _ALL_PROMPT_FILES.append((category, name))


# Template variables required by each prompt, keyed by (category, name).
# Every prompt in the system must be listed here so the load test covers it.
_TEMPLATE_VARS: dict[tuple[str, str], dict[str, str]] = {
    # Heartbeat
    ("heartbeat", "skim"): {
        "current_date": "2025-01-01",
        "sa_summary": "test sa summary",
        "news_headlines": "test headlines",
    },
    ("heartbeat", "triage"): {
        "flagged_items": "test flagged items",
        "sa_summary": "test sa summary",
    },
    ("heartbeat", "sa-update"): {
        "triage_assessment": "test triage assessment",
        "sa_content": "test sa content",
        "feedback_memos": "test feedback memos",
    },
    # Classifier
    ("classifier", "classifier"): {
        "layer_summaries": "test layer summaries",
        "user_input": "test user input",
    },
    # Ideas
    ("ideas", "evaluate"): {
        "idea_text": "test idea text",
        "values_summary": "test values summary",
        "sa_summary": "test sa summary",
        "strategic_summary": "test strategic summary",
        "tactical_summary": "test tactical summary",
        "policies_summary": "test policies summary",
    },
    ("ideas", "generate"): {
        "values_summary": "test values summary",
        "sa_summary": "test sa summary",
        "strategic_summary": "test strategic summary",
        "tactical_summary": "test tactical summary",
        "policies_summary": "test policies summary",
        "scoping_context": "test scoping context",
    },
    # Seed
    ("seed", "philosophy"): {},  # No template variables
    ("seed", "values"): {},
    ("seed", "seed"): {
        "current_date": "2025-01-01",
        "values_content": "test values content",
    },
    ("seed", "strategic"): {
        "current_date": "2025-01-01",
        "context_below": "test context below",
    },
    ("seed", "tactical"): {
        "current_date": "2025-01-01",
        "context_below": "test context below",
    },
    ("seed", "policies"): {
        "current_date": "2025-01-01",
        "context_below": "test context below",
    },
    # Generators
    ("generators", "philosophy"): {
        "layer_content": "test layer content",
        "feedback_memos": "test feedback memos",
        "cross_layer_context": "test cross-layer context",
    },
    ("generators", "values"): {
        "layer_content": "test layer content",
        "feedback_memos": "test feedback memos",
        "cross_layer_context": "test cross-layer context",
    },
    ("generators", "situational-awareness"): {
        "upstream_content": "test upstream content",
        "layer_content": "test layer content",
        "feedback_memos": "test feedback memos",
        "cross_layer_context": "test cross-layer context",
    },
    ("generators", "strategic"): {
        "upstream_content": "test upstream content",
        "layer_content": "test layer content",
        "feedback_memos": "test feedback memos",
        "cross_layer_context": "test cross-layer context",
    },
    ("generators", "tactical"): {
        "upstream_content": "test upstream content",
        "layer_content": "test layer content",
        "feedback_memos": "test feedback memos",
        "cross_layer_context": "test cross-layer context",
    },
    ("generators", "policies"): {
        "upstream_content": "test upstream content",
        "layer_content": "test layer content",
        "feedback_memos": "test feedback memos",
        "cross_layer_context": "test cross-layer context",
    },
    # Critics (all share the same variables)
    ("critics", "realist"): {
        "layer_slug": "strategic-objectives",
        "layer_content": "test layer content",
        "cross_layer_context": "test cross-layer context",
    },
    ("critics", "liberal-institutionalist"): {
        "layer_slug": "strategic-objectives",
        "layer_content": "test layer content",
        "cross_layer_context": "test cross-layer context",
    },
    ("critics", "nationalist-conservative"): {
        "layer_slug": "strategic-objectives",
        "layer_content": "test layer content",
        "cross_layer_context": "test cross-layer context",
    },
    ("critics", "social-democratic"): {
        "layer_slug": "strategic-objectives",
        "layer_content": "test layer content",
        "cross_layer_context": "test cross-layer context",
    },
    ("critics", "libertarian"): {
        "layer_slug": "strategic-objectives",
        "layer_content": "test layer content",
        "cross_layer_context": "test cross-layer context",
    },
    ("critics", "green-ecological"): {
        "layer_slug": "strategic-objectives",
        "layer_content": "test layer content",
        "cross_layer_context": "test cross-layer context",
    },
    # Synthesis
    ("synthesis", "synthesis"): {
        "layer_slug": "strategic-objectives",
        "layer_content": "test layer content",
        "realist_assessment": "test realist",
        "liberal_assessment": "test liberal",
        "nationalist_assessment": "test nationalist",
        "social_democratic_assessment": "test social democratic",
        "libertarian_assessment": "test libertarian",
        "green_assessment": "test green",
    },
    # Conversation
    ("conversation", "system"): {},  # No template variables
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_loader() -> None:
    """Reset the singleton loader so tests use real prompt files."""
    import policy_factory.prompts.loader as loader_mod

    original = loader_mod._default_loader
    loader_mod._default_loader = None
    yield
    loader_mod._default_loader = original


# ---------------------------------------------------------------------------
# Test: No "tech policy" or "technology policy" in any prompt file
# ---------------------------------------------------------------------------


class TestNoTechPolicyReferences:
    """Verify that the anti-slop overhaul removed all tech-policy framing."""

    @pytest.mark.parametrize(
        "md_file",
        sorted(PROMPTS_DIR.rglob("*.md")),
        ids=lambda p: str(p.relative_to(PROMPTS_DIR)),
    )
    def test_no_tech_policy_string(self, md_file: Path) -> None:
        """No prompt file contains 'tech policy' (case-insensitive)."""
        content = md_file.read_text().lower()
        assert "tech policy" not in content, (
            f"{md_file.relative_to(PROMPTS_DIR)} still contains 'tech policy'"
        )

    @pytest.mark.parametrize(
        "md_file",
        sorted(PROMPTS_DIR.rglob("*.md")),
        ids=lambda p: str(p.relative_to(PROMPTS_DIR)),
    )
    def test_no_technology_policy_string(self, md_file: Path) -> None:
        """No prompt file contains 'technology policy' (case-insensitive)."""
        content = md_file.read_text().lower()
        assert "technology policy" not in content, (
            f"{md_file.relative_to(PROMPTS_DIR)} still contains 'technology policy'"
        )


# ---------------------------------------------------------------------------
# Test: Anti-slop section exists and is non-empty
# ---------------------------------------------------------------------------


class TestAntiSlopSectionExists:
    """Verify the anti-slop preamble section is present."""

    def test_anti_slop_section_file_exists(self) -> None:
        """The anti-slop.md section file exists on disk."""
        assert (PROMPTS_DIR / "sections" / "anti-slop.md").exists()

    def test_anti_slop_section_is_nonempty(self) -> None:
        """The anti-slop section has substantive content."""
        content = load_section("anti-slop")
        assert len(content.strip()) > 0

    def test_anti_slop_loads_via_load_section(self) -> None:
        """The anti-slop section loads without error via the loader."""
        content = load_section("anti-slop")
        assert isinstance(content, str)


# ---------------------------------------------------------------------------
# Test: Every prompt loads via build_agent_prompt() without error
# ---------------------------------------------------------------------------


class TestAllPromptsLoad:
    """Verify every prompt file can be loaded with its required variables."""

    @pytest.mark.parametrize(
        "category,name",
        _ALL_PROMPT_FILES,
        ids=[f"{cat}/{name}" for cat, name in _ALL_PROMPT_FILES],
    )
    def test_prompt_loads_successfully(self, category: str, name: str) -> None:
        """Each prompt file loads via build_agent_prompt() without error."""
        key = (category, name)
        assert key in _TEMPLATE_VARS, (
            f"Missing template variables for {category}/{name} in "
            f"_TEMPLATE_VARS — add it to the test configuration"
        )
        variables = _TEMPLATE_VARS[key]
        result = build_agent_prompt(category, name, **variables)
        assert len(result) > 0, f"Empty result for {category}/{name}"

    @pytest.mark.parametrize(
        "category,name",
        _ALL_PROMPT_FILES,
        ids=[f"{cat}/{name}" for cat, name in _ALL_PROMPT_FILES],
    )
    def test_prompt_includes_anti_slop_preamble(
        self, category: str, name: str
    ) -> None:
        """Each prompt starts with the anti-slop preamble when loaded."""
        key = (category, name)
        variables = _TEMPLATE_VARS[key]
        result = build_agent_prompt(category, name, **variables)
        preamble = load_section("anti-slop")
        assert result.startswith(preamble), (
            f"{category}/{name} does not start with the anti-slop preamble"
        )

    def test_all_prompt_files_are_covered(self) -> None:
        """Every prompt file on disk has a corresponding entry in _TEMPLATE_VARS."""
        uncovered = [
            f"{cat}/{name}"
            for cat, name in _ALL_PROMPT_FILES
            if (cat, name) not in _TEMPLATE_VARS
        ]
        assert uncovered == [], (
            f"Prompt files without test coverage: {uncovered}"
        )
