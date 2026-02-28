"""Tests for the IdeaStoreMixin."""

from pathlib import Path

import pytest

from policy_factory.store import PolicyStore


@pytest.fixture
def store(tmp_path: Path) -> PolicyStore:
    """Fresh PolicyStore with temporary database."""
    return PolicyStore(tmp_path / "test.db")


class TestCreateIdea:
    """Tests for create_idea()."""

    def test_creates_human_idea(self, store: PolicyStore) -> None:
        idea_id = store.create_idea(
            text="Finland should create a sovereign AI compute fund",
            source="human",
            submitted_by="user@example.com",
        )
        assert idea_id
        idea = store.get_idea(idea_id)
        assert idea is not None
        assert idea.text == "Finland should create a sovereign AI compute fund"
        assert idea.source == "human"
        assert idea.submitted_by == "user@example.com"
        assert idea.status == "pending"
        assert idea.target_objective is None
        assert idea.evaluation_started_at is None
        assert idea.evaluation_completed_at is None

    def test_creates_ai_idea(self, store: PolicyStore) -> None:
        idea_id = store.create_idea(
            text="Establish an AI ethics board",
            source="AI",
            submitted_by="system",
        )
        idea = store.get_idea(idea_id)
        assert idea is not None
        assert idea.source == "AI"
        assert idea.submitted_by == "system"
        assert idea.status == "pending"

    def test_creates_idea_with_target_objective(self, store: PolicyStore) -> None:
        idea_id = store.create_idea(
            text="Tax holiday for AI companies",
            source="human",
            target_objective="strategic-objectives/ai-leadership.md",
            submitted_by="user@example.com",
        )
        idea = store.get_idea(idea_id)
        assert idea is not None
        assert idea.target_objective == "strategic-objectives/ai-leadership.md"

    def test_unique_ids(self, store: PolicyStore) -> None:
        id1 = store.create_idea(text="Idea 1", source="human", submitted_by="u@e.com")
        id2 = store.create_idea(text="Idea 2", source="human", submitted_by="u@e.com")
        assert id1 != id2


class TestGetIdea:
    """Tests for get_idea()."""

    def test_returns_complete_record(self, store: PolicyStore) -> None:
        idea_id = store.create_idea(
            text="Test idea",
            source="human",
            submitted_by="user@test.com",
        )
        idea = store.get_idea(idea_id)
        assert idea is not None
        assert idea.id == idea_id
        assert idea.text == "Test idea"
        assert idea.submitted_at is not None

    def test_returns_none_for_nonexistent(self, store: PolicyStore) -> None:
        result = store.get_idea("nonexistent-id")
        assert result is None


class TestListIdeas:
    """Tests for list_ideas()."""

    def test_returns_ideas_newest_first(self, store: PolicyStore) -> None:
        id1 = store.create_idea(text="First", source="human", submitted_by="u@e.com")
        id2 = store.create_idea(text="Second", source="human", submitted_by="u@e.com")
        id3 = store.create_idea(text="Third", source="human", submitted_by="u@e.com")

        ideas = store.list_ideas()
        assert len(ideas) == 3
        # Newest first (default desc order)
        assert ideas[0].id == id3
        assert ideas[1].id == id2
        assert ideas[2].id == id1

    def test_filters_by_status(self, store: PolicyStore) -> None:
        store.create_idea(text="Pending", source="human", submitted_by="u@e.com")
        eval_id = store.create_idea(text="Evaluating", source="human", submitted_by="u@e.com")
        store.update_idea_status(eval_id, "evaluating")

        pending = store.list_ideas(status="pending")
        assert len(pending) == 1
        assert pending[0].text == "Pending"

        evaluating = store.list_ideas(status="evaluating")
        assert len(evaluating) == 1
        assert evaluating[0].text == "Evaluating"

    def test_excludes_archived_by_default(self, store: PolicyStore) -> None:
        store.create_idea(text="Active", source="human", submitted_by="u@e.com")
        archived_id = store.create_idea(text="Archived", source="human", submitted_by="u@e.com")
        store.archive_idea(archived_id)

        ideas = store.list_ideas()
        assert len(ideas) == 1
        assert ideas[0].text == "Active"

    def test_shows_archived_when_explicit(self, store: PolicyStore) -> None:
        store.create_idea(text="Active", source="human", submitted_by="u@e.com")
        archived_id = store.create_idea(text="Archived", source="human", submitted_by="u@e.com")
        store.archive_idea(archived_id)

        ideas = store.list_ideas(status="archived")
        assert len(ideas) == 1
        assert ideas[0].text == "Archived"

    def test_sorts_by_score(self, store: PolicyStore) -> None:
        id1 = store.create_idea(text="Low score", source="human", submitted_by="u@e.com")
        id2 = store.create_idea(text="High score", source="human", submitted_by="u@e.com")

        store.store_scores(id1, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0)
        store.store_scores(id2, 9.0, 9.0, 9.0, 9.0, 9.0, 9.0)

        ideas = store.list_ideas(sort_by="score", sort_order="desc")
        assert len(ideas) == 2
        assert ideas[0].id == id2  # Higher score first
        assert ideas[1].id == id1

    def test_pagination(self, store: PolicyStore) -> None:
        for i in range(5):
            store.create_idea(text=f"Idea {i}", source="human", submitted_by="u@e.com")

        page1 = store.list_ideas(limit=2, offset=0)
        assert len(page1) == 2

        page2 = store.list_ideas(limit=2, offset=2)
        assert len(page2) == 2

        page3 = store.list_ideas(limit=2, offset=4)
        assert len(page3) == 1

    def test_empty_list(self, store: PolicyStore) -> None:
        ideas = store.list_ideas()
        assert ideas == []


