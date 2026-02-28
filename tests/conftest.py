"""Shared test fixtures for Policy Factory tests.

Provides reusable fixtures for:
- Temp database and data directory setup
- Authenticated test clients (admin and regular user)
- Mock agent session factory for deterministic agent output
- EventEmitter and WebSocket infrastructure
"""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

import policy_factory.auth as auth_mod
from policy_factory.auth import create_access_token, hash_password
from policy_factory.data.init import initialize_data_directory
from policy_factory.data.layers import LAYER_SLUGS
from policy_factory.events import EventEmitter
from policy_factory.server.app import create_app
from policy_factory.server.broadcast import BroadcastHandler
from policy_factory.server.ws import ConnectionManager
from policy_factory.store import PolicyStore


# ---------------------------------------------------------------------------
# Basic fixtures (preserved from original for backward compatibility)
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_db_path(tmp_path: Path) -> Path:
    """Provide a temporary database path for testing."""
    return tmp_path / "test_store.db"


@pytest.fixture
def store(tmp_db_path: Path) -> PolicyStore:
    """Provide a fresh PolicyStore instance with an in-memory-like temporary database."""
    return PolicyStore(tmp_db_path)


# ---------------------------------------------------------------------------
# Auth configuration fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def configure_auth():
    """Set JWT_SECRET_KEY for tests. Use as a dependency in integration tests."""
    original_key = auth_mod.JWT_SECRET_KEY
    original_expiry = auth_mod.JWT_EXPIRY_HOURS
    auth_mod.JWT_SECRET_KEY = "test-secret-key-for-integration-tests"
    auth_mod.JWT_EXPIRY_HOURS = 24
    yield
    auth_mod.JWT_SECRET_KEY = original_key
    auth_mod.JWT_EXPIRY_HOURS = original_expiry


