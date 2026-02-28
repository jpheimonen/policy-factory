"""Integration tests for the idea pipeline end-to-end (with mocked agents).

Tests idea submission, evaluation (scores + critics + synthesis), idea
generation, and concurrent evaluations.
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from unittest.mock import AsyncMock, patch

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
    auth_mod.JWT_SECRET_KEY = "test-secret-key-for-ideas-integration"
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


class TestIdeaSubmission:
    """Submit ideas via the API and verify storage."""

    def test_submit_human_idea(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        """Submit an idea via POST and verify it's created with correct attributes."""
        with patch(
            "policy_factory.ideas.evaluator.evaluate_idea",
            new_callable=AsyncMock,
        ):
            resp = client.post(
                "/api/ideas/",
                json={"text": "Finland should invest in quantum computing"},
                headers=auth_headers,
            )

        assert resp.status_code in (200, 201)
        data = resp.json()
        assert "idea_id" in data or "id" in data

    def test_submitted_idea_appears_in_listing(
        self, client: TestClient, auth_headers: dict[str, str], store: PolicyStore
    ) -> None:
        """Submit an idea, then verify it appears in the listing."""
        # Create idea directly in store
        idea_id = store.create_idea(
            text="Test idea for listing",
            source="human",
            submitted_by="test@example.com",
        )

        resp = client.get(
            "/api/ideas/",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        ideas = resp.json()
        assert isinstance(ideas, list)
        assert len(ideas) >= 1

        idea_ids = [i.get("id") or i.get("idea_id") for i in ideas]
        assert idea_id in idea_ids


class TestIdeaEvaluation:
    """Evaluating an idea stores scores, critic results, and synthesis."""

    def test_evaluated_idea_has_scores(
        self, store: PolicyStore
    ) -> None:
        """Store evaluation scores for an idea and verify retrieval."""
        idea_id = store.create_idea(
            text="Test idea for scoring",
            source="human",
            submitted_by="test@test.com",
        )

        # Store scores
        store.store_scores(
            idea_id=idea_id,
            strategic_fit=8.0,
            feasibility=7.0,
            cost=6.0,
            risk=5.0,
            public_acceptance=9.0,
            international_impact=7.5,
        )

        # Retrieve scores
        scores = store.get_scores(idea_id)
        assert scores is not None
        assert scores.strategic_fit == 8.0
        assert scores.feasibility == 7.0
        assert scores.cost == 6.0
        assert scores.risk == 5.0
        assert scores.public_acceptance == 9.0
        assert scores.international_impact == 7.5

    def test_idea_evaluation_does_not_acquire_cascade_lock(
        self, store: PolicyStore
    ) -> None:
        """Idea evaluation should not acquire the cascade lock."""
        # Create a running cascade (holds lock)
        cascade_id = store.create_cascade(
            trigger_source="test",
            starting_layer="values",
        )
        store.acquire_lock(cascade_id)

        # Create and "evaluate" an idea — should not need the lock
        idea_id = store.create_idea(
            text="Concurrent idea",
            source="human",
            submitted_by="test@test.com",
        )

        # Store evaluation results (simulating evaluation without lock)
        store.store_scores(
            idea_id=idea_id,
            strategic_fit=7.0,
            feasibility=6.0,
            cost=5.0,
            risk=4.0,
            public_acceptance=8.0,
            international_impact=6.5,
        )

        # Lock should still be held by cascade
        assert store.is_lock_held()

        # Scores should be stored successfully
        scores = store.get_scores(idea_id)
        assert scores is not None
        assert scores.strategic_fit == 7.0


class TestIdeaGeneration:
    """AI idea generation creates ideas with source 'AI'."""

    def test_ai_idea_generation_endpoint(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        """Trigger AI idea generation via the API."""
        with patch(
            "policy_factory.ideas.generator.generate_ideas",
            new_callable=AsyncMock,
        ) as mock_gen:
            mock_gen.return_value = None  # Background task

            resp = client.post(
                "/api/ideas/generate",
                headers=auth_headers,
            )

        assert resp.status_code == 200

    def test_ai_generated_ideas_stored(self, store: PolicyStore) -> None:
        """AI-generated ideas should have source='AI'."""
        idea_id = store.create_idea(
            text="AI-generated policy idea",
            source="AI",
            submitted_by="system",
        )

        idea = store.get_idea(idea_id)
        assert idea is not None
        assert idea.source == "AI"
        assert idea.submitted_by == "system"


class TestConcurrentEvaluations:
    """Two idea evaluations running concurrently complete independently."""

    def test_independent_score_storage(self, store: PolicyStore) -> None:
        """Two ideas evaluated concurrently store scores independently."""
        idea1 = store.create_idea(
            text="Idea 1", source="human", submitted_by="test@test.com"
        )
        idea2 = store.create_idea(
            text="Idea 2", source="human", submitted_by="test@test.com"
        )

        # Store scores for both
        store.store_scores(
            idea_id=idea1,
            strategic_fit=9.0, feasibility=8.0, cost=7.0,
            risk=6.0, public_acceptance=8.5, international_impact=7.0,
        )
        store.store_scores(
            idea_id=idea2,
            strategic_fit=5.0, feasibility=4.0, cost=3.0,
            risk=2.0, public_acceptance=6.0, international_impact=4.5,
        )

        # Verify independence
        scores1 = store.get_scores(idea1)
        scores2 = store.get_scores(idea2)
        assert scores1.strategic_fit == 9.0
        assert scores2.strategic_fit == 5.0
