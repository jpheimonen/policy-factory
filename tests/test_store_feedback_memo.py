"""Tests for FeedbackMemoMixin — feedback memo store operations."""

from pathlib import Path

import pytest

from policy_factory.store import PolicyStore

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def store(tmp_path: Path) -> PolicyStore:
    """Fresh PolicyStore with feedback memos table."""
    return PolicyStore(tmp_path / "test.db")


# ---------------------------------------------------------------------------
# Creation tests
# ---------------------------------------------------------------------------


class TestCreateFeedbackMemo:
    """Tests for create_feedback_memo."""

    def test_creates_memo_with_pending_status(self, store: PolicyStore) -> None:
        memo_id = store.create_feedback_memo(
            source_layer="strategic-objectives",
            target_layer="values",
            cascade_id="cascade-123",
            content="The value of economic prosperity conflicts with green transition goals.",
        )
        assert memo_id is not None

        memo = store.get_memo(memo_id)
        assert memo is not None
        assert memo.status == "pending"

    def test_stores_correct_source_and_target_layers(self, store: PolicyStore) -> None:
        memo_id = store.create_feedback_memo(
            source_layer="policies",
            target_layer="tactical-objectives",
            cascade_id="cascade-456",
            content="Policy implementation requires additional tactical objective.",
        )
        memo = store.get_memo(memo_id)
        assert memo is not None
        assert memo.source_layer == "policies"
        assert memo.target_layer == "tactical-objectives"

    def test_stores_cascade_id(self, store: PolicyStore) -> None:
        memo_id = store.create_feedback_memo(
            source_layer="strategic-objectives",
            target_layer="values",
            cascade_id="cascade-789",
            content="Test content.",
        )
        memo = store.get_memo(memo_id)
        assert memo is not None
        assert memo.cascade_id == "cascade-789"

    def test_stores_referenced_items(self, store: PolicyStore) -> None:
        memo_id = store.create_feedback_memo(
            source_layer="strategic-objectives",
            target_layer="values",
            cascade_id=None,
            content="Test content.",
            referenced_items=["national-security.md", "economic-prosperity.md"],
        )
        memo = store.get_memo(memo_id)
        assert memo is not None
        assert memo.referenced_items == ["national-security.md", "economic-prosperity.md"]

    def test_empty_referenced_items(self, store: PolicyStore) -> None:
        memo_id = store.create_feedback_memo(
            source_layer="strategic-objectives",
            target_layer="values",
            cascade_id=None,
            content="Test content.",
        )
        memo = store.get_memo(memo_id)
        assert memo is not None
        assert memo.referenced_items == []

    def test_nullable_cascade_id(self, store: PolicyStore) -> None:
        memo_id = store.create_feedback_memo(
            source_layer="strategic-objectives",
            target_layer="values",
            cascade_id=None,
            content="Manual feedback.",
        )
        memo = store.get_memo(memo_id)
        assert memo is not None
        assert memo.cascade_id is None

    def test_sets_created_at_timestamp(self, store: PolicyStore) -> None:
        memo_id = store.create_feedback_memo(
            source_layer="policies",
            target_layer="tactical-objectives",
            cascade_id=None,
            content="Test.",
        )
        memo = store.get_memo(memo_id)
        assert memo is not None
        assert memo.created_at is not None

    def test_resolved_at_is_none_on_creation(self, store: PolicyStore) -> None:
        memo_id = store.create_feedback_memo(
            source_layer="policies",
            target_layer="tactical-objectives",
            cascade_id=None,
            content="Test.",
        )
        memo = store.get_memo(memo_id)
        assert memo is not None
        assert memo.resolved_at is None


# ---------------------------------------------------------------------------
# Pending memo retrieval tests
# ---------------------------------------------------------------------------