# ---------------------------------------------------------------------------
# Data directory fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """Create a temporary data directory with the five-layer subdirectory structure.

    Includes an initialized git repo and pre-seeded values files,
    mimicking first-run initialization.
    """
    d = tmp_path / "data"
    initialize_data_directory(d)
    return d


@pytest.fixture
def empty_data_dir(tmp_path: Path) -> Path:
    """Create a temporary data directory with just layer subdirectories (no git, no seeds).

    Useful for tests that don't need the full initialization overhead.
    """
    d = tmp_path / "data"
    for slug in LAYER_SLUGS:
        (d / slug).mkdir(parents=True, exist_ok=True)
        (d / slug / "README.md").write_text(f"# {slug}\n\nSummary.")
    return d


# ---------------------------------------------------------------------------
# Event infrastructure
# ---------------------------------------------------------------------------


@pytest.fixture
def event_emitter() -> EventEmitter:
    """Provide a fresh EventEmitter instance."""
    return EventEmitter()


@pytest.fixture
def ws_manager() -> ConnectionManager:
    """Provide a fresh WebSocket ConnectionManager."""
    return ConnectionManager()


# ---------------------------------------------------------------------------
# Fully configured test clients
# ---------------------------------------------------------------------------


@pytest.fixture
def integration_app(
    store: PolicyStore,
    event_emitter: EventEmitter,
    ws_manager: ConnectionManager,
    empty_data_dir: Path,
    configure_auth: None,
) -> Any:
    """Create a fully configured FastAPI app for integration testing."""
    app = create_app(
        store=store,
        event_emitter=event_emitter,
        ws_manager=ws_manager,
        data_dir=empty_data_dir,
    )
    return app


@pytest.fixture
def integration_client(
    store: PolicyStore,
    event_emitter: EventEmitter,
    ws_manager: ConnectionManager,
    empty_data_dir: Path,
    configure_auth: None,
) -> Generator[TestClient, None, None]:
    """Provide a TestClient with all dependencies wired up."""
    app = create_app(
        store=store,
        event_emitter=event_emitter,
        ws_manager=ws_manager,
        data_dir=empty_data_dir,
    )
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# User fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def admin_user_data(store: PolicyStore, configure_auth: None) -> dict[str, str]:
    """Register an admin user and return their info + JWT.

    Returns dict with keys: id, email, token, password.
    """
    password = "adminpassword123"
    hashed = hash_password(password)
    user_id = store.create_user("admin@test.com", hashed, "admin")
    token = create_access_token(user_id, "admin@test.com", "admin")
    return {
        "id": user_id,
        "email": "admin@test.com",
        "token": token,
        "password": password,
    }


@pytest.fixture
def regular_user_data(store: PolicyStore, configure_auth: None) -> dict[str, str]:
    """Register a regular (non-admin) user and return their info + JWT.

    Returns dict with keys: id, email, token, password.
    """
    password = "userpassword123"
    hashed = hash_password(password)
    user_id = store.create_user("user@test.com", hashed, "user")
    token = create_access_token(user_id, "user@test.com", "user")
    return {
        "id": user_id,
        "email": "user@test.com",
        "token": token,
        "password": password,
    }


@pytest.fixture
def admin_headers(admin_user_data: dict[str, str]) -> dict[str, str]:
    """Return Authorization headers for the admin user."""
    return {"Authorization": f"Bearer {admin_user_data['token']}"}


@pytest.fixture
def user_headers(regular_user_data: dict[str, str]) -> dict[str, str]:
    """Return Authorization headers for the regular user."""
    return {"Authorization": f"Bearer {regular_user_data['token']}"}


# ---------------------------------------------------------------------------
# Authenticated test clients
# ---------------------------------------------------------------------------


@pytest.fixture
def admin_client(
    store: PolicyStore,
    event_emitter: EventEmitter,
    ws_manager: ConnectionManager,
    empty_data_dir: Path,
    admin_user_data: dict[str, str],
) -> Generator[TestClient, None, None]:
    """TestClient pre-configured with admin user JWT in headers."""
    app = create_app(
        store=store,
        event_emitter=event_emitter,
        ws_manager=ws_manager,
        data_dir=empty_data_dir,
    )
    with TestClient(app) as c:
        c.headers.update({"Authorization": f"Bearer {admin_user_data['token']}"})
        yield c


@pytest.fixture
def user_client(
    store: PolicyStore,
    event_emitter: EventEmitter,
    ws_manager: ConnectionManager,
    empty_data_dir: Path,
    regular_user_data: dict[str, str],
) -> Generator[TestClient, None, None]:
    """TestClient pre-configured with regular user JWT in headers."""
    app = create_app(
        store=store,
        event_emitter=event_emitter,
        ws_manager=ws_manager,
        data_dir=empty_data_dir,
    )
    with TestClient(app) as c:
        c.headers.update({"Authorization": f"Bearer {regular_user_data['token']}"})
        yield c


# ---------------------------------------------------------------------------
# Mock agent session factory
# ---------------------------------------------------------------------------


def create_mock_agent_result(
    output: str = "Mock agent output",
    success: bool = True,
    error: str | None = None,
) -> Any:
    """Create a mock AgentResult-like object."""
    result = MagicMock()
    result.output = output
    result.success = success
    result.error = error
    result.cost_usd = 0.001
    return result


def make_mock_generation_runner(data_dir: Path) -> AsyncMock:
    """Create a mock generation runner that writes predictable markdown files.

    The mock writes a deterministic item to the target layer directory
    so downstream assertions can verify file content.
    """

    async def _mock_runner(
        layer_slug: str,
        context: str,
        store: Any,
        emitter: Any,
        data_dir_arg: Path,
        **kwargs: Any,
    ) -> str:
        """Mock generation runner that writes a predictable file."""
        layer_dir = data_dir / layer_slug
        layer_dir.mkdir(parents=True, exist_ok=True)

        filename = f"mock-generated-{layer_slug}.md"
        content = f"""---
title: Mock Generated Item for {layer_slug}
status: draft
created_at: "2025-01-01T00:00:00Z"
last_modified: "2025-01-01T00:00:00Z"
last_modified_by: mock-agent
references: []
---

# Mock Generated Content

