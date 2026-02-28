"""Tests for the seed REST API router."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import policy_factory.auth as auth_mod
from policy_factory.auth import create_access_token, hash_password
from policy_factory.data.layers import LAYER_SLUGS
from policy_factory.events import EventEmitter
from policy_factory.server.app import create_app
from policy_factory.store import PolicyStore

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _configure_auth():
    """Set JWT_SECRET_KEY for all tests."""
    original_key = auth_mod.JWT_SECRET_KEY
    original_expiry = auth_mod.JWT_EXPIRY_HOURS
    auth_mod.JWT_SECRET_KEY = "test-secret-key-for-seed-api-tests"
    auth_mod.JWT_EXPIRY_HOURS = 24
    yield
    auth_mod.JWT_SECRET_KEY = original_key
    auth_mod.JWT_EXPIRY_HOURS = original_expiry


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    d = tmp_path / "data"
    for slug in LAYER_SLUGS:
        (d / slug).mkdir(parents=True, exist_ok=True)
    return d


@pytest.fixture
def store(tmp_path: Path) -> PolicyStore:
    return PolicyStore(tmp_path / "test.db")


@pytest.fixture
def emitter() -> EventEmitter:
    return EventEmitter()


@pytest.fixture
def client(
    store: PolicyStore, emitter: EventEmitter, data_dir: Path
) -> Generator[TestClient, None, None]:
    app = create_app(store=store, event_emitter=emitter, data_dir=data_dir)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_headers(store: PolicyStore) -> dict[str, str]:
    hashed = hash_password("testpassword")
    user_id = store.create_user("test@example.com", hashed, "admin")
    token = create_access_token(user_id, "test@example.com", "admin")
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Seed status tests
# ---------------------------------------------------------------------------


class TestSeedStatus:
    """Tests for GET /api/seed/status."""

    def test_requires_auth(self, client: TestClient) -> None:
        resp = client.get("/api/seed/status")
        assert resp.status_code == 401

    def test_returns_not_seeded_for_empty_sa(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        resp = client.get("/api/seed/status", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["seeded"] is False
        assert data["item_count"] == 0

    def test_returns_seeded_when_sa_has_items(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        data_dir: Path,
    ) -> None:
        # Add an item to SA
        sa_dir = data_dir / "situational-awareness"
        (sa_dir / "geopolitics.md").write_text(
            "---\ntitle: Geopolitics\nstatus: current\n---\nContent"
        )

        resp = client.get("/api/seed/status", headers=auth_headers)
        data = resp.json()
        assert data["seeded"] is True
        assert data["item_count"] == 1


# ---------------------------------------------------------------------------
# Seed trigger tests
# ---------------------------------------------------------------------------


class TestTriggerSeed:
    """Tests for POST /api/seed/."""

    def test_requires_auth(self, client: TestClient) -> None:
        resp = client.post("/api/seed/")
        assert resp.status_code == 401

    def test_returns_409_if_already_seeded(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        data_dir: Path,
    ) -> None:
        # Add an item to SA to simulate existing content
        sa_dir = data_dir / "situational-awareness"
        (sa_dir / "geopolitics.md").write_text(
            "---\ntitle: Geopolitics\nstatus: current\n---\nContent"
        )

        resp = client.post("/api/seed/", headers=auth_headers)
        assert resp.status_code == 409