class TestGetPendingMemos:
    """Tests for get_pending_memos."""

    def test_returns_pending_memos_for_target_layer(self, store: PolicyStore) -> None:
        store.create_feedback_memo("policies", "values", None, "Memo 1")
        store.create_feedback_memo("strategic-objectives", "values", None, "Memo 2")
        store.create_feedback_memo("policies", "tactical-objectives", None, "Memo 3")

        pending = store.get_pending_memos("values")
        assert len(pending) == 2
        assert all(m.target_layer == "values" for m in pending)

    def test_sorted_by_creation_date_oldest_first(self, store: PolicyStore) -> None:
        store.create_feedback_memo("policies", "values", None, "First")
        store.create_feedback_memo("policies", "values", None, "Second")

        pending = store.get_pending_memos("values")
        assert len(pending) == 2
        assert pending[0].content == "First"
        assert pending[1].content == "Second"

    def test_excludes_accepted_and_dismissed(self, store: PolicyStore) -> None:
        store.create_feedback_memo("policies", "values", None, "Pending")
        id2 = store.create_feedback_memo("policies", "values", None, "Accepted")
        id3 = store.create_feedback_memo("policies", "values", None, "Dismissed")

        store.update_memo_status(id2, "accepted")
        store.update_memo_status(id3, "dismissed")

        pending = store.get_pending_memos("values")
        assert len(pending) == 1
        assert pending[0].content == "Pending"

    def test_returns_empty_for_no_pending(self, store: PolicyStore) -> None:
        pending = store.get_pending_memos("values")
        assert pending == []


# ---------------------------------------------------------------------------
# Pending memo count tests
# ---------------------------------------------------------------------------


class TestGetPendingMemoCount:
    """Tests for get_pending_memo_count."""

    def test_returns_correct_count(self, store: PolicyStore) -> None:
        store.create_feedback_memo("policies", "values", None, "A")
        store.create_feedback_memo("policies", "values", None, "B")
        store.create_feedback_memo("policies", "tactical-objectives", None, "C")

        assert store.get_pending_memo_count("values") == 2
        assert store.get_pending_memo_count("tactical-objectives") == 1

    def test_returns_zero_when_no_memos(self, store: PolicyStore) -> None:
        assert store.get_pending_memo_count("values") == 0

    def test_excludes_non_pending(self, store: PolicyStore) -> None:
        id1 = store.create_feedback_memo("policies", "values", None, "A")
        store.create_feedback_memo("policies", "values", None, "B")
        store.update_memo_status(id1, "accepted")

        assert store.get_pending_memo_count("values") == 1


# ---------------------------------------------------------------------------
# Status update tests
# ---------------------------------------------------------------------------


class TestUpdateMemoStatus:
    """Tests for update_memo_status."""

    def test_updates_to_accepted(self, store: PolicyStore) -> None:
        memo_id = store.create_feedback_memo("policies", "values", None, "Test")
        result = store.update_memo_status(memo_id, "accepted")
        assert result is True

        memo = store.get_memo(memo_id)
        assert memo is not None
        assert memo.status == "accepted"

    def test_updates_to_dismissed(self, store: PolicyStore) -> None:
        memo_id = store.create_feedback_memo("policies", "values", None, "Test")
        result = store.update_memo_status(memo_id, "dismissed")
        assert result is True

        memo = store.get_memo(memo_id)
        assert memo is not None
        assert memo.status == "dismissed"

    def test_sets_resolved_timestamp(self, store: PolicyStore) -> None:
        memo_id = store.create_feedback_memo("policies", "values", None, "Test")
        store.update_memo_status(memo_id, "accepted")

        memo = store.get_memo(memo_id)
        assert memo is not None
        assert memo.resolved_at is not None

    def test_returns_false_for_nonexistent_memo(self, store: PolicyStore) -> None:
        result = store.update_memo_status("nonexistent-id", "accepted")
        assert result is False


# ---------------------------------------------------------------------------
# Batch update tests
# ---------------------------------------------------------------------------


