"""Tests for critic archetype definitions."""

from policy_factory.cascade.critics import (
    CRITIC_ARCHETYPES,
    CriticArchetype,
    get_all_archetypes,
    get_archetype,
    get_archetype_slugs,
)


class TestCriticArchetypes:
    """Test the critic archetype definitions."""

    def test_exactly_six_archetypes_defined(self):
        """There must be exactly 6 critic archetypes."""
        assert len(CRITIC_ARCHETYPES) == 6

    def test_all_archetypes_have_required_fields(self):
        """Each archetype must have slug, display_name, and agent_label."""
        for archetype in CRITIC_ARCHETYPES:
            assert isinstance(archetype, CriticArchetype)
            assert archetype.slug, f"Missing slug for {archetype}"
            assert archetype.display_name, f"Missing display_name for {archetype.slug}"
            assert archetype.agent_label, f"Missing agent_label for {archetype.slug}"

    def test_expected_slugs(self):
        """All 6 expected archetype slugs are present."""
        slugs = get_archetype_slugs()
        expected = [
            "realist",
            "liberal-institutionalist",
            "nationalist-conservative",
            "social-democratic",
            "libertarian",
            "green-ecological",
        ]
        assert slugs == expected

    def test_slugs_are_unique(self):
        """All archetype slugs must be unique."""
        slugs = get_archetype_slugs()
        assert len(slugs) == len(set(slugs))

    def test_get_archetype_by_slug(self):
        """get_archetype returns the correct archetype for a valid slug."""
        realist = get_archetype("realist")
        assert realist is not None
        assert realist.slug == "realist"
        assert "Realist" in realist.display_name

    def test_get_archetype_invalid_slug(self):
        """get_archetype returns None for an unknown slug."""
        assert get_archetype("nonexistent") is None

    def test_get_all_archetypes_returns_copy(self):
        """get_all_archetypes returns a copy, not the original list."""
        result = get_all_archetypes()
        assert result == CRITIC_ARCHETYPES
        assert result is not CRITIC_ARCHETYPES

    def test_get_archetype_slugs_order(self):
        """Slugs are returned in the canonical order."""
        slugs = get_archetype_slugs()
        assert slugs[0] == "realist"
        assert slugs[-1] == "green-ecological"

    def test_archetype_frozen(self):
        """Archetypes are frozen dataclasses (immutable)."""
        archetype = CRITIC_ARCHETYPES[0]
        try:
            archetype.slug = "modified"
            assert False, "Should have raised FrozenInstanceError"
        except AttributeError:
            pass  # Expected — frozen dataclass

    def test_agent_labels_contain_critic(self):
        """Each agent label should contain 'critic'."""
        for archetype in CRITIC_ARCHETYPES:
            assert "critic" in archetype.agent_label.lower(), (
                f"Agent label '{archetype.agent_label}' doesn't contain 'critic'"
            )

    def test_each_archetype_has_matching_prompt_template(self):
        """Each archetype slug should correspond to a prompt template file."""
        from pathlib import Path

        prompts_dir = (
            Path(__file__).parent.parent / "src" / "policy_factory" / "prompts" / "critics"
        )
        for archetype in CRITIC_ARCHETYPES:
            template_path = prompts_dir / f"{archetype.slug}.md"
            assert template_path.exists(), (
                f"Missing prompt template for {archetype.slug}: {template_path}"
            )
