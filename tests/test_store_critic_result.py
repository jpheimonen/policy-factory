"""Tests for the critic result store mixin."""



from policy_factory.store import PolicyStore
from policy_factory.store.critic_result import CriticResult, SynthesisResult


class TestCriticResultStorage:
    """Test storing and retrieving critic results."""

    def test_store_critic_result(self, store: PolicyStore):
        """Storing a critic result returns a valid ID."""
        result_id = store.store_critic_result(
            cascade_id="cascade-1",
            layer_slug="values",
            idea_id=None,
            archetype="realist",
            assessment_text="The values layer adequately addresses security.",
            structured_assessment={"items": [{"title": "Item 1", "score": 8}]},
            agent_run_id="run-1",
        )
        assert result_id
        assert isinstance(result_id, str)

    def test_get_critic_results_for_cascade_and_layer(self, store: PolicyStore):
        """Retrieving critic results returns all stored for a cascade/layer."""
        # Store results for 3 archetypes
        for archetype in ["realist", "liberal-institutionalist", "social-democratic"]:
            store.store_critic_result(
                cascade_id="cascade-1",
                layer_slug="values",
                idea_id=None,
                archetype=archetype,
                assessment_text=f"Assessment from {archetype}",
                structured_assessment=None,
                agent_run_id=f"run-{archetype}",
            )

        results = store.get_critic_results("cascade-1", "values")
        assert len(results) == 3
        archetypes = {r.archetype for r in results}
        assert archetypes == {"realist", "liberal-institutionalist", "social-democratic"}

    def test_get_critic_results_returns_empty_for_nonexistent(self, store: PolicyStore):
        """Retrieving results for a non-existent cascade returns empty list."""
        results = store.get_critic_results("nonexistent", "values")
        assert results == []

    def test_get_critic_results_isolates_by_cascade(self, store: PolicyStore):
        """Results from different cascades are isolated."""
        store.store_critic_result(
            cascade_id="cascade-1",
            layer_slug="values",
            idea_id=None,
            archetype="realist",
            assessment_text="First cascade",
            structured_assessment=None,
            agent_run_id="run-1",
        )
        store.store_critic_result(
            cascade_id="cascade-2",
            layer_slug="values",
            idea_id=None,
            archetype="realist",
            assessment_text="Second cascade",
            structured_assessment=None,
            agent_run_id="run-2",
        )

        results = store.get_critic_results("cascade-1", "values")
        assert len(results) == 1
        assert results[0].assessment_text == "First cascade"

    def test_get_critic_results_isolates_by_layer(self, store: PolicyStore):
        """Results from different layers within the same cascade are isolated."""
        store.store_critic_result(
            cascade_id="cascade-1",
            layer_slug="values",
            idea_id=None,
            archetype="realist",
            assessment_text="Values assessment",
            structured_assessment=None,
            agent_run_id="run-1",
        )
        store.store_critic_result(
            cascade_id="cascade-1",
            layer_slug="policies",
            idea_id=None,
            archetype="realist",
            assessment_text="Policies assessment",
            structured_assessment=None,
            agent_run_id="run-2",
        )

        values_results = store.get_critic_results("cascade-1", "values")
        assert len(values_results) == 1
        assert values_results[0].layer_slug == "values"

        policies_results = store.get_critic_results("cascade-1", "policies")
        assert len(policies_results) == 1
        assert policies_results[0].layer_slug == "policies"

    def test_critic_result_has_all_fields(self, store: PolicyStore):
        """The CriticResult dataclass has all expected fields populated."""
        structured = {"items": [{"title": "X", "score": 7}], "average_score": 7.0}
        store.store_critic_result(
            cascade_id="cascade-1",
            layer_slug="values",
            idea_id=None,
            archetype="realist",
            assessment_text="Detailed assessment text",
            structured_assessment=structured,
            agent_run_id="run-abc",
        )

        results = store.get_critic_results("cascade-1", "values")
        assert len(results) == 1
        r = results[0]

        assert isinstance(r, CriticResult)
        assert r.id
        assert r.cascade_id == "cascade-1"
        assert r.layer_slug == "values"
        assert r.idea_id is None
        assert r.archetype == "realist"
        assert r.assessment_text == "Detailed assessment text"
        assert r.structured_assessment == structured
        assert r.agent_run_id == "run-abc"
        assert r.created_at is not None

    def test_critic_result_with_null_structured_assessment(self, store: PolicyStore):
        """Structured assessment can be None (parsing failed)."""
        store.store_critic_result(
            cascade_id="cascade-1",
            layer_slug="values",
            idea_id=None,
            archetype="realist",
            assessment_text="Free-form text",
            structured_assessment=None,
            agent_run_id="run-1",
        )

        results = store.get_critic_results("cascade-1", "values")
        assert results[0].structured_assessment is None

    def test_get_critic_result_by_archetype(self, store: PolicyStore):
        """Retrieving a single critic result by archetype works."""
        store.store_critic_result(
            cascade_id="cascade-1",
            layer_slug="values",
            idea_id=None,
            archetype="realist",
            assessment_text="Realist says...",
            structured_assessment=None,
            agent_run_id="run-1",
        )
        store.store_critic_result(
            cascade_id="cascade-1",
            layer_slug="values",
            idea_id=None,
            archetype="libertarian",
            assessment_text="Libertarian says...",
            structured_assessment=None,
            agent_run_id="run-2",
        )

        result = store.get_critic_result_by_archetype("cascade-1", "values", "realist")
        assert result is not None
        assert result.archetype == "realist"
        assert result.assessment_text == "Realist says..."

    def test_get_critic_result_by_archetype_not_found(self, store: PolicyStore):
        """Returns None when the archetype result doesn't exist."""
        result = store.get_critic_result_by_archetype("cascade-1", "values", "realist")
        assert result is None

    def test_get_critic_results_for_idea(self, store: PolicyStore):
        """Retrieving critic results scoped to an idea works."""
        store.store_critic_result(
            cascade_id=None,
            layer_slug=None,
            idea_id="idea-1",
            archetype="realist",
            assessment_text="Idea assessment",
            structured_assessment=None,
            agent_run_id="run-1",
        )
        store.store_critic_result(
            cascade_id=None,
            layer_slug=None,
            idea_id="idea-2",
            archetype="realist",
            assessment_text="Different idea",
            structured_assessment=None,
            agent_run_id="run-2",
        )

        results = store.get_critic_results_for_idea("idea-1")
        assert len(results) == 1
        assert results[0].idea_id == "idea-1"

    def test_is_success_property(self, store: PolicyStore):
        """CriticResult.is_success reflects whether text is non-empty."""
        store.store_critic_result(
            cascade_id="c1",
            layer_slug="values",
            idea_id=None,
            archetype="realist",
            assessment_text="Has content",
            structured_assessment=None,
            agent_run_id=None,
        )
        store.store_critic_result(
            cascade_id="c1",
            layer_slug="values",
            idea_id=None,
            archetype="libertarian",
            assessment_text="",
            structured_assessment=None,
            agent_run_id=None,
        )

        results = store.get_critic_results("c1", "values")
        by_arch = {r.archetype: r for r in results}
        assert by_arch["realist"].is_success is True
        assert by_arch["libertarian"].is_success is False


