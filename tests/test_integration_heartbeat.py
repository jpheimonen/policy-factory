"""Integration tests for heartbeat tier escalation (with mocked agents).

Tests the tiered heartbeat system: Tier 1 "nothing noteworthy" stops at tier 1,
Tier 1+2 "no action" stops at tier 2, full escalation triggers cascade.
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
    auth_mod.JWT_SECRET_KEY = "test-secret-key-for-heartbeat-integration"
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


class TestHeartbeatTier1NoEscalation:
    """Tier 1 returns 'nothing noteworthy' — stops at tier 1."""

    def test_tier1_nothing_noteworthy_logged(self, store: PolicyStore) -> None:
        """Create a heartbeat run that stops at tier 1."""
        run_id = store.create_heartbeat_run(trigger="manual")
        store.update_heartbeat_tier(
            run_id=run_id,
            tier=1,
            escalated=False,
            outcome="nothing_noteworthy",
        )
        store.complete_heartbeat_run(run_id)

        run = store.get_heartbeat_run(run_id)
        assert run is not None
        assert run.highest_tier == 1

    def test_tier1_run_in_history(self, store: PolicyStore) -> None:
        """Tier 1 run appears in heartbeat history."""
        run_id = store.create_heartbeat_run(trigger="manual")
        store.update_heartbeat_tier(
            run_id=run_id,
            tier=1,
            escalated=False,
            outcome="nothing_noteworthy",
        )
        store.complete_heartbeat_run(run_id)

        runs = store.list_heartbeat_runs(limit=10)
        assert len(runs) >= 1
        assert any(r.id == run_id for r in runs)


class TestHeartbeatTier2NoEscalation:
    """Tier 1 flags items, Tier 2 returns no actionable items — stops at tier 2."""

    def test_tier2_no_action_logged(self, store: PolicyStore) -> None:
        """Create a heartbeat run that escalates to tier 2 then stops."""
        run_id = store.create_heartbeat_run(trigger="scheduled")
        store.update_heartbeat_tier(
            run_id=run_id,
            tier=1,
            escalated=True,
            outcome="Policy change in EU trade agreements flagged",
        )
        store.update_heartbeat_tier(
            run_id=run_id,
            tier=2,
            escalated=False,
            outcome="no_action",
        )
        store.complete_heartbeat_run(run_id)

        run = store.get_heartbeat_run(run_id)
        assert run is not None
        assert run.highest_tier == 2


class TestHeartbeatFullEscalation:
    """Full escalation through all 4 tiers triggers cascade."""

    def test_full_escalation_logged_with_tier4(self, store: PolicyStore) -> None:
        """Full escalation records highest tier = 4 with cascade reference."""
        run_id = store.create_heartbeat_run(trigger="scheduled")

        # Tier 1: flags items
        store.update_heartbeat_tier(
            run_id=run_id,
            tier=1,
            escalated=True,
            outcome="Major defense spending bill announced",
        )

        # Tier 2: recommends updates
        store.update_heartbeat_tier(
            run_id=run_id,
            tier=2,
            escalated=True,
            outcome="Update SA with defense spending context",
        )

        # Tier 3: updates SA
        store.update_heartbeat_tier(
            run_id=run_id,
            tier=3,
            escalated=True,
            outcome="Updated situational-awareness files",
        )

        # Tier 4: cascade triggered
        cascade_id = store.create_cascade(
            trigger_source="heartbeat",
            starting_layer="situational-awareness",
        )
        store.update_heartbeat_tier(
            run_id=run_id,
            tier=4,
            escalated=False,
            outcome=f"cascade_triggered: cascade_id={cascade_id}",
        )
        store.complete_heartbeat_run(run_id)

        run = store.get_heartbeat_run(run_id)
        assert run is not None
        assert run.highest_tier == 4
        # Verify structured log has all 4 tiers
        assert len(run.structured_log) == 4
