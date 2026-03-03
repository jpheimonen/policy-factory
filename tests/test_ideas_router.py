"""Tests for the ideas router REST endpoints."""

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


@pytest.fixture(autouse=True)
def _configure_auth():
    """Set JWT_SECRET_KEY for all tests."""
    original_key = auth_mod.JWT_SECRET_KEY
    original_expiry = auth_mod.JWT_EXPIRY_HOURS
    auth_mod.JWT_SECRET_KEY = "test-secret-key-for-ideas-api-tests"
    auth_mod.JWT_EXPIRY_HOURS = 24
    yield
    auth_mod.JWT_SECRET_KEY = original_key
    auth_mod.JWT_EXPIRY_HOURS = original_expiry


@pytest.fixture
def store(tmp_path: Path) -> PolicyStore:
    """Fresh PolicyStore."""
    return PolicyStore(tmp_path / "test.db")


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """Create data directory with layer subdirectories."""
    d = tmp_path / "data"
    for slug in LAYER_SLUGS:
        (d / slug).mkdir(parents=True, exist_ok=True)
        (d / slug / "README.md").write_text(f"# {slug}\n\nSummary.")
    return d


@pytest.fixture
def emitter() -> EventEmitter:
    """Fresh event emitter."""
    return EventEmitter()


@pytest.fixture
def client(
    store: PolicyStore, data_dir: Path, emitter: EventEmitter
) -> Generator[TestClient, None, None]:
    """Test client with authenticated user."""
    app = create_app(
        store=store,
        data_dir=data_dir,
        event_emitter=emitter,
    )
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_headers(store: PolicyStore) -> dict[str, str]:
    """Create a user and return auth headers."""
    hashed = hash_password("testpassword")
    user_id = store.create_user("test@example.com", hashed, "admin")
    token = create_access_token(user_id, "test@example.com", "admin")
    return {"Authorization": f"Bearer {token}"}