class TestBatchUpdateMemoStatus:
    """Tests for batch_update_memo_status."""

    def test_updates_multiple_memos(self, store: PolicyStore) -> None:
        id1 = store.create_feedback_memo("policies", "values", None, "A")
        id2 = store.create_feedback_memo("policies", "values", None, "B")
        id3 = store.create_feedback_memo("policies", "values", None, "C")

        count = store.batch_update_memo_status([id1, id2], "accepted")
        assert count == 2

        memo1 = store.get_memo(id1)
        memo2 = store.get_memo(id2)
        memo3 = store.get_memo(id3)
        assert memo1 is not None and memo1.status == "accepted"
        assert memo2 is not None and memo2.status == "accepted"
        assert memo3 is not None and memo3.status == "pending"

    def test_sets_resolved_timestamp_for_all(self, store: PolicyStore) -> None:
        id1 = store.create_feedback_memo("policies", "values", None, "A")
        id2 = store.create_feedback_memo("policies", "values", None, "B")

        store.batch_update_memo_status([id1, id2], "dismissed")

        for mid in [id1, id2]:
            memo = store.get_memo(mid)
            assert memo is not None
            assert memo.resolved_at is not None

    def test_empty_list_returns_zero(self, store: PolicyStore) -> None:
        count = store.batch_update_memo_status([], "accepted")
        assert count == 0


# ---------------------------------------------------------------------------
# Listing with filters tests
# ---------------------------------------------------------------------------


class TestListMemos:
    """Tests for list_memos."""

    def test_filter_by_target_layer(self, store: PolicyStore) -> None:
        store.create_feedback_memo("policies", "values", None, "A")
        store.create_feedback_memo("policies", "tactical-objectives", None, "B")

        memos = store.list_memos(target_layer="values")
        assert len(memos) == 1
        assert memos[0].target_layer == "values"

    def test_filter_by_source_layer(self, store: PolicyStore) -> None:
        store.create_feedback_memo("policies", "values", None, "A")
        store.create_feedback_memo("strategic-objectives", "values", None, "B")

        memos = store.list_memos(source_layer="policies")
        assert len(memos) == 1
        assert memos[0].source_layer == "policies"

    def test_filter_by_status(self, store: PolicyStore) -> None:
        id1 = store.create_feedback_memo("policies", "values", None, "A")
        store.create_feedback_memo("policies", "values", None, "B")
        store.update_memo_status(id1, "accepted")

        memos = store.list_memos(memo_status="pending")
        assert len(memos) == 1
        assert memos[0].status == "pending"

    def test_filter_by_cascade_id(self, store: PolicyStore) -> None:
        store.create_feedback_memo("policies", "values", "cascade-1", "A")
        store.create_feedback_memo("policies", "values", "cascade-2", "B")

        memos = store.list_memos(cascade_id="cascade-1")
        assert len(memos) == 1
        assert memos[0].cascade_id == "cascade-1"

    def test_pagination(self, store: PolicyStore) -> None:
        for i in range(5):
            store.create_feedback_memo("policies", "values", None, f"Memo {i}")

        page1 = store.list_memos(limit=2, offset=0)
        page2 = store.list_memos(limit=2, offset=2)
        assert len(page1) == 2
        assert len(page2) == 2

    def test_reverse_chronological_order(self, store: PolicyStore) -> None:
        store.create_feedback_memo("policies", "values", None, "First")
        store.create_feedback_memo("policies", "values", None, "Second")

        memos = store.list_memos()
        # Reverse chronological = newest first
        assert memos[0].content == "Second"
        assert memos[1].content == "First"


# ---------------------------------------------------------------------------
# get_memo tests
# ---------------------------------------------------------------------------


class TestGetMemo:
    """Tests for get_memo."""

    def test_returns_memo_by_id(self, store: PolicyStore) -> None:
        memo_id = store.create_feedback_memo("policies", "values", None, "Test content")
        memo = store.get_memo(memo_id)
        assert memo is not None
        assert memo.id == memo_id
        assert memo.content == "Test content"

    def test_returns_none_for_nonexistent(self, store: PolicyStore) -> None:
        memo = store.get_memo("nonexistent-id")
        assert memo is None
