"""Integration tests for frontend-backend API contract.

API-level tests (using TestClient, not a browser) that verify the response
shapes the frontend expects from each endpoint.
"""

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
from policy_factory.server.ws import ConnectionManager
from policy_factory.store import PolicyStore


@pytest.fixture(autouse=True)
def _configure_auth():
    original_key = auth_mod.JWT_SECRET_KEY
    original_expiry = auth_mod.JWT_EXPIRY_HOURS
    auth_mod.JWT_SECRET_KEY = "test-secret-key-for-contract-tests"
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
        (d / slug / "README.md").write_text(f"# {slug}\n\nNarrative summary for {slug}.")
    return d


@pytest.fixture
def client(
    store: PolicyStore, data_dir: Path
) -> Generator[TestClient, None, None]:
    app = create_app(
        store=store,
        data_dir=data_dir,
        event_emitter=EventEmitter(),
        ws_manager=ConnectionManager(),
    )
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_headers(store: PolicyStore) -> dict[str, str]:
    hashed = hash_password("testpassword")
    user_id = store.create_user("test@example.com", hashed, "admin")
    token = create_access_token(user_id, "test@example.com", "admin")
    return {"Authorization": f"Bearer {token}"}


class TestLoginResponseShape:
    """Login endpoint returns the shape the frontend auth store expects."""

    def test_login_response_has_token_and_user(
        self, client: TestClient, store: PolicyStore
    ) -> None:
        """Login returns {token: string, user: {id, email, role, created_at}}."""
        hashed = hash_password("password123")
        store.create_user("shape@test.com", hashed, "admin")

        resp = client.post(
            "/api/auth/login",
            json={"email": "shape@test.com", "password": "password123"},
        )
        assert resp.status_code == 200
        data = resp.json()

        # Required fields for frontend auth store
        assert "token" in data
        assert isinstance(data["token"], str)
        assert len(data["token"]) > 0

        assert "user" in data
        user = data["user"]
        assert "id" in user
        assert "email" in user
        assert "role" in user
        assert "created_at" in user


class TestLayersListingResponseShape:
    """Layers listing returns the shape the frontend layer store expects."""

    def test_layers_listing_shape(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        """GET /api/layers/ returns array with metadata per layer."""
        resp = client.get("/api/layers/", headers=auth_headers)
        assert resp.status_code == 200
        layers = resp.json()

        assert isinstance(layers, list)
        assert len(layers) == 6  # All 6 layers

        for layer in layers:
            # Required fields the frontend expects
            assert "slug" in layer
            assert "display_name" in layer or "name" in layer
            assert "item_count" in layer or "items" in layer
            assert "position" in layer


class TestCascadeStatusResponseShape:
    """Cascade status returns the shape the frontend cascade store expects."""

    def test_cascade_status_shape(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        """GET /api/cascade/status returns status and queue info."""
        resp = client.get("/api/cascade/status", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()

        # The frontend expects at minimum a status indication
        assert isinstance(data, dict)
        # Should have some status field
        has_status = any(
            key in data
            for key in ["status", "active", "running", "cascade_id", "is_running"]
        )
        assert has_status, f"Missing status field in cascade status: {data.keys()}"


class TestIdeasListingResponseShape:
    """Ideas listing returns the shape the frontend idea store expects."""

    def test_ideas_listing_shape(
        self, client: TestClient, auth_headers: dict[str, str], store: PolicyStore
    ) -> None:
        """GET /api/ideas/ returns array of ideas with expected fields."""
        # Create a test idea
        store.create_idea(
            text="Test idea for shape check",
            source="human",
            submitted_by="test@example.com",
        )

        resp = client.get("/api/ideas/", headers=auth_headers)
        assert resp.status_code == 200
        ideas = resp.json()

        assert isinstance(ideas, list)
        assert len(ideas) >= 1

        idea = ideas[0]
        # Required fields the frontend expects
        assert "id" in idea or "idea_id" in idea
        assert "text" in idea
        assert "status" in idea
        assert "source" in idea


class TestIdeaDetailResponseShape:
    """Idea detail returns scores when available."""

    def test_idea_detail_with_scores(
        self, client: TestClient, auth_headers: dict[str, str], store: PolicyStore
    ) -> None:
        """GET /api/ideas/:id returns idea with scores when evaluated."""
        idea_id = store.create_idea(
            text="Scored idea",
            source="human",
            submitted_by="test@test.com",
        )
        store.store_scores(
            idea_id=idea_id,
            strategic_fit=8.0, feasibility=7.0, cost=6.0,
            risk=5.0, public_acceptance=9.0, international_impact=7.5,
        )
        store.update_idea_status(idea_id, "evaluated")

        resp = client.get(f"/api/ideas/{idea_id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()

        # Should have scores
        scores = data.get("scores")
        assert scores is not None
        assert "strategic_fit" in scores
        assert "feasibility" in scores
