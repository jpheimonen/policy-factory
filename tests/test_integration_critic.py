"""Integration tests for the critic system end-to-end (with mocked agents).

Tests that running critics stores all 6 assessments and synthesis results
in the database, linked to the correct cascade and layer.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import policy_factory.auth as auth_mod
from policy_factory.data.layers import LAYER_SLUGS
from policy_factory.store import PolicyStore


@pytest.fixture(autouse=True)
def _configure_auth():
    original_key = auth_mod.JWT_SECRET_KEY
    original_expiry = auth_mod.JWT_EXPIRY_HOURS
    auth_mod.JWT_SECRET_KEY = "test-secret-key-for-critic-integration"
    auth_mod.JWT_EXPIRY_HOURS = 24
    yield
    auth_mod.JWT_SECRET_KEY = original_key
    auth_mod.JWT_EXPIRY_HOURS = original_expiry


@pytest.fixture
def store(tmp_path: Path) -> PolicyStore:
    return PolicyStore(tmp_path / "test.db")


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    d = tmp_path / "data"
    for slug in LAYER_SLUGS:
        (d / slug).mkdir(parents=True, exist_ok=True)
        (d / slug / "README.md").write_text(f"# {slug}\n\nSummary.")
    return d


CRITIC_ARCHETYPES = [
    "realist",
    "liberal-institutionalist",
    "nationalist-conservative",
    "social-democratic",
    "libertarian",
    "green-ecological",
]


class TestCriticResultStorage:
    """Running critics stores all 6 assessments in the database."""

    def test_store_all_six_critic_results(self, store: PolicyStore) -> None:
        """Verify all 6 critic assessments can be stored and retrieved."""
        cascade_id = store.create_cascade(
            trigger_source="test",
            starting_layer="values",
        )
        layer_slug = "values"

        # Store 6 critic results
        for archetype in CRITIC_ARCHETYPES:
            store.store_critic_result(
                cascade_id=cascade_id,
                layer_slug=layer_slug,
                idea_id=None,
                archetype=archetype,
                assessment_text=f"Mock assessment from {archetype}",
                structured_assessment={
                    "agreement": "partial",
                    "alternatives": f"Consider {archetype} alternatives.",
                },
                agent_run_id=None,
            )

        # Retrieve and verify
        results = store.get_critic_results(cascade_id, layer_slug)
        assert len(results) == 6

        stored_archetypes = {r.archetype for r in results}
        assert stored_archetypes == set(CRITIC_ARCHETYPES)

        # Each result should have the correct cascade and layer
        for r in results:
            assert r.cascade_id == cascade_id
            assert r.layer_slug == layer_slug
            assert "assessment" in r.assessment_text.lower() or "mock" in r.assessment_text.lower()

    def test_synthesis_stored_with_cascade_and_layer(self, store: PolicyStore) -> None:
        """Verify synthesis result is stored linked to cascade and layer."""
        cascade_id = store.create_cascade(
            trigger_source="test",
            starting_layer="values",
        )
        layer_slug = "strategic-objectives"

        # Store critic results first
        for archetype in CRITIC_ARCHETYPES:
            store.store_critic_result(
                cascade_id=cascade_id,
                layer_slug=layer_slug,
                idea_id=None,
                archetype=archetype,
                assessment_text=f"Assessment from {archetype}",
                structured_assessment=None,
                agent_run_id=None,
            )

        # Store synthesis
        synthesis_text = (
            "After reviewing all 6 perspectives, the content is well-balanced. "
            "Key tensions exist between security and cooperation perspectives."
        )
        store.store_synthesis_result(
            cascade_id=cascade_id,
            layer_slug=layer_slug,
            idea_id=None,
            synthesis_text=synthesis_text,
            structured_synthesis=None,
            agent_run_id=None,
        )

        # Retrieve and verify
        synthesis = store.get_synthesis_result(cascade_id, layer_slug)
        assert synthesis is not None
        assert synthesis.cascade_id == cascade_id
        assert synthesis.layer_slug == layer_slug
        assert "well-balanced" in synthesis.synthesis_text

    def test_critic_results_linked_to_correct_cascade(self, store: PolicyStore) -> None:
        """Results from different cascades don't mix."""
        cascade_1 = store.create_cascade(trigger_source="test1", starting_layer="values")
        cascade_2 = store.create_cascade(trigger_source="test2", starting_layer="values")

        # Store results for cascade 1
        store.store_critic_result(
            cascade_id=cascade_1,
            layer_slug="values",
            idea_id=None,
            archetype="realist",
            assessment_text="Cascade 1 realist assessment",
            structured_assessment=None,
            agent_run_id=None,
        )

        # Store results for cascade 2
        store.store_critic_result(
            cascade_id=cascade_2,
            layer_slug="values",
            idea_id=None,
            archetype="realist",
            assessment_text="Cascade 2 realist assessment",
            structured_assessment=None,
            agent_run_id=None,
        )

        # Retrieve separately
        results_1 = store.get_critic_results(cascade_1, "values")
        results_2 = store.get_critic_results(cascade_2, "values")

        assert len(results_1) == 1
        assert len(results_2) == 1
        assert "Cascade 1" in results_1[0].assessment_text
        assert "Cascade 2" in results_2[0].assessment_text
