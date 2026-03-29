"""Integration tests for seeding flows.

Tests the seeding endpoints with mocked agent execution to verify:
- Values seeding: authentication, file creation, clear-before-write, git commit
- SA seeding: no-409, clear-before-write, context parameter, cascade trigger
- Seed status: correct reporting of layer counts
- Data initialization: directory creation, no pre-seeded values, idempotency
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import policy_factory.auth as auth_mod
from policy_factory.agent.session import AgentResult
from policy_factory.auth import create_access_token, hash_password
from policy_factory.data.git import _run_git, is_git_repo
from policy_factory.data.init import initialize_data_directory
from policy_factory.data.layers import LAYER_SLUGS, LAYERS, list_items
from policy_factory.events import EventEmitter
from policy_factory.server.app import create_app
from policy_factory.server.ws import ConnectionManager
from policy_factory.store import PolicyStore

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _configure_auth():
    """Set JWT_SECRET_KEY for all tests."""
    original_key = auth_mod.JWT_SECRET_KEY
    original_expiry = auth_mod.JWT_EXPIRY_HOURS
    auth_mod.JWT_SECRET_KEY = "test-secret-key-for-seeding-integration"
    auth_mod.JWT_EXPIRY_HOURS = 24
    yield
    auth_mod.JWT_SECRET_KEY = original_key
    auth_mod.JWT_EXPIRY_HOURS = original_expiry


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """Create a temporary data directory with git initialized."""
    d = tmp_path / "data"
    initialize_data_directory(d)
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
    app = create_app(
        store=store,
        event_emitter=emitter,
        data_dir=data_dir,
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


# ---------------------------------------------------------------------------
# Mock helpers for agent execution
# ---------------------------------------------------------------------------


def _make_mock_values_agent_result() -> AgentResult:
    """Create a mock AgentResult for values seeding.

    Returns output with properly formatted YAML frontmatter values.
    """
    output = """
---
title: "National Security"
tensions:
  - "Economic Prosperity"
  - "International Cooperation"
---

Finland prioritizes national security as a foundational value, particularly
in light of its geopolitical position. This includes territorial integrity,
defense capabilities, and resilience against hybrid threats.

---
title: "Economic Prosperity"
tensions:
  - "Environmental Sustainability"
  - "Social Equity"
---

Finland values sustainable economic growth that provides opportunities for
all citizens. This includes innovation, competitiveness, and workforce
development.

---
title: "Democratic Values"
tensions:
  - "National Security"
  - "Efficiency"
---

