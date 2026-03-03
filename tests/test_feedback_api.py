"""Tests for the feedback memo REST API router."""

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
    auth_mod.JWT_SECRET_KEY = "test-secret-key-for-feedback-api-tests"
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
# List memos tests
# ---------------------------------------------------------------------------


class TestListLayerMemos:
    """Tests for GET /api/feedback/{layer_slug}."""

    def test_requires_auth(self, client: TestClient) -> None:
        resp = client.get("/api/feedback/values")
        assert resp.status_code == 401

    def test_returns_memos_for_layer(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        store: PolicyStore,
    ) -> None:
        store.create_feedback_memo("policies", "values", None, "Feedback 1")
        store.create_feedback_memo("strategic-objectives", "values", None, "Feedback 2")

        resp = client.get("/api/feedback/values", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    def test_filters_by_status(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        store: PolicyStore,
    ) -> None:
        store.create_feedback_memo("policies", "values", None, "Pending")
        id2 = store.create_feedback_memo("policies", "values", None, "Accepted")
        store.update_memo_status(id2, "accepted")

        resp = client.get(
            "/api/feedback/values?memo_status=pending", headers=auth_headers
        )
        data = resp.json()
        assert len(data) == 1
        assert data[0]["status"] == "pending"

    def test_returns_404_for_invalid_layer(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        resp = client.get("/api/feedback/invalid-layer", headers=auth_headers)
        assert resp.status_code == 404

    def test_returns_empty_list_for_no_memos(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        resp = client.get("/api/feedback/values", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_pagination(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        store: PolicyStore,
    ) -> None:
        for i in range(5):
            store.create_feedback_memo("policies", "values", None, f"Memo {i}")

        resp = client.get(
            "/api/feedback/values?limit=2&offset=0", headers=auth_headers
        )
        data = resp.json()
        assert len(data) == 2


# ---------------------------------------------------------------------------
# Update memo status tests
# ---------------------------------------------------------------------------


class TestUpdateMemoStatus:
    """Tests for PUT /api/feedback/{memo_id}."""

    def test_requires_auth(self, client: TestClient) -> None:
        resp = client.put("/api/feedback/some-id", json={"status": "accepted"})
        assert resp.status_code == 401

    def test_accepts_memo(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        store: PolicyStore,
    ) -> None:
        memo_id = store.create_feedback_memo("policies", "values", None, "Test")

        resp = client.put(
            f"/api/feedback/{memo_id}",
            json={"status": "accepted"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "accepted"
        assert data["resolved_at"] is not None

    def test_dismisses_memo(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        store: PolicyStore,
    ) -> None:
        memo_id = store.create_feedback_memo("policies", "values", None, "Test")

        resp = client.put(
            f"/api/feedback/{memo_id}",
            json={"status": "dismissed"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "dismissed"

    def test_returns_404_for_nonexistent_memo(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        resp = client.put(
            "/api/feedback/nonexistent",
            json={"status": "accepted"},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_returns_400_for_invalid_status(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        store: PolicyStore,
    ) -> None:
        memo_id = store.create_feedback_memo("policies", "values", None, "Test")

        resp = client.put(
            f"/api/feedback/{memo_id}",
            json={"status": "invalid"},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_returns_complete_memo_data(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        store: PolicyStore,
    ) -> None:
        memo_id = store.create_feedback_memo(
            "policies",
            "values",
            "cascade-123",
            "Test content",
            ["national-security.md"],
        )

        resp = client.put(
            f"/api/feedback/{memo_id}",
            json={"status": "accepted"},
            headers=auth_headers,
        )
        data = resp.json()
        assert data["id"] == memo_id
        assert data["source_layer"] == "policies"
        assert data["target_layer"] == "values"
        assert data["cascade_id"] == "cascade-123"
        assert data["content"] == "Test content"
        assert data["referenced_items"] == ["national-security.md"]
