"""Shared test fixtures for Policy Factory tests."""

from pathlib import Path

import pytest

from policy_factory.store import PolicyStore


@pytest.fixture
def tmp_db_path(tmp_path: Path) -> Path:
    """Provide a temporary database path for testing."""
    return tmp_path / "test_store.db"


@pytest.fixture
def store(tmp_db_path: Path) -> PolicyStore:
    """Provide a fresh PolicyStore instance with an in-memory-like temporary database."""
    return PolicyStore(tmp_db_path)
