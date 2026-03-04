"""Tests for the seed REST API router."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import policy_factory.auth as auth_mod
from policy_factory.agent.session import AgentResult
from policy_factory.auth import create_access_token, hash_password
from policy_factory.data.layers import LAYER_SLUGS, LAYERS
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
# Helpers
# ---------------------------------------------------------------------------


def _find_layer(layers: list[dict], slug: str) -> dict:
    """Find a layer entry by slug in the response layers list."""
    for entry in layers:
        if entry["slug"] == slug:
            return entry
    raise AssertionError(f"Layer {slug!r} not found in response")


# ---------------------------------------------------------------------------
# Seed status tests
# ---------------------------------------------------------------------------


class TestSeedStatus:
    """Tests for GET /api/seed/status."""

    def test_requires_auth(self, client: TestClient) -> None:
        resp = client.get("/api/seed/status")
        assert resp.status_code == 401

    def test_returns_not_seeded_for_empty_layers(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        """Status shows all layers as not seeded when empty."""
        resp = client.get("/api/seed/status", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        layers = data["layers"]
        assert len(layers) == 5
        for entry in layers:
            assert entry["seeded"] is False
            assert entry["count"] == 0

    def test_returns_values_seeded_when_values_has_items(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        data_dir: Path,
    ) -> None:
        """Status correctly reflects populated values layer."""
        # Add items to values layer
        values_dir = data_dir / "values"
        (values_dir / "national-security.md").write_text(
            "---\ntitle: National Security\n---\nSecurity is paramount."
        )
        (values_dir / "economic-prosperity.md").write_text(
            "---\ntitle: Economic Prosperity\n---\nProsperity matters."
        )

        resp = client.get("/api/seed/status", headers=auth_headers)
        layers = resp.json()["layers"]

        values = _find_layer(layers, "values")
        assert values["seeded"] is True
        assert values["count"] == 2

        # SA and upper layers still empty
        sa = _find_layer(layers, "situational-awareness")
        assert sa["seeded"] is False
        assert sa["count"] == 0

        for slug in ("strategic-objectives", "tactical-objectives", "policies"):
            entry = _find_layer(layers, slug)
            assert entry["seeded"] is False

    def test_returns_sa_seeded_when_sa_has_items(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        data_dir: Path,
    ) -> None:
        """Status correctly reflects populated SA layer."""
        # Add an item to SA
        sa_dir = data_dir / "situational-awareness"
        (sa_dir / "geopolitics.md").write_text(
            "---\ntitle: Geopolitics\nstatus: current\n---\nContent"
        )

        resp = client.get("/api/seed/status", headers=auth_headers)
        layers = resp.json()["layers"]

        # Values still empty
        values = _find_layer(layers, "values")
        assert values["seeded"] is False
        assert values["count"] == 0

        # SA has items
        sa = _find_layer(layers, "situational-awareness")
        assert sa["seeded"] is True
        assert sa["count"] == 1

    def test_returns_both_seeded_when_both_have_items(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        data_dir: Path,
    ) -> None:
        """Status correctly reflects when both layers are populated."""
        # Add items to values layer
        values_dir = data_dir / "values"
        (values_dir / "security.md").write_text(
            "---\ntitle: Security\n---\nContent"
        )

        # Add items to SA layer
        sa_dir = data_dir / "situational-awareness"
        (sa_dir / "geopolitics.md").write_text(
            "---\ntitle: Geopolitics\n---\nContent"
        )
        (sa_dir / "technology.md").write_text(
            "---\ntitle: Technology\n---\nContent"
        )

        resp = client.get("/api/seed/status", headers=auth_headers)
        layers = resp.json()["layers"]

        values = _find_layer(layers, "values")
        assert values["seeded"] is True
        assert values["count"] == 1

        sa = _find_layer(layers, "situational-awareness")
        assert sa["seeded"] is True
        assert sa["count"] == 2

    def test_response_contains_exactly_five_layers_in_order(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        """Response contains exactly 5 layers in canonical order."""
        resp = client.get("/api/seed/status", headers=auth_headers)
        assert resp.status_code == 200
        layers = resp.json()["layers"]
        assert len(layers) == 5
        expected_slugs = [
            "values",
            "situational-awareness",
            "strategic-objectives",
            "tactical-objectives",
            "policies",
        ]
        actual_slugs = [entry["slug"] for entry in layers]
        assert actual_slugs == expected_slugs

    def test_layer_entries_include_display_names(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        """Each entry has a display_name matching the canonical LAYERS definition."""
        resp = client.get("/api/seed/status", headers=auth_headers)
        layers = resp.json()["layers"]
        for layer_info in LAYERS:
            entry = _find_layer(layers, layer_info.slug)
            assert entry["display_name"] == layer_info.display_name

    def test_upper_layers_reflect_items_when_populated(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        data_dir: Path,
    ) -> None:
        """Upper layers correctly report items when populated on disk."""
        # Write items to strategic-objectives
        so_dir = data_dir / "strategic-objectives"
        (so_dir / "obj1.md").write_text(
            "---\ntitle: Strategic Obj 1\n---\nContent"
        )
        (so_dir / "obj2.md").write_text(
            "---\ntitle: Strategic Obj 2\n---\nContent"
        )

        # Write items to policies
        pol_dir = data_dir / "policies"
        (pol_dir / "policy1.md").write_text(
            "---\ntitle: Policy 1\n---\nContent"
        )

        resp = client.get("/api/seed/status", headers=auth_headers)
        layers = resp.json()["layers"]

        so = _find_layer(layers, "strategic-objectives")
        assert so["seeded"] is True
        assert so["count"] == 2

        pol = _find_layer(layers, "policies")
        assert pol["seeded"] is True
        assert pol["count"] == 1

        # tactical-objectives still empty
        to = _find_layer(layers, "tactical-objectives")
        assert to["seeded"] is False
        assert to["count"] == 0


# ---------------------------------------------------------------------------
# Seed trigger tests
# ---------------------------------------------------------------------------


class TestTriggerSeed:
    """Tests for POST /api/seed/."""

    def test_requires_auth(self, client: TestClient) -> None:
        resp = client.post("/api/seed/")
        assert resp.status_code == 401

    def test_accepts_request_without_body(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        data_dir: Path,
    ) -> None:
        """Endpoint accepts POST without request body (backward compatible)."""
        mock_session = MagicMock()
        mock_result = AgentResult(
            is_error=False,
            result_text="Created SA files.",
            full_output="Created SA files.",
            total_cost_usd=0.01,
            num_turns=1,
        )
        mock_session.run = AsyncMock(return_value=mock_result)

        with patch(
            "policy_factory.agent.session.AgentSession",
            return_value=mock_session,
        ), patch(
            "policy_factory.server.routers.seed.trigger_cascade",
            new_callable=AsyncMock,
            return_value=("cascade-123", True),
        ):
            resp = client.post("/api/seed/", headers=auth_headers)
        # 200 success or any non-422/401 error means the body parsing succeeded
        assert resp.status_code not in (422, 401), "Endpoint should accept empty body"

    def test_accepts_request_with_context(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        data_dir: Path,
    ) -> None:
        """Endpoint accepts POST with optional context field."""
        mock_session = MagicMock()
        mock_result = AgentResult(
            is_error=False,
            result_text="Created SA files.",
            full_output="Created SA files.",
            total_cost_usd=0.01,
            num_turns=1,
        )
        mock_session.run = AsyncMock(return_value=mock_result)

        with patch(
            "policy_factory.agent.session.AgentSession",
            return_value=mock_session,
        ), patch(
            "policy_factory.server.routers.seed.trigger_cascade",
            new_callable=AsyncMock,
            return_value=("cascade-123", True),
        ):
            resp = client.post(
                "/api/seed/",
                headers=auth_headers,
                json={"context": "Finland's current situation involves..."},
            )
        # Just verify the request body is accepted
        assert resp.status_code not in (422, 401), "Endpoint should accept context field"

    def test_clears_existing_items_before_seeding(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        data_dir: Path,
    ) -> None:
        """Endpoint clears existing SA items before running agent.

        Note: The actual clearing happens before the agent runs, so we verify
        the endpoint no longer returns 409 when SA has items (the old behavior).
        """
        # Add an item to SA to simulate existing content
        sa_dir = data_dir / "situational-awareness"
        (sa_dir / "geopolitics.md").write_text(
            "---\ntitle: Geopolitics\nstatus: current\n---\nContent"
        )

        mock_session = MagicMock()
        mock_result = AgentResult(
            is_error=False,
            result_text="Created SA files.",
            full_output="Created SA files.",
            total_cost_usd=0.01,
            num_turns=1,
        )
        mock_session.run = AsyncMock(return_value=mock_result)

        with patch(
            "policy_factory.agent.session.AgentSession",
            return_value=mock_session,
        ), patch(
            "policy_factory.server.routers.seed.trigger_cascade",
            new_callable=AsyncMock,
            return_value=("cascade-123", True),
        ):
            resp = client.post("/api/seed/", headers=auth_headers)
        # The endpoint should NOT return 409 anymore
        assert resp.status_code != 409, "Endpoint should allow re-seeding"