This is mock-generated content for the {layer_slug} layer.
Context provided: {context[:100] if context else 'none'}
"""
        (layer_dir / filename).write_text(content)

        # Also write/update README.md narrative
        (layer_dir / "README.md").write_text(
            f"# {layer_slug}\n\nMock narrative summary for {layer_slug}.\n"
        )

        return f"Generated mock content for {layer_slug}"

    mock = AsyncMock(side_effect=_mock_runner)
    return mock


def make_mock_critic_runner() -> AsyncMock:
    """Create a mock critic runner that returns deterministic assessments.

    Returns structured assessment text for each of the 6 critics.
    """
    critic_archetypes = [
        "realist",
        "liberal-institutionalist",
        "nationalist-conservative",
        "social-democratic",
        "libertarian",
        "green-ecological",
    ]

    async def _mock_critic(
        layer_slug: str,
        cascade_id: str,
        store: Any,
        emitter: Any,
        data_dir: Path,
        **kwargs: Any,
    ) -> list[dict[str, str]]:
        """Mock critic runner returning deterministic results."""
        results = []
        for archetype in critic_archetypes:
            result = {
                "archetype": archetype,
                "assessment": f"Mock {archetype} assessment for {layer_slug}. "
                f"This perspective finds the content generally acceptable "
                f"with minor concerns about implementation specifics.",
                "agreement": "partial",
                "alternatives": f"Consider {archetype}-aligned alternatives.",
            }
            results.append(result)

            # Store the critic result in the database
            store.store_critic_result(
                cascade_id=cascade_id,
                layer_slug=layer_slug,
                idea_id=None,
                archetype=archetype,
                assessment_text=result["assessment"],
                structured_assessment={
                    "agreement": result["agreement"],
                    "alternatives": result["alternatives"],
                },
                agent_run_id=None,
            )

        return results

    mock = AsyncMock(side_effect=_mock_critic)
    return mock


def make_mock_synthesis_runner() -> AsyncMock:
    """Create a mock synthesis runner that returns a balanced assessment."""

    async def _mock_synthesis(
        layer_slug: str,
        cascade_id: str,
        critic_results: list[dict[str, str]],
        store: Any,
        emitter: Any,
        **kwargs: Any,
    ) -> str:
        """Mock synthesis runner returning a deterministic synthesis."""
        synthesis_text = (
            f"Mock synthesis for {layer_slug}: After reviewing all 6 critic "
            f"perspectives, the content is generally well-balanced. Key tensions "
            f"exist between security-focused and cooperation-focused viewpoints. "
            f"No critical issues require immediate attention."
        )

        # Store the synthesis result
        store.store_synthesis_result(
            cascade_id=cascade_id,
            layer_slug=layer_slug,
            idea_id=None,
            synthesis_text=synthesis_text,
            structured_synthesis=None,
            agent_run_id=None,
        )

        return synthesis_text

    mock = AsyncMock(side_effect=_mock_synthesis)
    return mock


def make_mock_heartbeat_tier_runner(
    tier1_escalate: bool = False,
    tier2_escalate: bool = False,
    tier3_escalate: bool = False,
) -> dict[str, AsyncMock]:
    """Create mock heartbeat tier runners with configurable escalation.

    Args:
        tier1_escalate: Whether Tier 1 should flag items for Tier 2.
        tier2_escalate: Whether Tier 2 should recommend updates for Tier 3.
        tier3_escalate: Whether Tier 3 should trigger Tier 4 cascade.

    Returns:
        Dict mapping tier names to mock runners.
    """
    tier1 = AsyncMock()
    if tier1_escalate:
        tier1.return_value = {
            "escalate": True,
            "flagged_items": ["Item A: Major policy change detected"],
        }
    else:
        tier1.return_value = {
            "escalate": False,
            "flagged_items": [],
        }

    tier2 = AsyncMock()
    if tier2_escalate:
        tier2.return_value = {
            "escalate": True,
            "actionable_items": ["Update SA with new trade agreement details"],
        }
    else:
        tier2.return_value = {
            "escalate": False,
            "actionable_items": [],
        }

    tier3 = AsyncMock()
    if tier3_escalate:
        tier3.return_value = {
            "escalate": True,
            "updates_made": ["Updated situational-awareness/trade-policy.md"],
        }
    else:
        tier3.return_value = {
            "escalate": False,
            "updates_made": [],
        }

    return {
        "tier1": tier1,
        "tier2": tier2,
        "tier3": tier3,
    }