Finland upholds democratic principles including rule of law, transparency,
and citizen participation in governance.
"""
    return AgentResult(
        is_error=False,
        result_text=output,
        full_output=output,
        total_cost_usd=0.01,
        num_turns=1,
    )


def _make_mock_sa_agent_result(data_dir: Path) -> AgentResult:
    """Create a mock AgentResult for SA seeding that writes files.

    The SA agent uses tools to write files, so this mock simulates
    that behavior by writing files to the data directory.
    """
    # Simulate what the agent would do - write SA files
    sa_dir = data_dir / "situational-awareness"
    sa_dir.mkdir(parents=True, exist_ok=True)

    # Write some SA files
    files_to_create = [
        ("geopolitical-landscape.md", "Geopolitical Landscape", "Finland's position..."),
        ("technology-policy.md", "Technology Policy", "Current tech policy..."),
        ("economic-situation.md", "Economic Situation", "Economic overview..."),
    ]

    for filename, title, content in files_to_create:
        file_path = sa_dir / filename
        file_content = f"---\ntitle: {title}\nstatus: current\n---\n\n{content}"
        file_path.write_text(file_content)

    output = "Created 3 situational awareness files."
    return AgentResult(
        is_error=False,
        result_text=output,
        full_output=output,
        total_cost_usd=0.02,
        num_turns=2,
    )


def _make_mock_failing_agent_result() -> AgentResult:
    """Create a mock AgentResult for a failing agent."""
    return AgentResult(
        is_error=True,
        result_text="API error: rate limit exceeded",
        full_output="",
        total_cost_usd=0.0,
        num_turns=1,
    )


@contextmanager
def mock_agent_session(mock_result: AgentResult):
    """Context manager that mocks AgentSession for seeding tests.

    Args:
        mock_result: The AgentResult to return from session.run()

    Note:
        AgentSession is lazily imported inside the endpoint function with `from`,
        so we must patch at the source module (policy_factory.agent.session.AgentSession).
    """
    mock_session = MagicMock()
    mock_session.run = AsyncMock(return_value=mock_result)

    with patch(
        "policy_factory.agent.session.AgentSession",
        return_value=mock_session,
    ):
        yield mock_session


@contextmanager
def mock_agent_session_with_side_effect(side_effect_fn):
    """Context manager that mocks AgentSession with a custom side effect.

    Args:
        side_effect_fn: Function called with prompt that returns AgentResult

    Note:
        AgentSession is lazily imported inside the endpoint function with `from`,
        so we must patch at the source module (policy_factory.agent.session.AgentSession).
    """
    mock_session = MagicMock()
    mock_session.run = AsyncMock(side_effect=side_effect_fn)

    with patch(
        "policy_factory.agent.session.AgentSession",
        return_value=mock_session,
    ):
        yield mock_session


# ---------------------------------------------------------------------------
# Values Seeding Flow Tests
# ---------------------------------------------------------------------------


class TestValuesSeedingFlow:
    """Integration tests for POST /api/seed/values endpoint."""

    def test_values_seeding_requires_auth(self, client: TestClient) -> None:
        """Values seeding endpoint requires authentication."""
        resp = client.post("/api/seed/values")
        assert resp.status_code == 401

    def test_values_seeding_creates_markdown_files(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        data_dir: Path,
    ) -> None:
        """Values seeding creates markdown files in data/values directory."""
        mock_result = _make_mock_values_agent_result()

        with mock_agent_session(mock_result):
            resp = client.post("/api/seed/values", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["values_created"] == 3

        # Verify files were created
        values_items = list_items(data_dir, "values")
        assert len(values_items) == 3

        # Check that files have expected content
        filenames = {item.filename for item in values_items}
        assert "national-security.md" in filenames
        assert "economic-prosperity.md" in filenames
        assert "democratic-values.md" in filenames

    def test_values_seeding_clears_existing_before_write(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        data_dir: Path,
    ) -> None:
        """Values seeding clears existing values before writing new ones."""
        # Create an existing value file
        values_dir = data_dir / "values"
        existing_file = values_dir / "old-value.md"
        existing_file.write_text("---\ntitle: Old Value\n---\n\nOld content.")

        # Verify it exists
        items_before = list_items(data_dir, "values")
        assert len(items_before) == 1
        assert items_before[0].filename == "old-value.md"

        mock_result = _make_mock_values_agent_result()

        with mock_agent_session(mock_result):
            resp = client.post("/api/seed/values", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

        # Verify old file is gone and new files exist
        items_after = list_items(data_dir, "values")
        filenames = {item.filename for item in items_after}
        assert "old-value.md" not in filenames
        assert len(items_after) == 3

    def test_values_seeding_returns_count(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Values seeding returns count of values created."""
        mock_result = _make_mock_values_agent_result()

        with mock_agent_session(mock_result):
            resp = client.post("/api/seed/values", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert "values_created" in data
        assert data["values_created"] == 3

    def test_values_seeding_commits_to_git(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        data_dir: Path,
    ) -> None:
        """Values seeding commits changes to git."""
        # Get commit count before
        log_before = _run_git(["rev-list", "--count", "HEAD"], cwd=data_dir)
        count_before = int(log_before.stdout.strip())

        mock_result = _make_mock_values_agent_result()

        with mock_agent_session(mock_result):
            resp = client.post("/api/seed/values", headers=auth_headers)

        assert resp.status_code == 200

        # Get commit count after
        log_after = _run_git(["rev-list", "--count", "HEAD"], cwd=data_dir)
        count_after = int(log_after.stdout.strip())

        # Should have one more commit
        assert count_after == count_before + 1

        # Verify commit message mentions values
        log_msg = _run_git(["log", "-1", "--format=%s"], cwd=data_dir)
        assert "values" in log_msg.stdout.lower()

    def test_values_seeding_error_returns_appropriate_response(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Values seeding with agent error returns appropriate error response."""
        mock_result = _make_mock_failing_agent_result()

        with mock_agent_session(mock_result):
            resp = client.post("/api/seed/values", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert "failed" in data["message"].lower() or "error" in data["message"].lower()


# ---------------------------------------------------------------------------
# SA Seeding Flow Tests
# ---------------------------------------------------------------------------


class TestSASeedingFlow:
    """Integration tests for POST /api/seed/ endpoint."""

    def test_sa_seeding_requires_auth(self, client: TestClient) -> None:
        """SA seeding endpoint requires authentication."""
        resp = client.post("/api/seed/")
        assert resp.status_code == 401

    def test_sa_seeding_no_longer_returns_409(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        data_dir: Path,
    ) -> None:
        """POST /api/seed/ no longer returns 409 when SA layer has items."""
        # Add an existing SA item
        sa_dir = data_dir / "situational-awareness"
        (sa_dir / "existing-item.md").write_text(
            "---\ntitle: Existing\nstatus: current\n---\n\nContent"
        )

        # Verify it exists
        items_before = list_items(data_dir, "situational-awareness")
        assert len(items_before) == 1

        def mock_run(prompt: str) -> AgentResult:
            return _make_mock_sa_agent_result(data_dir)

        with mock_agent_session_with_side_effect(mock_run):
            # Also mock cascade trigger since SA seeding triggers it
            with patch(
                "policy_factory.server.routers.seed.trigger_cascade",
                new_callable=AsyncMock,
            ) as mock_cascade:
                mock_cascade.return_value = ("cascade-123", True)

                resp = client.post("/api/seed/", headers=auth_headers)

        # Should NOT be 409 - endpoint now allows re-seeding
        assert resp.status_code != 409
        assert resp.status_code == 200

    def test_sa_seeding_clears_existing_items(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        data_dir: Path,
    ) -> None:
        """SA seeding clears existing SA items before writing new ones."""
        # Add an existing SA item
        sa_dir = data_dir / "situational-awareness"
        (sa_dir / "old-sa-item.md").write_text(
            "---\ntitle: Old SA Item\nstatus: current\n---\n\nOld content"
        )

        # Verify it exists
        items_before = list_items(data_dir, "situational-awareness")
        assert len(items_before) == 1
        assert items_before[0].filename == "old-sa-item.md"

        def mock_run(prompt: str) -> AgentResult:
            return _make_mock_sa_agent_result(data_dir)

        with mock_agent_session_with_side_effect(mock_run):
            with patch(
                "policy_factory.server.routers.seed.trigger_cascade",
                new_callable=AsyncMock,
            ) as mock_cascade:
                mock_cascade.return_value = ("cascade-123", True)

                resp = client.post("/api/seed/", headers=auth_headers)

        assert resp.status_code == 200

        # The old item should be cleared (the mock creates new items)
        items_after = list_items(data_dir, "situational-awareness")
        filenames = {item.filename for item in items_after}
        assert "old-sa-item.md" not in filenames

    def test_sa_seeding_accepts_context_parameter(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        data_dir: Path,
    ) -> None:
        """SA seeding accepts optional context in request body."""
        context_text = "Finland is currently facing increased cyber threats."

        def mock_run(prompt: str) -> AgentResult:
            return _make_mock_sa_agent_result(data_dir)

        with mock_agent_session_with_side_effect(mock_run):
            with patch(
                "policy_factory.server.routers.seed.trigger_cascade",
                new_callable=AsyncMock,
            ) as mock_cascade:
                mock_cascade.return_value = ("cascade-123", True)

                resp = client.post(
                    "/api/seed/",
                    headers=auth_headers,
                    json={"context": context_text},
                )

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    def test_sa_seeding_context_incorporated_into_prompt(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        data_dir: Path,
    ) -> None:
        """Context is incorporated into the agent prompt when provided."""
        context_text = "Finland recently signed a new defense agreement."
        captured_prompts: list[str] = []

        def mock_run(prompt: str) -> AgentResult:
            captured_prompts.append(prompt)
            return _make_mock_sa_agent_result(data_dir)

        with mock_agent_session_with_side_effect(mock_run):
            with patch(
                "policy_factory.server.routers.seed.trigger_cascade",
                new_callable=AsyncMock,
            ) as mock_cascade:
                mock_cascade.return_value = ("cascade-123", True)

                resp = client.post(
                    "/api/seed/",
                    headers=auth_headers,
                    json={"context": context_text},
                )

        assert resp.status_code == 200

        # Verify the context was included in the prompt
        assert len(captured_prompts) == 1
        assert context_text in captured_prompts[0]
        assert "Human-Provided Context" in captured_prompts[0]

    def test_sa_seeding_works_without_context(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        data_dir: Path,
    ) -> None:
        """SA seeding works without context (backward compatible)."""

        def mock_run(prompt: str) -> AgentResult:
            return _make_mock_sa_agent_result(data_dir)

        with mock_agent_session_with_side_effect(mock_run):
            with patch(
                "policy_factory.server.routers.seed.trigger_cascade",
                new_callable=AsyncMock,
            ) as mock_cascade:
                mock_cascade.return_value = ("cascade-123", True)

                # POST without body
                resp = client.post("/api/seed/", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    def test_sa_seeding_triggers_cascade(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        data_dir: Path,
    ) -> None:
        """SA seeding triggers cascade after completion."""

        def mock_run(prompt: str) -> AgentResult:
            return _make_mock_sa_agent_result(data_dir)

        with mock_agent_session_with_side_effect(mock_run):
            with patch(
                "policy_factory.server.routers.seed.trigger_cascade",
                new_callable=AsyncMock,
            ) as mock_cascade:
                mock_cascade.return_value = ("cascade-456", True)

                resp = client.post("/api/seed/", headers=auth_headers)

        assert resp.status_code == 200

        # Verify cascade was triggered
        mock_cascade.assert_called_once()
        call_kwargs = mock_cascade.call_args
        assert call_kwargs.kwargs.get("starting_layer") == "situational-awareness"

    def test_sa_seeding_returns_cascade_id(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        data_dir: Path,
    ) -> None:
        """SA seeding returns cascade ID in response."""

        def mock_run(prompt: str) -> AgentResult:
            return _make_mock_sa_agent_result(data_dir)

        with mock_agent_session_with_side_effect(mock_run):
            with patch(
                "policy_factory.server.routers.seed.trigger_cascade",
                new_callable=AsyncMock,
            ) as mock_cascade:
                mock_cascade.return_value = ("cascade-789", True)

                resp = client.post("/api/seed/", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert "cascade_id" in data
        assert data["cascade_id"] == "cascade-789"


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
# Seed Status Tests
# ---------------------------------------------------------------------------


class TestSeedStatusEndpoint:
    """Integration tests for GET /api/seed/status endpoint."""

    def test_status_requires_auth(self, client: TestClient) -> None:
        """Seed status endpoint requires authentication."""
        resp = client.get("/api/seed/status")
        assert resp.status_code == 401

    def test_status_reflects_empty_layers(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Status correctly reflects empty layers after initialization."""
        resp = client.get("/api/seed/status", headers=auth_headers)
        assert resp.status_code == 200
        layers = resp.json()["layers"]

        # All 6 layers should be empty
        assert len(layers) == 6
        for entry in layers:
            assert entry["seeded"] is False
            assert entry["count"] == 0

    def test_status_reflects_populated_values(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        data_dir: Path,
    ) -> None:
        """Status correctly reflects populated values layer."""
        # Add some value files
        values_dir = data_dir / "values"
        (values_dir / "value1.md").write_text("---\ntitle: Value 1\n---\n\nContent")
        (values_dir / "value2.md").write_text("---\ntitle: Value 2\n---\n\nContent")

        resp = client.get("/api/seed/status", headers=auth_headers)
        assert resp.status_code == 200
        layers = resp.json()["layers"]

        values = _find_layer(layers, "values")
        assert values["seeded"] is True
        assert values["count"] == 2

        sa = _find_layer(layers, "situational-awareness")
        assert sa["seeded"] is False
        assert sa["count"] == 0

    def test_status_reflects_populated_sa(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        data_dir: Path,
    ) -> None:
        """Status correctly reflects populated SA layer."""
        # Add some SA files
        sa_dir = data_dir / "situational-awareness"
        (sa_dir / "sa1.md").write_text("---\ntitle: SA 1\n---\n\nContent")
        (sa_dir / "sa2.md").write_text("---\ntitle: SA 2\n---\n\nContent")
        (sa_dir / "sa3.md").write_text("---\ntitle: SA 3\n---\n\nContent")

        resp = client.get("/api/seed/status", headers=auth_headers)
        assert resp.status_code == 200
        layers = resp.json()["layers"]

        values = _find_layer(layers, "values")
        assert values["seeded"] is False
        assert values["count"] == 0

        sa = _find_layer(layers, "situational-awareness")
        assert sa["seeded"] is True
        assert sa["count"] == 3

    def test_status_returns_correct_counts_for_both_layers(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        data_dir: Path,
    ) -> None:
        """Status returns correct counts when both layers are populated."""
        # Add value files
        values_dir = data_dir / "values"
        (values_dir / "value1.md").write_text("---\ntitle: Value 1\n---\n\nContent")

        # Add SA files
        sa_dir = data_dir / "situational-awareness"
        (sa_dir / "sa1.md").write_text("---\ntitle: SA 1\n---\n\nContent")
        (sa_dir / "sa2.md").write_text("---\ntitle: SA 2\n---\n\nContent")

        resp = client.get("/api/seed/status", headers=auth_headers)
        assert resp.status_code == 200
        layers = resp.json()["layers"]

        values = _find_layer(layers, "values")
        assert values["seeded"] is True
        assert values["count"] == 1

        sa = _find_layer(layers, "situational-awareness")
        assert sa["seeded"] is True
        assert sa["count"] == 2

    def test_status_includes_all_six_layers(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Response contains exactly 6 layer entries with correct slugs."""
        resp = client.get("/api/seed/status", headers=auth_headers)
        assert resp.status_code == 200
        layers = resp.json()["layers"]
        assert len(layers) == 6
        expected_slugs = [layer.slug for layer in LAYERS]
        actual_slugs = [entry["slug"] for entry in layers]
        assert actual_slugs == expected_slugs


# ---------------------------------------------------------------------------
# Data Initialization Tests
# ---------------------------------------------------------------------------


class TestDataInitialization:
    """Integration tests for data directory initialization."""

    def test_initialization_creates_all_layer_directories(
        self, tmp_path: Path
    ) -> None:
        """Initialization creates all five layer directories."""
        data_root = tmp_path / "fresh-data"
        initialize_data_directory(data_root)

        for slug in LAYER_SLUGS:
            layer_dir = data_root / slug
            assert layer_dir.is_dir(), f"Missing layer directory: {slug}"

    def test_initialization_creates_git_repo(self, tmp_path: Path) -> None:
        """Initialization creates a git repository."""
        data_root = tmp_path / "fresh-data"
        initialize_data_directory(data_root)

        assert is_git_repo(data_root)

    def test_initialization_does_not_write_preseeded_values(
        self, tmp_path: Path
    ) -> None:
        """Initialization does NOT write pre-seeded values.

        Values are populated via explicit seeding through the API, not at startup.
        """
        data_root = tmp_path / "fresh-data"
        initialize_data_directory(data_root)

        # Values directory should be empty (only README.md)
        items = list_items(data_root, "values")
        assert len(items) == 0, "Values directory should be empty after initialization"

    def test_values_directory_contains_only_readme(self, tmp_path: Path) -> None:
        """Values directory contains only README.md after init."""
        data_root = tmp_path / "fresh-data"
        initialize_data_directory(data_root)

        values_dir = data_root / "values"
        files = list(values_dir.glob("*.md"))

        # Only README.md should exist
        filenames = {f.name for f in files}
        assert "README.md" in filenames
        assert len(filenames) == 1, "Values should only have README.md"

    def test_initialization_is_idempotent(self, tmp_path: Path) -> None:
        """Initialization is idempotent (safe to call multiple times)."""
        data_root = tmp_path / "fresh-data"

        # First initialization
        initialize_data_directory(data_root)

        # Get commit count after first init
        log_before = _run_git(["rev-list", "--count", "HEAD"], cwd=data_root)
        count_before = int(log_before.stdout.strip())

        # Second initialization
        initialize_data_directory(data_root)

        # Commit count should be unchanged
        log_after = _run_git(["rev-list", "--count", "HEAD"], cwd=data_root)
        count_after = int(log_after.stdout.strip())

        assert count_after == count_before, "Idempotent init should not add commits"

    def test_initialization_creates_readme_in_each_layer(
        self, tmp_path: Path
    ) -> None:
        """Initialization creates README.md placeholder in each layer."""
        data_root = tmp_path / "fresh-data"
        initialize_data_directory(data_root)

        for slug in LAYER_SLUGS:
            readme = data_root / slug / "README.md"
            assert readme.exists(), f"Missing README.md in {slug}"
            content = readme.read_text()
            assert len(content) > 0, f"README.md in {slug} is empty"


# ---------------------------------------------------------------------------
# Agent Mock Verification Tests
# ---------------------------------------------------------------------------


class TestAgentMockingAtSessionLevel:
    """Verify that all tests mock at AgentSession level, not making real API calls."""

    def test_values_seeding_uses_mocked_session(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Values seeding test uses mocked AgentSession."""
        mock_result = _make_mock_values_agent_result()
        session_run_called = False

        async def track_run(prompt: str) -> AgentResult:
            nonlocal session_run_called
            session_run_called = True
            return mock_result

        with mock_agent_session_with_side_effect(track_run):
            resp = client.post("/api/seed/values", headers=auth_headers)

        # Verify the session was used (mocked)
        assert session_run_called is True
        assert resp.status_code == 200

    def test_sa_seeding_uses_mocked_session(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        data_dir: Path,
    ) -> None:
        """SA seeding test uses mocked AgentSession."""
        session_run_called = False

        async def track_run(prompt: str) -> AgentResult:
            nonlocal session_run_called
            session_run_called = True
            return _make_mock_sa_agent_result(data_dir)

        with mock_agent_session_with_side_effect(track_run):
            with patch(
                "policy_factory.server.routers.seed.trigger_cascade",
                new_callable=AsyncMock,
            ) as mock_cascade:
                mock_cascade.return_value = ("cascade-123", True)
                resp = client.post("/api/seed/", headers=auth_headers)

        # Verify the session was used (mocked)
        assert session_run_called is True
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Upper-layer seed helpers
# ---------------------------------------------------------------------------


def _populate_layer(data_dir: Path, slug: str, count: int = 1) -> None:
    """Write minimal markdown items to a layer directory."""
    layer_dir = data_dir / slug
    layer_dir.mkdir(parents=True, exist_ok=True)
    for i in range(count):
        (layer_dir / f"item-{i + 1}.md").write_text(
            f"---\ntitle: Item {i + 1}\n---\n\nContent for {slug} item {i + 1}."
        )


def _populate_prerequisites(data_dir: Path, target_slug: str) -> None:
    """Populate all prerequisite layers for a target layer."""
    from policy_factory.cascade.orchestrator import layers_below

    for slug in layers_below(target_slug):
        _populate_layer(data_dir, slug)


def _make_mock_upper_layer_agent_result(
    data_dir: Path, layer_slug: str
) -> AgentResult:
    """Create a mock AgentResult for upper-layer seeding that writes files.

    Simulates what the agent would do — write markdown files to the
    target layer directory via FILE_TOOLS.
    """
    layer_dir = data_dir / layer_slug
    layer_dir.mkdir(parents=True, exist_ok=True)

    files = [
        ("item-alpha.md", "Item Alpha", "Alpha content."),
        ("item-beta.md", "Item Beta", "Beta content."),
    ]
    for filename, title, content in files:
        (layer_dir / filename).write_text(
            f"---\ntitle: {title}\nstatus: draft\n---\n\n{content}"
        )

    output = f"Created 2 {layer_slug} items."
    return AgentResult(
        is_error=False,
        result_text=output,
        full_output=output,
        total_cost_usd=0.02,
        num_turns=2,
    )


# ---------------------------------------------------------------------------
# Strategic Objectives Seeding Flow Tests
# ---------------------------------------------------------------------------


class TestStrategicSeedingFlow:
    """Integration tests for POST /api/seed/strategic-objectives."""

    def test_requires_auth(self, client: TestClient) -> None:
        resp = client.post("/api/seed/strategic-objectives")
        assert resp.status_code == 401

    def test_creates_items_in_correct_directory(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        data_dir: Path,
    ) -> None:
        """Agent-written files appear in strategic-objectives directory."""
        _populate_prerequisites(data_dir, "strategic-objectives")

        def mock_run(prompt: str) -> AgentResult:
            return _make_mock_upper_layer_agent_result(
                data_dir, "strategic-objectives"
            )

        with mock_agent_session_with_side_effect(mock_run):
            resp = client.post(
                "/api/seed/strategic-objectives", headers=auth_headers
            )

        assert resp.status_code == 200
        assert resp.json()["success"] is True

        items = list_items(data_dir, "strategic-objectives")
        assert len(items) == 2
        filenames = {item.filename for item in items}
        assert "item-alpha.md" in filenames
        assert "item-beta.md" in filenames

    def test_clears_existing_items_before_seeding(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        data_dir: Path,
    ) -> None:
        """Old items are removed before the agent runs."""
        _populate_prerequisites(data_dir, "strategic-objectives")
        _populate_layer(data_dir, "strategic-objectives", count=3)

        # Verify old items exist
        items_before = list_items(data_dir, "strategic-objectives")
        assert len(items_before) == 3

        def mock_run(prompt: str) -> AgentResult:
            return _make_mock_upper_layer_agent_result(
                data_dir, "strategic-objectives"
            )

        with mock_agent_session_with_side_effect(mock_run):
            resp = client.post(
                "/api/seed/strategic-objectives", headers=auth_headers
            )

        assert resp.status_code == 200

        items_after = list_items(data_dir, "strategic-objectives")
        filenames = {item.filename for item in items_after}
        # Old items gone, new ones present
        assert "item-1.md" not in filenames
        assert "item-alpha.md" in filenames

    def test_commits_to_git(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        data_dir: Path,
    ) -> None:
        """A git commit is made after successful seeding."""
        _populate_prerequisites(data_dir, "strategic-objectives")

        log_before = _run_git(["rev-list", "--count", "HEAD"], cwd=data_dir)
        count_before = int(log_before.stdout.strip())

        def mock_run(prompt: str) -> AgentResult:
            return _make_mock_upper_layer_agent_result(
                data_dir, "strategic-objectives"
            )

        with mock_agent_session_with_side_effect(mock_run):
            resp = client.post(
                "/api/seed/strategic-objectives", headers=auth_headers
            )

        assert resp.status_code == 200

        log_after = _run_git(["rev-list", "--count", "HEAD"], cwd=data_dir)
        count_after = int(log_after.stdout.strip())
        assert count_after == count_before + 1

        log_msg = _run_git(["log", "-1", "--format=%s"], cwd=data_dir)
        assert "strategic-objectives" in log_msg.stdout.lower()

    def test_records_agent_run(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        data_dir: Path,
        store: PolicyStore,
    ) -> None:
        """An agent run record is created with the correct type and layer."""
        _populate_prerequisites(data_dir, "strategic-objectives")

        def mock_run(prompt: str) -> AgentResult:
            return _make_mock_upper_layer_agent_result(
                data_dir, "strategic-objectives"
            )

        with mock_agent_session_with_side_effect(mock_run):
            resp = client.post(
                "/api/seed/strategic-objectives", headers=auth_headers
            )

        assert resp.status_code == 200

        runs = store.list_agent_runs(agent_type="strategic-seed")
        assert len(runs) == 1
        assert runs[0].target_layer == "strategic-objectives"
        assert runs[0].success is True

    def test_returns_error_on_agent_failure(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        data_dir: Path,
    ) -> None:
        """Returns failure response when the agent errors."""
        _populate_prerequisites(data_dir, "strategic-objectives")

        mock_result = _make_mock_failing_agent_result()
        with mock_agent_session(mock_result):
            resp = client.post(
                "/api/seed/strategic-objectives", headers=auth_headers
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert "failed" in data["message"].lower()

    def test_does_not_trigger_cascade(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        data_dir: Path,
    ) -> None:
        """Strategic seed does NOT trigger a cascade."""
        _populate_prerequisites(data_dir, "strategic-objectives")

        def mock_run(prompt: str) -> AgentResult:
            return _make_mock_upper_layer_agent_result(
                data_dir, "strategic-objectives"
            )

        with mock_agent_session_with_side_effect(mock_run), patch(
            "policy_factory.server.routers.seed.trigger_cascade",
            new_callable=AsyncMock,
        ) as mock_cascade:
            resp = client.post(
                "/api/seed/strategic-objectives", headers=auth_headers
            )

        assert resp.status_code == 200
        mock_cascade.assert_not_called()

    def test_prerequisite_failure_does_not_clear_items(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        data_dir: Path,
    ) -> None:
        """When prerequisites fail, existing target items are preserved."""
        _populate_layer(data_dir, "strategic-objectives", count=2)
        # Don't populate prerequisites

        resp = client.post(
            "/api/seed/strategic-objectives", headers=auth_headers
        )

        assert resp.status_code == 200
        assert resp.json()["success"] is False

        items = list_items(data_dir, "strategic-objectives")
        assert len(items) == 2


# ---------------------------------------------------------------------------
# Tactical Objectives Seeding Flow Tests
# ---------------------------------------------------------------------------


class TestTacticalSeedingFlow:
    """Integration tests for POST /api/seed/tactical-objectives."""

    def test_requires_auth(self, client: TestClient) -> None:
        resp = client.post("/api/seed/tactical-objectives")
        assert resp.status_code == 401

    def test_creates_items_in_correct_directory(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        data_dir: Path,
    ) -> None:
        """Agent-written files appear in tactical-objectives directory."""
        _populate_prerequisites(data_dir, "tactical-objectives")

        def mock_run(prompt: str) -> AgentResult:
            return _make_mock_upper_layer_agent_result(
                data_dir, "tactical-objectives"
            )

        with mock_agent_session_with_side_effect(mock_run):
            resp = client.post(
                "/api/seed/tactical-objectives", headers=auth_headers
            )

        assert resp.status_code == 200
        assert resp.json()["success"] is True

        items = list_items(data_dir, "tactical-objectives")
        assert len(items) == 2

    def test_clears_existing_items(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        data_dir: Path,
    ) -> None:
        """Old items are removed before seeding."""
        _populate_prerequisites(data_dir, "tactical-objectives")
        _populate_layer(data_dir, "tactical-objectives", count=2)

        def mock_run(prompt: str) -> AgentResult:
            return _make_mock_upper_layer_agent_result(
                data_dir, "tactical-objectives"
            )

        with mock_agent_session_with_side_effect(mock_run):
            resp = client.post(
                "/api/seed/tactical-objectives", headers=auth_headers
            )

        assert resp.status_code == 200

        items = list_items(data_dir, "tactical-objectives")
        filenames = {item.filename for item in items}
        assert "item-1.md" not in filenames
        assert "item-alpha.md" in filenames

    def test_commits_to_git(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        data_dir: Path,
    ) -> None:
        """A git commit is made after successful seeding."""
        _populate_prerequisites(data_dir, "tactical-objectives")

        log_before = _run_git(["rev-list", "--count", "HEAD"], cwd=data_dir)
        count_before = int(log_before.stdout.strip())

        def mock_run(prompt: str) -> AgentResult:
            return _make_mock_upper_layer_agent_result(
                data_dir, "tactical-objectives"
            )

        with mock_agent_session_with_side_effect(mock_run):
            resp = client.post(
                "/api/seed/tactical-objectives", headers=auth_headers
            )

        assert resp.status_code == 200

        log_after = _run_git(["rev-list", "--count", "HEAD"], cwd=data_dir)
        count_after = int(log_after.stdout.strip())
        assert count_after == count_before + 1

        log_msg = _run_git(["log", "-1", "--format=%s"], cwd=data_dir)
        assert "tactical-objectives" in log_msg.stdout.lower()

    def test_records_agent_run(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        data_dir: Path,
        store: PolicyStore,
    ) -> None:
        """An agent run record is created with the correct agent type."""
        _populate_prerequisites(data_dir, "tactical-objectives")

        def mock_run(prompt: str) -> AgentResult:
            return _make_mock_upper_layer_agent_result(
                data_dir, "tactical-objectives"
            )

        with mock_agent_session_with_side_effect(mock_run):
            resp = client.post(
                "/api/seed/tactical-objectives", headers=auth_headers
            )

        assert resp.status_code == 200

        runs = store.list_agent_runs(agent_type="tactical-seed")
        assert len(runs) == 1
        assert runs[0].target_layer == "tactical-objectives"
        assert runs[0].success is True

    def test_returns_error_on_agent_failure(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        data_dir: Path,
    ) -> None:
        """Returns failure response when the agent errors."""
        _populate_prerequisites(data_dir, "tactical-objectives")

        mock_result = _make_mock_failing_agent_result()
        with mock_agent_session(mock_result):
            resp = client.post(
                "/api/seed/tactical-objectives", headers=auth_headers
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert "failed" in data["message"].lower()

    def test_does_not_trigger_cascade(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        data_dir: Path,
    ) -> None:
        """Tactical seed does NOT trigger a cascade."""
        _populate_prerequisites(data_dir, "tactical-objectives")

        def mock_run(prompt: str) -> AgentResult:
            return _make_mock_upper_layer_agent_result(
                data_dir, "tactical-objectives"
            )

        with mock_agent_session_with_side_effect(mock_run), patch(
            "policy_factory.server.routers.seed.trigger_cascade",
            new_callable=AsyncMock,
        ) as mock_cascade:
            resp = client.post(
                "/api/seed/tactical-objectives", headers=auth_headers
            )

        assert resp.status_code == 200
        mock_cascade.assert_not_called()

    def test_fails_when_only_values_and_sa_populated(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        data_dir: Path,
    ) -> None:
        """Fails when strategic-objectives is empty even if values and SA are fine."""
        _populate_layer(data_dir, "values")
        _populate_layer(data_dir, "situational-awareness")
        # strategic-objectives deliberately not populated

        resp = client.post(
            "/api/seed/tactical-objectives", headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert "strategic-objectives" in data["message"]

    def test_prerequisite_failure_does_not_clear_items(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        data_dir: Path,
    ) -> None:
        """When prerequisites fail, existing target items are preserved."""
        _populate_layer(data_dir, "tactical-objectives", count=1)

        resp = client.post(
            "/api/seed/tactical-objectives", headers=auth_headers
        )

        assert resp.status_code == 200
        assert resp.json()["success"] is False

        items = list_items(data_dir, "tactical-objectives")
        assert len(items) == 1


# ---------------------------------------------------------------------------
# Policies Seeding Flow Tests
# ---------------------------------------------------------------------------


class TestPoliciesSeedingFlow:
    """Integration tests for POST /api/seed/policies."""

    def test_requires_auth(self, client: TestClient) -> None:
        resp = client.post("/api/seed/policies")
        assert resp.status_code == 401

    def test_creates_items_in_correct_directory(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        data_dir: Path,
    ) -> None:
        """Agent-written files appear in policies directory."""
        _populate_prerequisites(data_dir, "policies")

        def mock_run(prompt: str) -> AgentResult:
            return _make_mock_upper_layer_agent_result(data_dir, "policies")

        with mock_agent_session_with_side_effect(mock_run):
            resp = client.post("/api/seed/policies", headers=auth_headers)

        assert resp.status_code == 200
        assert resp.json()["success"] is True

        items = list_items(data_dir, "policies")
        assert len(items) == 2

    def test_clears_existing_items(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        data_dir: Path,
    ) -> None:
        """Old items are removed before seeding."""
        _populate_prerequisites(data_dir, "policies")
        _populate_layer(data_dir, "policies", count=4)

        def mock_run(prompt: str) -> AgentResult:
            return _make_mock_upper_layer_agent_result(data_dir, "policies")

        with mock_agent_session_with_side_effect(mock_run):
            resp = client.post("/api/seed/policies", headers=auth_headers)

        assert resp.status_code == 200

        items = list_items(data_dir, "policies")
        filenames = {item.filename for item in items}
        assert "item-1.md" not in filenames
        assert "item-alpha.md" in filenames

    def test_commits_to_git(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        data_dir: Path,
    ) -> None:
        """A git commit is made after successful seeding."""
        _populate_prerequisites(data_dir, "policies")

        log_before = _run_git(["rev-list", "--count", "HEAD"], cwd=data_dir)
        count_before = int(log_before.stdout.strip())

        def mock_run(prompt: str) -> AgentResult:
            return _make_mock_upper_layer_agent_result(data_dir, "policies")

        with mock_agent_session_with_side_effect(mock_run):
            resp = client.post("/api/seed/policies", headers=auth_headers)

        assert resp.status_code == 200

        log_after = _run_git(["rev-list", "--count", "HEAD"], cwd=data_dir)
        count_after = int(log_after.stdout.strip())
        assert count_after == count_before + 1

        log_msg = _run_git(["log", "-1", "--format=%s"], cwd=data_dir)
        assert "policies" in log_msg.stdout.lower()

    def test_records_agent_run(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        data_dir: Path,
        store: PolicyStore,
    ) -> None:
        """An agent run record is created with the correct agent type."""
        _populate_prerequisites(data_dir, "policies")

        def mock_run(prompt: str) -> AgentResult:
            return _make_mock_upper_layer_agent_result(data_dir, "policies")

        with mock_agent_session_with_side_effect(mock_run):
            resp = client.post("/api/seed/policies", headers=auth_headers)

        assert resp.status_code == 200

        runs = store.list_agent_runs(agent_type="policies-seed")
        assert len(runs) == 1
        assert runs[0].target_layer == "policies"
        assert runs[0].success is True

    def test_returns_error_on_agent_failure(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        data_dir: Path,
    ) -> None:
        """Returns failure response when the agent errors."""
        _populate_prerequisites(data_dir, "policies")

        mock_result = _make_mock_failing_agent_result()
        with mock_agent_session(mock_result):
            resp = client.post("/api/seed/policies", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert "failed" in data["message"].lower()

    def test_does_not_trigger_cascade(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        data_dir: Path,
    ) -> None:
        """Policies seed does NOT trigger a cascade."""
        _populate_prerequisites(data_dir, "policies")

        def mock_run(prompt: str) -> AgentResult:
            return _make_mock_upper_layer_agent_result(data_dir, "policies")

        with mock_agent_session_with_side_effect(mock_run), patch(
            "policy_factory.server.routers.seed.trigger_cascade",
            new_callable=AsyncMock,
        ) as mock_cascade:
            resp = client.post("/api/seed/policies", headers=auth_headers)

        assert resp.status_code == 200
        mock_cascade.assert_not_called()

    def test_fails_when_any_single_prerequisite_empty(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        data_dir: Path,
    ) -> None:
        """Fails when tactical is empty even if all other 3 prerequisites are populated."""
        _populate_layer(data_dir, "values")
        _populate_layer(data_dir, "situational-awareness")
        _populate_layer(data_dir, "strategic-objectives")
        # tactical-objectives deliberately not populated

        resp = client.post("/api/seed/policies", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert "tactical-objectives" in data["message"]

    def test_prerequisite_failure_does_not_clear_items(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        data_dir: Path,
    ) -> None:
        """When prerequisites fail, existing target items are preserved."""
        _populate_layer(data_dir, "policies", count=3)

        resp = client.post("/api/seed/policies", headers=auth_headers)

        assert resp.status_code == 200
        assert resp.json()["success"] is False

        items = list_items(data_dir, "policies")
        assert len(items) == 3
