"""Tests for heartbeat scheduler integration (APScheduler + deps.py)."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from policy_factory.events import EventEmitter
from policy_factory.store import PolicyStore


# ---------------------------------------------------------------------------
# Tests for scheduler configuration
# ---------------------------------------------------------------------------


class TestSchedulerConfig:
    """Tests for heartbeat scheduler configuration in deps.py."""

    def test_default_interval_is_4_hours(self) -> None:
        """Default heartbeat interval is 4 hours."""
        from policy_factory.server.deps import _get_heartbeat_interval_hours

        with patch.dict(os.environ, {}, clear=True):
            # Clear the specific env var if it exists
            os.environ.pop("POLICY_FACTORY_HEARTBEAT_INTERVAL_HOURS", None)
            interval = _get_heartbeat_interval_hours()
            assert interval == 4.0

    def test_interval_configurable_via_env(self) -> None:
        """Heartbeat interval is configurable via environment variable."""
        from policy_factory.server.deps import _get_heartbeat_interval_hours

        with patch.dict(
            os.environ, {"POLICY_FACTORY_HEARTBEAT_INTERVAL_HOURS": "6"}
        ):
            interval = _get_heartbeat_interval_hours()
            assert interval == 6.0

    def test_interval_zero_disables(self) -> None:
        """Setting interval to 0 disables the heartbeat."""
        from policy_factory.server.deps import _get_heartbeat_interval_hours

        with patch.dict(
            os.environ, {"POLICY_FACTORY_HEARTBEAT_INTERVAL_HOURS": "0"}
        ):
            interval = _get_heartbeat_interval_hours()
            assert interval == 0.0

    def test_invalid_interval_uses_default(self) -> None:
        """Invalid interval value falls back to default."""
        from policy_factory.server.deps import _get_heartbeat_interval_hours

        with patch.dict(
            os.environ, {"POLICY_FACTORY_HEARTBEAT_INTERVAL_HOURS": "not_a_number"}
        ):
            interval = _get_heartbeat_interval_hours()
            assert interval == 4.0

    def test_init_scheduler_disabled_returns_none(
        self, store: PolicyStore
    ) -> None:
        """init_scheduler returns None when interval is 0."""
        from policy_factory.server.deps import init_scheduler

        emitter = EventEmitter()
        data_dir = Path("/tmp/test-data")

        with patch.dict(
            os.environ, {"POLICY_FACTORY_HEARTBEAT_INTERVAL_HOURS": "0"}
        ):
            scheduler = init_scheduler(store, emitter, data_dir)
            assert scheduler is None

    def test_init_scheduler_creates_scheduler(
        self, store: PolicyStore, tmp_path: Path
    ) -> None:
        """init_scheduler creates an AsyncIOScheduler when enabled."""
        from policy_factory.server.deps import init_scheduler, shutdown_scheduler

        emitter = EventEmitter()

        with patch.dict(
            os.environ, {"POLICY_FACTORY_HEARTBEAT_INTERVAL_HOURS": "2"}
        ):
            scheduler = init_scheduler(store, emitter, tmp_path)
            assert scheduler is not None

            # Verify job was added
            job = scheduler.get_job("heartbeat")
            assert job is not None
            assert job.name == "Heartbeat — tiered news monitoring"

            # Clean up
            shutdown_scheduler()

    def test_get_scheduler_returns_none_before_init(self) -> None:
        """get_scheduler returns None before initialization."""
        from policy_factory.server.deps import get_scheduler

        # Reset global state
        import policy_factory.server.deps as deps
        original = deps._scheduler
        deps._scheduler = None

        try:
            assert get_scheduler() is None
        finally:
            deps._scheduler = original

    def test_shutdown_scheduler_is_safe_when_none(self) -> None:
        """Shutting down a None scheduler is a no-op."""
        from policy_factory.server.deps import shutdown_scheduler

        import policy_factory.server.deps as deps
        original = deps._scheduler
        deps._scheduler = None

        try:
            shutdown_scheduler()  # Should not raise
        finally:
            deps._scheduler = original