class TestLatestCriticResults:
    """Test the get_latest_* helper methods."""

    def test_get_latest_critic_results(self, store: PolicyStore):
        """Returns results from the most recent cascade for a layer."""
        # First cascade
        store.store_critic_result(
            cascade_id="cascade-old",
            layer_slug="values",
            idea_id=None,
            archetype="realist",
            assessment_text="Old assessment",
            structured_assessment=None,
            agent_run_id="run-1",
        )

        # Second cascade (newer)
        store.store_critic_result(
            cascade_id="cascade-new",
            layer_slug="values",
            idea_id=None,
            archetype="realist",
            assessment_text="New assessment",
            structured_assessment=None,
            agent_run_id="run-2",
        )
        store.store_critic_result(
            cascade_id="cascade-new",
            layer_slug="values",
            idea_id=None,
            archetype="libertarian",
            assessment_text="New libertarian",
            structured_assessment=None,
            agent_run_id="run-3",
        )

        results = store.get_latest_critic_results("values")
        assert len(results) == 2
        assert all(r.cascade_id == "cascade-new" for r in results)

    def test_get_latest_critic_results_empty(self, store: PolicyStore):
        """Returns empty list when no results exist for the layer."""
        results = store.get_latest_critic_results("values")
        assert results == []

    def test_get_latest_critic_results_excludes_idea_results(self, store: PolicyStore):
        """Latest critic results only considers cascade results, not idea results."""
        # Idea result (no cascade_id)
        store.store_critic_result(
            cascade_id=None,
            layer_slug=None,
            idea_id="idea-1",
            archetype="realist",
            assessment_text="Idea assessment",
            structured_assessment=None,
            agent_run_id="run-1",
        )

        results = store.get_latest_critic_results("values")
        assert results == []


