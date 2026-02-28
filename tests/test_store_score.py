"""Tests for the ScoreStoreMixin."""

from pathlib import Path

import pytest

from policy_factory.store import PolicyStore


@pytest.fixture
def store(tmp_path: Path) -> PolicyStore:
    """Fresh PolicyStore with temporary database."""
    return PolicyStore(tmp_path / "test.db")


@pytest.fixture
def idea_id(store: PolicyStore) -> str:
    """Create a test idea and return its ID."""
    return store.create_idea(
        text="Test idea for scoring",
        source="human",
        submitted_by="user@test.com",
    )


class TestStoreScores:
    """Tests for store_scores()."""

    def test_stores_all_six_axes(self, store: PolicyStore, idea_id: str) -> None:
        score_id = store.store_scores(
            idea_id=idea_id,
            strategic_fit=8.0,
            feasibility=7.0,
            cost=6.0,
            risk=5.0,
            public_acceptance=9.0,
            international_impact=4.0,
        )
        assert score_id

        scores = store.get_scores(idea_id)
        assert scores is not None
        assert scores.strategic_fit == 8.0
        assert scores.feasibility == 7.0
        assert scores.cost == 6.0
        assert scores.risk == 5.0
        assert scores.public_acceptance == 9.0
        assert scores.international_impact == 4.0

    def test_computes_overall_score(self, store: PolicyStore, idea_id: str) -> None:
        store.store_scores(
            idea_id=idea_id,
            strategic_fit=6.0,
            feasibility=6.0,
            cost=6.0,
            risk=6.0,
            public_acceptance=6.0,
            international_impact=6.0,
        )

        scores = store.get_scores(idea_id)
        assert scores is not None
        assert scores.overall_score == 6.0

    def test_computes_overall_score_mixed(self, store: PolicyStore, idea_id: str) -> None:
        store.store_scores(
            idea_id=idea_id,
            strategic_fit=10.0,
            feasibility=8.0,
            cost=6.0,
            risk=4.0,
            public_acceptance=2.0,
            international_impact=0.0,
        )

        scores = store.get_scores(idea_id)
        assert scores is not None
        assert scores.overall_score == 5.0

    def test_stores_agent_run_id(self, store: PolicyStore, idea_id: str) -> None:
        store.store_scores(
            idea_id=idea_id,
            strategic_fit=5.0,
            feasibility=5.0,
            cost=5.0,
            risk=5.0,
            public_acceptance=5.0,
            international_impact=5.0,
            agent_run_id="test-run-123",
        )

        scores = store.get_scores(idea_id)
        assert scores is not None
        assert scores.agent_run_id == "test-run-123"


class TestGetScores:
    """Tests for get_scores()."""

    def test_returns_none_for_unevaluated(self, store: PolicyStore, idea_id: str) -> None:
        scores = store.get_scores(idea_id)
        assert scores is None

    def test_returns_latest_scores(self, store: PolicyStore, idea_id: str) -> None:
        # Store first set of scores
        store.store_scores(
            idea_id=idea_id,
            strategic_fit=3.0,
            feasibility=3.0,
            cost=3.0,
            risk=3.0,
            public_acceptance=3.0,
            international_impact=3.0,
        )

        # Store second (newer) set
        store.store_scores(
            idea_id=idea_id,
            strategic_fit=9.0,
            feasibility=9.0,
            cost=9.0,
            risk=9.0,
            public_acceptance=9.0,
            international_impact=9.0,
        )

        scores = store.get_scores(idea_id)
        assert scores is not None
        assert scores.overall_score == 9.0  # Should be the latest


class TestGetTopScoredIdeas:
    """Tests for get_top_scored_ideas()."""

    def test_returns_ordered_by_score(self, store: PolicyStore) -> None:
        id1 = store.create_idea(text="Low", source="human", submitted_by="u@e.com")
        id2 = store.create_idea(text="High", source="human", submitted_by="u@e.com")
        id3 = store.create_idea(text="Mid", source="human", submitted_by="u@e.com")

        store.store_scores(id1, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0)
        store.store_scores(id2, 9.0, 9.0, 9.0, 9.0, 9.0, 9.0)
        store.store_scores(id3, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0)

        top = store.get_top_scored_ideas(limit=3)
        assert len(top) == 3
        assert top[0] == id2  # Highest
        assert top[1] == id3  # Middle
        assert top[2] == id1  # Lowest

    def test_respects_limit(self, store: PolicyStore) -> None:
        for i in range(5):
            idea_id = store.create_idea(text=f"Idea {i}", source="human", submitted_by="u@e.com")
            store.store_scores(idea_id, float(i), float(i), float(i), float(i), float(i), float(i))

        top = store.get_top_scored_ideas(limit=2)
        assert len(top) == 2

    def test_returns_empty_when_no_scores(self, store: PolicyStore) -> None:
        store.create_idea(text="No scores", source="human", submitted_by="u@e.com")
        top = store.get_top_scored_ideas()
        assert top == []