class TestSubmitIdea:
    """Tests for POST /api/ideas/."""

    def test_creates_human_idea(
        self, client: TestClient, auth_headers: dict, store: PolicyStore
    ) -> None:
        resp = client.post(
            "/api/ideas/",
            json={"text": "Finland should invest in quantum computing"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "id" in data
        assert data["status"] == "pending"

        # Verify idea was created in the store
        idea = store.get_idea(data["id"])
        assert idea is not None
        assert idea.source == "human"
        assert idea.submitted_by == "test@example.com"

    def test_creates_with_target_objective(
        self, client: TestClient, auth_headers: dict, store: PolicyStore
    ) -> None:
        resp = client.post(
            "/api/ideas/",
            json={
                "text": "Quantum advantage program",
                "target_objective": "strategic-objectives/tech-leadership.md",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        idea = store.get_idea(data["id"])
        assert idea is not None
        assert idea.target_objective == "strategic-objectives/tech-leadership.md"

    def test_requires_auth(self, client: TestClient) -> None:
        resp = client.post(
            "/api/ideas/",
            json={"text": "Test idea"},
        )
        assert resp.status_code == 401


class TestListIdeas:
    """Tests for GET /api/ideas/."""

    def test_returns_ideas(
        self, client: TestClient, auth_headers: dict, store: PolicyStore
    ) -> None:
        store.create_idea(text="Idea 1", source="human", submitted_by="u@e.com")
        store.create_idea(text="Idea 2", source="AI", submitted_by="system")

        resp = client.get("/api/ideas/", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    def test_filters_by_status(
        self, client: TestClient, auth_headers: dict, store: PolicyStore
    ) -> None:
        store.create_idea(text="Pending", source="human", submitted_by="u@e.com")
        eval_id = store.create_idea(text="Evaluating", source="human", submitted_by="u@e.com")
        store.update_idea_status(eval_id, "evaluating")

        resp = client.get("/api/ideas/?idea_status=pending", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["status"] == "pending"

    def test_excludes_archived_by_default(
        self, client: TestClient, auth_headers: dict, store: PolicyStore
    ) -> None:
        store.create_idea(text="Active", source="human", submitted_by="u@e.com")
        arch_id = store.create_idea(text="Archived", source="human", submitted_by="u@e.com")
        store.archive_idea(arch_id)

        resp = client.get("/api/ideas/", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["text"].startswith("Active")

    def test_pagination(
        self, client: TestClient, auth_headers: dict, store: PolicyStore
    ) -> None:
        for i in range(5):
            store.create_idea(text=f"Idea {i}", source="human", submitted_by="u@e.com")

        resp = client.get("/api/ideas/?limit=2&offset=0", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 2

        resp2 = client.get("/api/ideas/?limit=2&offset=4", headers=auth_headers)
        assert resp2.status_code == 200
        assert len(resp2.json()) == 1

    def test_requires_auth(self, client: TestClient) -> None:
        resp = client.get("/api/ideas/")
        assert resp.status_code == 401


class TestGetIdeaDetail:
    """Tests for GET /api/ideas/:idea_id."""

    def test_returns_full_detail(
        self, client: TestClient, auth_headers: dict, store: PolicyStore
    ) -> None:
        idea_id = store.create_idea(
            text="Detailed idea",
            source="human",
            submitted_by="u@e.com",
        )

        resp = client.get(f"/api/ideas/{idea_id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == idea_id
        assert data["text"] == "Detailed idea"
        assert data["source"] == "human"
        assert data["scores"] is None
        assert data["critic_assessments"] == []
        assert data["synthesis"] is None

    def test_returns_scores_when_evaluated(
        self, client: TestClient, auth_headers: dict, store: PolicyStore
    ) -> None:
        idea_id = store.create_idea(
            text="Scored idea",
            source="human",
            submitted_by="u@e.com",
        )
        store.store_scores(
            idea_id, 8.0, 7.0, 6.0, 5.0, 4.0, 3.0
        )

        resp = client.get(f"/api/ideas/{idea_id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["scores"] is not None
        assert data["scores"]["strategic_fit"] == 8.0
        assert data["scores"]["overall_score"] is not None

    def test_returns_critic_assessments(
        self, client: TestClient, auth_headers: dict, store: PolicyStore
    ) -> None:
        idea_id = store.create_idea(
            text="Critiqued idea",
            source="human",
            submitted_by="u@e.com",
        )
        store.store_critic_result(
            cascade_id=None,
            layer_slug=None,
            idea_id=idea_id,
            archetype="realist",
            assessment_text="Good analysis from realist perspective.",
            structured_assessment=None,
            agent_run_id=None,
        )

        resp = client.get(f"/api/ideas/{idea_id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["critic_assessments"]) == 1
        assert data["critic_assessments"][0]["archetype"] == "realist"

    def test_returns_404_for_unknown(
        self, client: TestClient, auth_headers: dict
    ) -> None:
        resp = client.get("/api/ideas/nonexistent", headers=auth_headers)
        assert resp.status_code == 404

    def test_requires_auth(self, client: TestClient) -> None:
        resp = client.get("/api/ideas/some-id")
        assert resp.status_code == 401


class TestArchiveIdea:
    """Tests for PUT /api/ideas/:idea_id/archive."""

    def test_archives_idea(
        self, client: TestClient, auth_headers: dict, store: PolicyStore
    ) -> None:
        idea_id = store.create_idea(
            text="To archive",
            source="human",
            submitted_by="u@e.com",
        )

        resp = client.put(f"/api/ideas/{idea_id}/archive", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "archived"

        idea = store.get_idea(idea_id)
        assert idea is not None
        assert idea.status == "archived"

    def test_returns_404_for_unknown(
        self, client: TestClient, auth_headers: dict
    ) -> None:
        resp = client.put("/api/ideas/nonexistent/archive", headers=auth_headers)
        assert resp.status_code == 404


class TestRetriggerEvaluation:
    """Tests for POST /api/ideas/:idea_id/evaluate."""

    def test_retrigger_pending_idea(
        self, client: TestClient, auth_headers: dict, store: PolicyStore
    ) -> None:
        idea_id = store.create_idea(
            text="Re-evaluate me",
            source="human",
            submitted_by="u@e.com",
        )

        resp = client.post(f"/api/ideas/{idea_id}/evaluate", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "evaluation_started"

    def test_retrigger_evaluated_idea(
        self, client: TestClient, auth_headers: dict, store: PolicyStore
    ) -> None:
        idea_id = store.create_idea(
            text="Re-evaluate after eval",
            source="human",
            submitted_by="u@e.com",
        )
        store.update_idea_status(idea_id, "evaluating")
        store.update_idea_status(idea_id, "evaluated")

        resp = client.post(f"/api/ideas/{idea_id}/evaluate", headers=auth_headers)
        assert resp.status_code == 200

        # Should have been reset to pending
        idea = store.get_idea(idea_id)
        assert idea is not None
        # Note: background task may have started, but the status was
        # reset to pending before launching evaluation
        assert idea.status in ("pending", "evaluating")

    def test_returns_409_when_evaluating(
        self, client: TestClient, auth_headers: dict, store: PolicyStore
    ) -> None:
        idea_id = store.create_idea(
            text="Currently evaluating",
            source="human",
            submitted_by="u@e.com",
        )
        store.update_idea_status(idea_id, "evaluating")

        resp = client.post(f"/api/ideas/{idea_id}/evaluate", headers=auth_headers)
        assert resp.status_code == 409

    def test_returns_404_for_unknown(
        self, client: TestClient, auth_headers: dict
    ) -> None:
        resp = client.post("/api/ideas/nonexistent/evaluate", headers=auth_headers)
        assert resp.status_code == 404


class TestGenerateIdeas:
    """Tests for POST /api/ideas/generate."""

    def test_returns_immediately(
        self, client: TestClient, auth_headers: dict
    ) -> None:
        resp = client.post("/api/ideas/generate", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "message" in data

    def test_accepts_scoping(
        self, client: TestClient, auth_headers: dict
    ) -> None:
        resp = client.post(
            "/api/ideas/generate",
            json={"target_objective": "strategic-objectives/ai.md"},
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_requires_auth(self, client: TestClient) -> None:
        resp = client.post("/api/ideas/generate")
        assert resp.status_code == 401