class TestUpdateIdeaStatus:
    """Tests for update_idea_status()."""

    def test_to_evaluating_sets_started_timestamp(self, store: PolicyStore) -> None:
        idea_id = store.create_idea(text="Test", source="human", submitted_by="u@e.com")
        store.update_idea_status(idea_id, "evaluating")

        idea = store.get_idea(idea_id)
        assert idea is not None
        assert idea.status == "evaluating"
        assert idea.evaluation_started_at is not None

    def test_to_evaluated_sets_completed_timestamp(self, store: PolicyStore) -> None:
        idea_id = store.create_idea(text="Test", source="human", submitted_by="u@e.com")
        store.update_idea_status(idea_id, "evaluating")
        store.update_idea_status(idea_id, "evaluated")

        idea = store.get_idea(idea_id)
        assert idea is not None
        assert idea.status == "evaluated"
        assert idea.evaluation_completed_at is not None

    def test_returns_false_for_nonexistent(self, store: PolicyStore) -> None:
        result = store.update_idea_status("nonexistent", "evaluating")
        assert result is False

    def test_returns_true_on_success(self, store: PolicyStore) -> None:
        idea_id = store.create_idea(text="Test", source="human", submitted_by="u@e.com")
        result = store.update_idea_status(idea_id, "evaluating")
        assert result is True


class TestArchiveIdea:
    """Tests for archive_idea()."""

    def test_sets_archived_status(self, store: PolicyStore) -> None:
        idea_id = store.create_idea(text="Test", source="human", submitted_by="u@e.com")
        store.archive_idea(idea_id)

        idea = store.get_idea(idea_id)
        assert idea is not None
        assert idea.status == "archived"

    def test_returns_false_for_nonexistent(self, store: PolicyStore) -> None:
        result = store.archive_idea("nonexistent")
        assert result is False


class TestCountIdeas:
    """Tests for count_ideas()."""

    def test_counts_all(self, store: PolicyStore) -> None:
        store.create_idea(text="A", source="human", submitted_by="u@e.com")
        store.create_idea(text="B", source="AI", submitted_by="system")
        assert store.count_ideas() == 2

    def test_counts_by_status(self, store: PolicyStore) -> None:
        store.create_idea(text="A", source="human", submitted_by="u@e.com")
        eval_id = store.create_idea(text="B", source="human", submitted_by="u@e.com")
        store.update_idea_status(eval_id, "evaluating")

        assert store.count_ideas(status="pending") == 1
        assert store.count_ideas(status="evaluating") == 1
        assert store.count_ideas(status="evaluated") == 0

    def test_counts_zero_when_empty(self, store: PolicyStore) -> None:
        assert store.count_ideas() == 0
