"""Integration tests for first-run initialization.

Tests that starting the app with no data directory creates the full
directory structure and git repo. Values are no longer pre-seeded;
they are populated via explicit seeding with POST /api/seed/values.
"""

from __future__ import annotations

import subprocess
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import policy_factory.auth as auth_mod
from policy_factory.data.layers import LAYER_SLUGS
from policy_factory.events import EventEmitter
from policy_factory.server.app import create_app
from policy_factory.server.ws import ConnectionManager
from policy_factory.store import PolicyStore


@pytest.fixture(autouse=True)
def _configure_auth():
    original_key = auth_mod.JWT_SECRET_KEY
    original_expiry = auth_mod.JWT_EXPIRY_HOURS
    auth_mod.JWT_SECRET_KEY = "test-secret-key-for-first-run"
    auth_mod.JWT_EXPIRY_HOURS = 24
    yield
    auth_mod.JWT_SECRET_KEY = original_key
    auth_mod.JWT_EXPIRY_HOURS = original_expiry


class TestFirstRunInitialization:
    """Starting with no data directory creates the full structure."""

    def test_creates_data_directory_and_git_repo(self, tmp_path: Path) -> None:
        """Start the app with no data directory — verify full structure is created."""
        data_dir = tmp_path / "fresh-data"
        store = PolicyStore(tmp_path / "test.db")

        app = create_app(
            store=store,
            data_dir=data_dir,
            event_emitter=EventEmitter(),
            ws_manager=ConnectionManager(),
        )
        # Trigger lifespan (which initializes the data directory)
        with TestClient(app):
            pass

        # Verify data directory exists
        assert data_dir.exists()

        # Verify git repo is initialized
        git_dir = data_dir / ".git"
        assert git_dir.exists()

        # Verify all five layer subdirectories exist
        for slug in LAYER_SLUGS:
            assert (data_dir / slug).is_dir(), f"Missing layer directory: {slug}"

        # Verify values directory exists but is empty (except for README.md)
        # Values are now populated via explicit seeding, not pre-seeded
        values_dir = data_dir / "values"
        value_files = list(values_dir.glob("*.md"))
        # Should have only README.md placeholder — no pre-seeded values
        non_readme = [f for f in value_files if f.name != "README.md"]
        assert len(non_readme) == 0, "Values directory should be empty after initialization"

        # Verify README.md exists in values directory
        readme = values_dir / "README.md"
        assert readme.exists(), "Missing README.md in values directory"

    def test_existing_data_directory_not_overwritten(self, tmp_path: Path) -> None:
        """Start with an existing populated data directory — verify not re-initialized."""
        data_dir = tmp_path / "existing-data"
        store = PolicyStore(tmp_path / "test.db")

        # Create initial data directory
        app1 = create_app(
            store=store,
            data_dir=data_dir,
            event_emitter=EventEmitter(),
            ws_manager=ConnectionManager(),
        )
        with TestClient(app1):
            pass

        # Add a custom file to verify it's not overwritten
        custom_file = data_dir / "values" / "custom-value.md"
        custom_file.write_text("---\ntitle: Custom\n---\n\nCustom content.\n")

        # Get the git log before second startup
        result_before = subprocess.run(
            ["git", "log", "--oneline"],
            cwd=str(data_dir),
            capture_output=True,
            text=True,
        )
        commit_count_before = len(result_before.stdout.strip().split("\n"))

        # Start the app again
        store2 = PolicyStore(tmp_path / "test2.db")
        app2 = create_app(
            store=store2,
            data_dir=data_dir,
            event_emitter=EventEmitter(),
            ws_manager=ConnectionManager(),
        )
        with TestClient(app2):
            pass

        # Verify custom file still exists
        assert custom_file.exists()
        assert "Custom content" in custom_file.read_text()

        # Verify no additional initialization commits were made
        result_after = subprocess.run(
            ["git", "log", "--oneline"],
            cwd=str(data_dir),
            capture_output=True,
            text=True,
        )
        commit_count_after = len(result_after.stdout.strip().split("\n"))
        assert commit_count_after == commit_count_before
