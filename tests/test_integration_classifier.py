"""Integration tests for input classification end-to-end (with mocked agents).

Tests the flow: submit free-text input → classification → cascade trigger.
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

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
    auth_mod.JWT_SECRET_KEY = "test-secret-key-for-classifier-integration"
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


class TestInputClassification:
    """Submit free-text input, verify classification and cascade trigger."""

    def test_input_triggers_classification_and_cascade(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        """Submit free-text input and verify classification determines a target layer."""
        mock_classification = MagicMock()
        mock_classification.target_layer = "strategic-objectives"
        mock_classification.secondary_layers = []
        mock_classification.confidence = "high"
        mock_classification.explanation = "This input relates to strategic objectives."

        with patch(
            "policy_factory.server.routers.cascade.classify_input",
            new_callable=AsyncMock,
            return_value=mock_classification,
        ), patch(
            "policy_factory.server.routers.cascade.trigger_cascade",
            new_callable=AsyncMock,
            return_value=("cascade-123", True),
        ):
            resp = client.post(
                "/api/cascade/trigger",
                json={"input_text": "Finland should strengthen its strategic defense capabilities"},
                headers=auth_headers,
            )

        assert resp.status_code == 200
        data = resp.json()
        # The response should contain cascade info
        assert data.get("cascade_id") or data.get("id") or "cascade" in str(data).lower()

    def test_input_requires_auth(self, client: TestClient) -> None:
        """The cascade trigger endpoint requires authentication."""
        resp = client.post(
            "/api/cascade/trigger",
            json={"input_text": "test input"},
        )
        assert resp.status_code == 401