class TestSynthesisResultStorage:
    """Test storing and retrieving synthesis results."""

    def test_store_synthesis_result(self, store: PolicyStore):
        """Storing a synthesis result returns a valid ID."""
        result_id = store.store_synthesis_result(
            cascade_id="cascade-1",
            layer_slug="values",
            idea_id=None,
            synthesis_text="Balanced synthesis of all perspectives.",
            structured_synthesis={
                "consensus_points": "Security is important",
                "tension_points": "Realist vs Liberal on NATO",
            },
            agent_run_id="run-synth-1",
        )
        assert result_id
        assert isinstance(result_id, str)

    def test_get_synthesis_result(self, store: PolicyStore):
        """Retrieving a synthesis result for a cascade/layer works."""
        store.store_synthesis_result(
            cascade_id="cascade-1",
            layer_slug="values",
            idea_id=None,
            synthesis_text="Synthesis text",
            structured_synthesis={"overall_score": 7},
            agent_run_id="run-1",
        )

        result = store.get_synthesis_result("cascade-1", "values")
        assert result is not None
        assert isinstance(result, SynthesisResult)
        assert result.synthesis_text == "Synthesis text"
        assert result.structured_synthesis == {"overall_score": 7}

    def test_get_synthesis_result_not_found(self, store: PolicyStore):
        """Returns None when no synthesis exists for cascade/layer."""
        result = store.get_synthesis_result("nonexistent", "values")
        assert result is None

    def test_get_synthesis_result_for_idea(self, store: PolicyStore):
        """Retrieving a synthesis result scoped to an idea works."""
        store.store_synthesis_result(
            cascade_id=None,
            layer_slug=None,
            idea_id="idea-1",
            synthesis_text="Idea synthesis",
            structured_synthesis=None,
            agent_run_id="run-1",
        )

        result = store.get_synthesis_result_for_idea("idea-1")
        assert result is not None
        assert result.idea_id == "idea-1"

    def test_get_synthesis_result_for_idea_not_found(self, store: PolicyStore):
        """Returns None when no synthesis exists for an idea."""
        result = store.get_synthesis_result_for_idea("nonexistent")
        assert result is None

    def test_get_latest_synthesis_result(self, store: PolicyStore):
        """Returns the most recent synthesis result for a layer."""
        store.store_synthesis_result(
            cascade_id="cascade-old",
            layer_slug="values",
            idea_id=None,
            synthesis_text="Old synthesis",
            structured_synthesis=None,
            agent_run_id="run-1",
        )
        store.store_synthesis_result(
            cascade_id="cascade-new",
            layer_slug="values",
            idea_id=None,
            synthesis_text="New synthesis",
            structured_synthesis=None,
            agent_run_id="run-2",
        )

        result = store.get_latest_synthesis_result("values")
        assert result is not None
        assert result.cascade_id == "cascade-new"
        assert result.synthesis_text == "New synthesis"

    def test_get_latest_synthesis_result_empty(self, store: PolicyStore):
        """Returns None when no synthesis exists for the layer."""
        result = store.get_latest_synthesis_result("values")
        assert result is None

    def test_synthesis_result_has_all_fields(self, store: PolicyStore):
        """SynthesisResult dataclass has all expected fields."""
        structured = {"consensus_points": "All agree on X", "overall_score": 8}
        store.store_synthesis_result(
            cascade_id="cascade-1",
            layer_slug="values",
            idea_id=None,
            synthesis_text="Full synthesis text here",
            structured_synthesis=structured,
            agent_run_id="run-synth",
        )

        result = store.get_synthesis_result("cascade-1", "values")
        assert result is not None
        assert result.id
        assert result.cascade_id == "cascade-1"
        assert result.layer_slug == "values"
        assert result.idea_id is None
        assert result.synthesis_text == "Full synthesis text here"
        assert result.structured_synthesis == structured
        assert result.agent_run_id == "run-synth"
        assert result.created_at is not None

    def test_synthesis_null_structured(self, store: PolicyStore):
        """Structured synthesis can be None."""
        store.store_synthesis_result(
            cascade_id="cascade-1",
            layer_slug="values",
            idea_id=None,
            synthesis_text="Text only",
            structured_synthesis=None,
            agent_run_id=None,
        )

        result = store.get_synthesis_result("cascade-1", "values")
        assert result is not None
        assert result.structured_synthesis is None


class TestSchemaCreation:
    """Test that the new tables are created during schema init."""

    def test_critic_results_table_exists(self, store: PolicyStore):
        """The critic_results table exists after store initialization."""
        cursor = store.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='critic_results'"
        )
        assert cursor.fetchone() is not None

    def test_synthesis_results_table_exists(self, store: PolicyStore):
        """The synthesis_results table exists after store initialization."""
        cursor = store.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='synthesis_results'"
        )
        assert cursor.fetchone() is not None

    def test_critic_results_cascade_layer_index_exists(self, store: PolicyStore):
        """Index on cascade_id + layer_slug exists for critic_results."""
        cursor = store.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND name='idx_critic_results_cascade_layer'"
        )
        assert cursor.fetchone() is not None

    def test_critic_results_idea_id_index_exists(self, store: PolicyStore):
        """Index on idea_id exists for critic_results."""
        cursor = store.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND name='idx_critic_results_idea_id'"
        )
        assert cursor.fetchone() is not None

    def test_synthesis_results_cascade_layer_index_exists(self, store: PolicyStore):
        """Index on cascade_id + layer_slug exists for synthesis_results."""
        cursor = store.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND name='idx_synthesis_results_cascade_layer'"
        )
        assert cursor.fetchone() is not None
