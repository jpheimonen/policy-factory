"""Tests for the heartbeat store mixin."""

from policy_factory.store import PolicyStore
from policy_factory.store.heartbeat import HeartbeatRun, TierEntry


class TestHeartbeatMixin:
    """Tests for HeartbeatMixin methods."""

    def test_create_heartbeat_run_manual(self, store: PolicyStore) -> None:
        """Creating a heartbeat run with manual trigger sets correct fields."""
        run_id = store.create_heartbeat_run("manual")

        assert run_id
        run = store.get_heartbeat_run(run_id)
        assert run is not None
        assert run.id == run_id
        assert run.trigger == "manual"
        assert run.highest_tier == 0
        assert run.completed_at is None
        assert run.structured_log == []

    def test_create_heartbeat_run_scheduled(self, store: PolicyStore) -> None:
        """Creating a heartbeat run with scheduled trigger works."""
        run_id = store.create_heartbeat_run("scheduled")

        run = store.get_heartbeat_run(run_id)
        assert run is not None
        assert run.trigger == "scheduled"

    def test_update_heartbeat_tier(self, store: PolicyStore) -> None:
        """Updating a tier appends to the structured log and updates highest_tier."""
        run_id = store.create_heartbeat_run("manual")

        store.update_heartbeat_tier(
            run_id, tier=1, escalated=True,
            outcome="Flagged 3 items", agent_run_id="agent-1",
        )

        run = store.get_heartbeat_run(run_id)
        assert run is not None
        assert run.highest_tier == 1
        assert len(run.structured_log) == 1

        entry = run.structured_log[0]
        assert entry.tier == 1
        assert entry.escalated is True
        assert entry.outcome == "Flagged 3 items"
        assert entry.agent_run_id == "agent-1"
        assert entry.started_at is not None

    def test_update_multiple_tiers(self, store: PolicyStore) -> None:
        """Multiple tier updates append to the structured log."""
        run_id = store.create_heartbeat_run("scheduled")

        store.update_heartbeat_tier(
            run_id, tier=1, escalated=True,
            outcome="Flagged items", agent_run_id="a1",
        )
        store.update_heartbeat_tier(
            run_id, tier=2, escalated=True,
            outcome="Updates warranted", agent_run_id="a2",
        )
        store.update_heartbeat_tier(
            run_id, tier=3, escalated=True,
            outcome="SA updated", agent_run_id="a3",
        )
        store.update_heartbeat_tier(
            run_id, tier=4, escalated=False,
            outcome="Cascade triggered",
        )

        run = store.get_heartbeat_run(run_id)
        assert run is not None
        assert run.highest_tier == 4
        assert len(run.structured_log) == 4

        # Check order
        assert run.structured_log[0].tier == 1
        assert run.structured_log[1].tier == 2
        assert run.structured_log[2].tier == 3
        assert run.structured_log[3].tier == 4

        # Tier 4 should not escalate
        assert run.structured_log[3].escalated is False

    def test_complete_heartbeat_run(self, store: PolicyStore) -> None:
        """Completing a heartbeat run sets the completed_at timestamp."""
        run_id = store.create_heartbeat_run("manual")

        store.update_heartbeat_tier(
            run_id, tier=1, escalated=False,
            outcome="Nothing noteworthy",
        )
        store.complete_heartbeat_run(run_id)

        run = store.get_heartbeat_run(run_id)
        assert run is not None
        assert run.completed_at is not None

    def test_get_nonexistent_heartbeat_run(self, store: PolicyStore) -> None:
        """Getting a nonexistent run returns None."""
        result = store.get_heartbeat_run("nonexistent-id")
        assert result is None

    def test_list_heartbeat_runs_empty(self, store: PolicyStore) -> None:
        """Listing runs when none exist returns empty list."""
        runs = store.list_heartbeat_runs()
        assert runs == []

    def test_list_heartbeat_runs_order(self, store: PolicyStore) -> None:
        """Listing runs returns them in reverse chronological order."""
        id1 = store.create_heartbeat_run("scheduled")
        store.complete_heartbeat_run(id1)

        id2 = store.create_heartbeat_run("manual")
        store.complete_heartbeat_run(id2)

        id3 = store.create_heartbeat_run("scheduled")

        runs = store.list_heartbeat_runs()
        assert len(runs) == 3
        # Most recent first
        assert runs[0].id == id3
        assert runs[1].id == id2
        assert runs[2].id == id1

    def test_list_heartbeat_runs_with_limit(self, store: PolicyStore) -> None:
        """Listing with a limit returns only the specified number of runs."""
        for _ in range(5):
            run_id = store.create_heartbeat_run("scheduled")
            store.complete_heartbeat_run(run_id)

        runs = store.list_heartbeat_runs(limit=3)
        assert len(runs) == 3

    def test_list_heartbeat_runs_with_offset(self, store: PolicyStore) -> None:
        """Listing with offset skips the specified number of runs."""
        ids = []
        for _ in range(5):
            run_id = store.create_heartbeat_run("scheduled")
            store.complete_heartbeat_run(run_id)
            ids.append(run_id)

        runs = store.list_heartbeat_runs(limit=2, offset=2)
        assert len(runs) == 2

    def test_get_latest_heartbeat_run_empty(self, store: PolicyStore) -> None:
        """Getting latest when none exist returns None."""
        result = store.get_latest_heartbeat_run()
        assert result is None

    def test_get_latest_heartbeat_run(self, store: PolicyStore) -> None:
        """Getting latest returns the most recent run."""
        id1 = store.create_heartbeat_run("scheduled")
        store.complete_heartbeat_run(id1)

        id2 = store.create_heartbeat_run("manual")

        latest = store.get_latest_heartbeat_run()
        assert latest is not None
        assert latest.id == id2

    def test_has_running_heartbeat_false(self, store: PolicyStore) -> None:
        """No running heartbeat when all runs are completed."""
        run_id = store.create_heartbeat_run("scheduled")
        store.complete_heartbeat_run(run_id)

        assert store.has_running_heartbeat() is False

    def test_has_running_heartbeat_true(self, store: PolicyStore) -> None:
        """Detects a running heartbeat (uncompleted run)."""
        store.create_heartbeat_run("manual")

        assert store.has_running_heartbeat() is True

    def test_has_running_heartbeat_empty(self, store: PolicyStore) -> None:
        """No running heartbeat when no runs exist."""
        assert store.has_running_heartbeat() is False

    def test_update_nonexistent_run_does_not_error(self, store: PolicyStore) -> None:
        """Updating a nonexistent run is a no-op (doesn't raise)."""
        store.update_heartbeat_tier(
            "nonexistent", tier=1, escalated=False,
            outcome="test",
        )
        # No exception = success

    def test_tier_entry_dataclass(self) -> None:
        """TierEntry dataclass has correct default values."""
        entry = TierEntry(tier=1, escalated=True, outcome="Test")
        assert entry.agent_run_id is None
        assert entry.started_at is None
        assert entry.ended_at is None

    def test_heartbeat_run_dataclass(self) -> None:
        """HeartbeatRun dataclass has correct default values."""
        from datetime import datetime, timezone

        run = HeartbeatRun(
            id="test",
            trigger="manual",
            started_at=datetime.now(timezone.utc),
            completed_at=None,
            highest_tier=0,
        )
        assert run.structured_log == []

    def test_structured_log_preserves_data(self, store: PolicyStore) -> None:
        """Structured log correctly round-trips through JSON."""
        run_id = store.create_heartbeat_run("manual")

        store.update_heartbeat_tier(
            run_id, tier=1, escalated=True,
            outcome="Flagged EU AI Act and cybersecurity developments",
            agent_run_id="run-abc123",
        )

        run = store.get_heartbeat_run(run_id)
        assert run is not None
        assert len(run.structured_log) == 1
        entry = run.structured_log[0]
        assert entry.outcome == "Flagged EU AI Act and cybersecurity developments"
        assert entry.agent_run_id == "run-abc123"
