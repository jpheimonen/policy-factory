"""Integration tests for conversation feature, philosophy layer, and values prompt fix.

Tests conversation API endpoints, conversation runner with mocked agent,
cascade triggering from conversations, philosophy layer in cascade,
WebSocket event broadcasting, and values prompt tension-pair format.
"""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import policy_factory.auth as auth_mod
from policy_factory.agent.session import AgentResult
from policy_factory.auth import create_access_token, hash_password
from policy_factory.data.git import _run_git
from policy_factory.data.init import initialize_data_directory
from policy_factory.data.layers import FOUNDATIONAL_LAYERS, LAYER_SLUGS, LAYERS
from policy_factory.events import (
    BaseEvent,
    ConversationCascadePending,
    ConversationFileEdit,
    ConversationStarted,
    ConversationTurnComplete,
    ConversationTurnError,
    EventEmitter,
)
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
    auth_mod.JWT_SECRET_KEY = "test-secret-key-for-conversations-integration"
    auth_mod.JWT_EXPIRY_HOURS = 24
    yield
    auth_mod.JWT_SECRET_KEY = original_key
    auth_mod.JWT_EXPIRY_HOURS = original_expiry


@pytest.fixture
def store(tmp_path: Path) -> PolicyStore:
    """Provide a fresh PolicyStore instance."""
    return PolicyStore(tmp_path / "test.db")


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """Create a temporary data directory with git and all layer subdirectories."""
    d = tmp_path / "data"
    initialize_data_directory(d)
    return d


@pytest.fixture
def empty_data_dir(tmp_path: Path) -> Path:
    """Create a temporary data directory with just layer subdirectories (no git)."""
    d = tmp_path / "data"
    for slug in LAYER_SLUGS:
        (d / slug).mkdir(parents=True, exist_ok=True)
        (d / slug / "README.md").write_text(f"# {slug}\n\nSummary.")
    return d


@pytest.fixture
def emitter() -> EventEmitter:
    """Provide a fresh EventEmitter instance."""
    return EventEmitter()


@pytest.fixture
def ws_manager() -> ConnectionManager:
    """Provide a fresh WebSocket ConnectionManager."""
    return ConnectionManager()


@pytest.fixture
def client(
    store: PolicyStore, empty_data_dir: Path, emitter: EventEmitter, ws_manager: ConnectionManager
) -> Generator[TestClient, None, None]:
    """Provide a TestClient with all dependencies wired up."""
    app = create_app(
        store=store,
        data_dir=empty_data_dir,
        event_emitter=emitter,
        ws_manager=ws_manager,
    )
    with TestClient(app) as c:
        yield c


@pytest.fixture
def client_with_git(
    store: PolicyStore, data_dir: Path, emitter: EventEmitter, ws_manager: ConnectionManager
) -> Generator[TestClient, None, None]:
    """Provide a TestClient with git-initialized data directory."""
    app = create_app(
        store=store,
        data_dir=data_dir,
        event_emitter=emitter,
        ws_manager=ws_manager,
    )
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_headers(store: PolicyStore) -> dict[str, str]:
    """Create an admin user and return Authorization headers."""
    hashed = hash_password("testpassword")
    user_id = store.create_user("test@example.com", hashed, "admin")
    token = create_access_token(user_id, "test@example.com", "admin")
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Event capture fixture
# ---------------------------------------------------------------------------


class EventCapture:
    """Captures emitted events for testing."""

    def __init__(self) -> None:
        self.events: list[BaseEvent] = []
        self._lock = asyncio.Lock()

    async def handler(self, event: BaseEvent) -> None:
        """Event handler that records all events."""
        async with self._lock:
            self.events.append(event)

    def get_events_of_type(self, event_type: str) -> list[BaseEvent]:
        """Return all events matching the given event type."""
        return [e for e in self.events if e.event_type == event_type]

    def clear(self) -> None:
        """Clear captured events."""
        self.events.clear()


@pytest.fixture
def captured_events(emitter: EventEmitter) -> EventCapture:
    """Create an event capture and subscribe it to the emitter."""
    capture = EventCapture()
    emitter.subscribe(capture.handler)
    return capture


# ---------------------------------------------------------------------------
# Mock helpers for agent execution
# ---------------------------------------------------------------------------


def _make_mock_conversation_agent_result(
    response_text: str = "I understand your concern. Let me address this.",
    file_edits: list[tuple[str, str]] | None = None,
) -> AgentResult:
    """Create a mock AgentResult for conversation turns.

    Args:
        response_text: The assistant's response text.
        file_edits: List of (path, action) tuples for simulated file edits.
            Each path should be "layer/filename.md", action is "write" or "delete".

    Returns:
        An AgentResult with full_output containing tool call markers if file_edits provided.
    """
    full_output = response_text

    # Add tool call markers if file edits are provided
    if file_edits:
        for path, action in file_edits:
            tool_name = "write_file" if action == "write" else "delete_file"
            full_output += f'\n<tool_use name="{tool_name}">{{"path": "{path}", "content": "..."}}</tool_use>'

    return AgentResult(
        is_error=False,
        result_text=response_text,
        full_output=full_output,
        total_cost_usd=0.01,
        num_turns=1,
    )


def _make_mock_failing_agent_result(error_message: str = "Agent timeout") -> AgentResult:
    """Create a mock AgentResult for failing agent."""
    return AgentResult(
        is_error=True,
        result_text=error_message,
        full_output="",
        total_cost_usd=0.0,
        num_turns=1,
    )


@contextmanager
def mock_conversation_agent(
    mock_result: AgentResult,
    data_dir: Path | None = None,
    file_edits: list[tuple[str, str]] | None = None,
):
    """Context manager that mocks AgentSession for conversation tests.

    Args:
        mock_result: The AgentResult to return from session.run()
        data_dir: Optional data directory to write actual files to
        file_edits: Optional list of (path, action) tuples to simulate file writes

    Yields:
        The mock session for inspection.
    """
    mock_session = MagicMock()

    async def mock_run(prompt: str) -> AgentResult:
        # Simulate file writes if provided
        if data_dir and file_edits:
            for path, action in file_edits:
                if action == "write" and "/" in path:
                    layer_slug, filename = path.split("/", 1)
                    file_path = data_dir / layer_slug / filename
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    file_path.write_text(f"---\ntitle: Mock Item\n---\n\nMock content.")
                elif action == "delete" and "/" in path:
                    layer_slug, filename = path.split("/", 1)
                    file_path = data_dir / layer_slug / filename
                    if file_path.exists():
                        file_path.unlink()
        return mock_result

    mock_session.run = AsyncMock(side_effect=mock_run)

    # Patch where AgentSession is imported in the runner module
    with patch(
        "policy_factory.conversation.runner.AgentSession",
        return_value=mock_session,
    ):
        yield mock_session


# ---------------------------------------------------------------------------
# TestConversationAPI
# ---------------------------------------------------------------------------


class TestConversationAPI:
    """Tests for the conversation REST API endpoints."""

    def test_create_conversation_with_valid_layer(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """POST /api/conversations creates conversation with valid layer_slug."""
        resp = client.post(
            "/api/conversations/",
            json={"layer_slug": "values"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["layer_slug"] == "values"
        assert data["filename"] is None
        assert "id" in data
        assert "created_at" in data
        assert "last_active_at" in data

    def test_create_conversation_invalid_layer_returns_400(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """POST /api/conversations returns 400 for invalid layer_slug."""
        resp = client.post(
            "/api/conversations/",
            json={"layer_slug": "invalid-layer"},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "Invalid layer_slug" in resp.json()["detail"]

    def test_create_conversation_requires_authentication(
        self,
        client: TestClient,
    ) -> None:
        """POST /api/conversations requires authentication (401 without token)."""
        resp = client.post(
            "/api/conversations/",
            json={"layer_slug": "values"},
        )
        assert resp.status_code == 401

    def test_create_conversation_with_item(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        empty_data_dir: Path,
    ) -> None:
        """POST /api/conversations creates item-level conversation."""
        # Create a test item
        item_path = empty_data_dir / "values" / "test-value.md"
        item_path.write_text("---\ntitle: Test Value\n---\n\nContent.")

        resp = client.post(
            "/api/conversations/",
            json={"layer_slug": "values", "filename": "test-value.md"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["layer_slug"] == "values"
        assert data["filename"] == "test-value.md"

    def test_create_conversation_with_nonexistent_item_returns_404(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """POST /api/conversations returns 404 for non-existent item."""
        resp = client.post(
            "/api/conversations/",
            json={"layer_slug": "values", "filename": "does-not-exist.md"},
            headers=auth_headers,
        )
        assert resp.status_code == 404
        assert "Item not found" in resp.json()["detail"]

    def test_list_conversations_by_layer(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        store: PolicyStore,
    ) -> None:
        """GET /api/conversations?layer_slug=X returns conversations for that layer."""
        # Create test conversations
        store.create_conversation("values")
        store.create_conversation("values")
        store.create_conversation("policies")

        resp = client.get(
            "/api/conversations/?layer_slug=values",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["conversations"]) == 2
        for conv in data["conversations"]:
            assert conv["layer_slug"] == "values"

    def test_list_conversations_by_item(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        store: PolicyStore,
    ) -> None:
        """GET /api/conversations?layer_slug=X&filename=Y returns item-level conversations."""
        # Create test conversations
        store.create_conversation("values", "item-a.md")
        store.create_conversation("values", "item-a.md")
        store.create_conversation("values", "item-b.md")
        store.create_conversation("values")  # Layer-level

        resp = client.get(
            "/api/conversations/?layer_slug=values&filename=item-a.md",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["conversations"]) == 2
        for conv in data["conversations"]:
            assert conv["layer_slug"] == "values"
            assert conv["filename"] == "item-a.md"

    def test_get_conversation_with_messages(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        store: PolicyStore,
    ) -> None:
        """GET /api/conversations/{id} returns conversation with messages."""
        conv_id = store.create_conversation("values")
        store.add_message(conv_id, "user", "Hello!")
        store.add_message(conv_id, "assistant", "Hi there!", files_edited=["values/test.md"])

        resp = client.get(
            f"/api/conversations/{conv_id}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["conversation"]["id"] == conv_id
        assert data["conversation"]["layer_slug"] == "values"
        assert len(data["messages"]) == 2
        assert data["messages"][0]["role"] == "user"
        assert data["messages"][0]["content"] == "Hello!"
        assert data["messages"][1]["role"] == "assistant"
        assert data["messages"][1]["content"] == "Hi there!"
        assert data["messages"][1]["files_edited"] == ["values/test.md"]

    def test_get_conversation_not_found(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """GET /api/conversations/{id} returns 404 for non-existent ID."""
        resp = client.get(
            "/api/conversations/nonexistent-id",
            headers=auth_headers,
        )
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_send_message_returns_202(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        store: PolicyStore,
    ) -> None:
        """POST /api/conversations/{id}/messages returns 202 (accepted for processing)."""
        conv_id = store.create_conversation("values")

        # Mock the conversation runner at the source module level
        with patch(
            "policy_factory.conversation.runner.run_conversation_turn",
            new_callable=AsyncMock,
        ):
            resp = client.post(
                f"/api/conversations/{conv_id}/messages",
                json={"content": "Test message"},
                headers=auth_headers,
            )

        assert resp.status_code == 202
        data = resp.json()
        assert "message_id" in data

        # Verify the user message was stored
        messages = store.get_messages(conv_id)
        assert len(messages) == 1
        assert messages[0].role == "user"
        assert messages[0].content == "Test message"

    def test_send_message_to_nonexistent_conversation(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """POST /api/conversations/{id}/messages returns 404 for non-existent conversation."""
        resp = client.post(
            "/api/conversations/nonexistent-id/messages",
            json={"content": "Test message"},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_delete_conversation(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        store: PolicyStore,
    ) -> None:
        """DELETE /api/conversations/{id} removes conversation and all messages."""
        conv_id = store.create_conversation("values")
        store.add_message(conv_id, "user", "Hello!")
        store.add_message(conv_id, "assistant", "Hi!")

        resp = client.delete(
            f"/api/conversations/{conv_id}",
            headers=auth_headers,
        )
        assert resp.status_code == 204

        # Verify conversation and messages are deleted
        assert store.get_conversation(conv_id) is None
        assert len(store.get_messages(conv_id)) == 0

    def test_delete_conversation_not_found(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """DELETE /api/conversations/{id} returns 404 for non-existent ID."""
        resp = client.delete(
            "/api/conversations/nonexistent-id",
            headers=auth_headers,
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# TestConversationTurnWithMockedAgent
# ---------------------------------------------------------------------------


class TestConversationTurnWithMockedAgent:
    """Tests for the conversation runner with mocked agent."""

    @pytest.mark.asyncio
    async def test_full_turn_stores_messages(
        self,
        store: PolicyStore,
        emitter: EventEmitter,
        empty_data_dir: Path,
    ) -> None:
        """Full turn stores both user message and assistant response."""
        from policy_factory.conversation.runner import run_conversation_turn

        conv_id = store.create_conversation("values")
        # The user message is stored before calling run_conversation_turn (by the API)
        store.add_message(conv_id, "user", "What are the current values?")

        mock_result = _make_mock_conversation_agent_result(
            "The current values include security and prosperity."
        )

        with mock_conversation_agent(mock_result):
            await run_conversation_turn(
                conversation_id=conv_id,
                user_content="What are the current values?",
                store=store,
                emitter=emitter,
                data_dir=empty_data_dir,
            )

        messages = store.get_messages(conv_id)
        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[1].role == "assistant"
        assert "current values" in messages[1].content

    @pytest.mark.asyncio
    async def test_file_write_triggers_event(
        self,
        store: PolicyStore,
        emitter: EventEmitter,
        empty_data_dir: Path,
        captured_events: EventCapture,
    ) -> None:
        """Agent file write triggers ConversationFileEdit event."""
        from policy_factory.conversation.runner import run_conversation_turn

        conv_id = store.create_conversation("values")
        store.add_message(conv_id, "user", "Update the security value")

        file_edits = [("values/security.md", "write")]
        mock_result = _make_mock_conversation_agent_result(
            "I've updated the security value.",
            file_edits=file_edits,
        )

        with mock_conversation_agent(mock_result, empty_data_dir, file_edits):
            await run_conversation_turn(
                conversation_id=conv_id,
                user_content="Update the security value",
                store=store,
                emitter=emitter,
                data_dir=empty_data_dir,
            )

        # Check for file edit event
        file_edit_events = captured_events.get_events_of_type("conversation_file_edit")
        assert len(file_edit_events) >= 1
        event = file_edit_events[0]
        assert isinstance(event, ConversationFileEdit)
        assert event.layer_slug == "values"
        assert event.filename == "security.md"
        assert event.action == "write"

    @pytest.mark.asyncio
    async def test_file_delete_triggers_event(
        self,
        store: PolicyStore,
        emitter: EventEmitter,
        empty_data_dir: Path,
        captured_events: EventCapture,
    ) -> None:
        """Agent file delete triggers ConversationFileEdit event with action='deleted'."""
        from policy_factory.conversation.runner import run_conversation_turn

        # Create a file to delete
        (empty_data_dir / "values" / "obsolete.md").write_text("---\ntitle: Old\n---\nContent")

        conv_id = store.create_conversation("values")
        store.add_message(conv_id, "user", "Remove the obsolete value")

        file_edits = [("values/obsolete.md", "delete")]
        mock_result = _make_mock_conversation_agent_result(
            "I've removed the obsolete value.",
            file_edits=file_edits,
        )

        with mock_conversation_agent(mock_result, empty_data_dir, file_edits):
            await run_conversation_turn(
                conversation_id=conv_id,
                user_content="Remove the obsolete value",
                store=store,
                emitter=emitter,
                data_dir=empty_data_dir,
            )

        # Check for file edit event
        file_edit_events = captured_events.get_events_of_type("conversation_file_edit")
        assert len(file_edit_events) >= 1
        event = file_edit_events[0]
        assert isinstance(event, ConversationFileEdit)
        assert event.action == "delete"

    @pytest.mark.asyncio
    async def test_multiple_file_edits_recorded(
        self,
        store: PolicyStore,
        emitter: EventEmitter,
        empty_data_dir: Path,
    ) -> None:
        """Multiple file edits in single turn are all recorded in files_edited."""
        from policy_factory.conversation.runner import run_conversation_turn

        conv_id = store.create_conversation("values")
        store.add_message(conv_id, "user", "Update multiple values")

        file_edits = [
            ("values/security.md", "write"),
            ("values/prosperity.md", "write"),
            ("values/liberty.md", "write"),
        ]
        mock_result = _make_mock_conversation_agent_result(
            "I've updated all three values.",
            file_edits=file_edits,
        )

        with mock_conversation_agent(mock_result, empty_data_dir, file_edits):
            await run_conversation_turn(
                conversation_id=conv_id,
                user_content="Update multiple values",
                store=store,
                emitter=emitter,
                data_dir=empty_data_dir,
            )

        messages = store.get_messages(conv_id)
        assistant_msg = [m for m in messages if m.role == "assistant"][0]
        assert assistant_msg.files_edited is not None
        assert len(assistant_msg.files_edited) == 3
        assert "values/security.md" in assistant_msg.files_edited
        assert "values/prosperity.md" in assistant_msg.files_edited
        assert "values/liberty.md" in assistant_msg.files_edited

    @pytest.mark.asyncio
    async def test_git_commit_after_file_edits(
        self,
        store: PolicyStore,
        emitter: EventEmitter,
        data_dir: Path,  # Uses git-initialized directory
    ) -> None:
        """Git commit is created after turn with file edits."""
        from policy_factory.conversation.runner import run_conversation_turn

        # Get initial commit count
        result = _run_git(["rev-list", "--count", "HEAD"], cwd=data_dir)
        initial_count = int(result.stdout.strip())

        conv_id = store.create_conversation("values")
        store.add_message(conv_id, "user", "Add a new value")

        file_edits = [("values/new-value.md", "write")]
        mock_result = _make_mock_conversation_agent_result(
            "I've added the new value.",
            file_edits=file_edits,
        )

        with mock_conversation_agent(mock_result, data_dir, file_edits):
            await run_conversation_turn(
                conversation_id=conv_id,
                user_content="Add a new value",
                store=store,
                emitter=emitter,
                data_dir=data_dir,
            )

        # Verify commit was created
        result = _run_git(["rev-list", "--count", "HEAD"], cwd=data_dir)
        final_count = int(result.stdout.strip())
        assert final_count == initial_count + 1

    @pytest.mark.asyncio
    async def test_git_commit_includes_conversation_context(
        self,
        store: PolicyStore,
        emitter: EventEmitter,
        data_dir: Path,
    ) -> None:
        """Git commit message includes conversation context (layer, item)."""
        from policy_factory.conversation.runner import run_conversation_turn

        conv_id = store.create_conversation("values")
        store.add_message(conv_id, "user", "Update values")

        file_edits = [("values/test.md", "write")]
        mock_result = _make_mock_conversation_agent_result(
            "Done.",
            file_edits=file_edits,
        )

        with mock_conversation_agent(mock_result, data_dir, file_edits):
            await run_conversation_turn(
                conversation_id=conv_id,
                user_content="Update values",
                store=store,
                emitter=emitter,
                data_dir=data_dir,
            )

        # Get last commit message
        result = _run_git(["log", "-1", "--pretty=%B"], cwd=data_dir)
        commit_msg = result.stdout.strip()
        assert "Conversation edit" in commit_msg
        assert conv_id[:8] in commit_msg

    @pytest.mark.asyncio
    async def test_agent_error_stores_error_message(
        self,
        store: PolicyStore,
        emitter: EventEmitter,
        empty_data_dir: Path,
    ) -> None:
        """Agent timeout results in error message stored."""
        from policy_factory.conversation.runner import run_conversation_turn

        conv_id = store.create_conversation("values")
        store.add_message(conv_id, "user", "Do something complex")

        mock_result = _make_mock_failing_agent_result("Agent timeout after 60 seconds")

        with mock_conversation_agent(mock_result):
            await run_conversation_turn(
                conversation_id=conv_id,
                user_content="Do something complex",
                store=store,
                emitter=emitter,
                data_dir=empty_data_dir,
            )

        messages = store.get_messages(conv_id)
        assistant_msg = [m for m in messages if m.role == "assistant"][0]
        assert "[Error:" in assistant_msg.content
        assert "timeout" in assistant_msg.content.lower()


# ---------------------------------------------------------------------------
# TestConversationCascadeIntegration
# ---------------------------------------------------------------------------


class TestConversationCascadeIntegration:
    """Tests for cascade triggering from conversations."""

    @pytest.mark.asyncio
    async def test_philosophy_edit_creates_pending_cascade(
        self,
        store: PolicyStore,
        emitter: EventEmitter,
        empty_data_dir: Path,
    ) -> None:
        """Edit to philosophy layer creates pending cascade with starting_layer='philosophy'."""
        from policy_factory.conversation.runner import run_conversation_turn

        conv_id = store.create_conversation("philosophy")
        store.add_message(conv_id, "user", "Update the philosophy")

        file_edits = [("philosophy/axioms.md", "write")]
        mock_result = _make_mock_conversation_agent_result(
            "Updated philosophy.",
            file_edits=file_edits,
        )

        with mock_conversation_agent(mock_result, empty_data_dir, file_edits):
            await run_conversation_turn(
                conversation_id=conv_id,
                user_content="Update the philosophy",
                store=store,
                emitter=emitter,
                data_dir=empty_data_dir,
            )

        pending = store.get_pending_cascade()
        assert pending is not None
        assert pending.starting_layer == "philosophy"
        assert pending.conversation_id == conv_id

    @pytest.mark.asyncio
    async def test_values_edit_creates_pending_cascade(
        self,
        store: PolicyStore,
        emitter: EventEmitter,
        empty_data_dir: Path,
    ) -> None:
        """Edit to values layer creates pending cascade with starting_layer='values'."""
        from policy_factory.conversation.runner import run_conversation_turn

        conv_id = store.create_conversation("values")
        store.add_message(conv_id, "user", "Update values")

        file_edits = [("values/security.md", "write")]
        mock_result = _make_mock_conversation_agent_result(
            "Updated values.",
            file_edits=file_edits,
        )

        with mock_conversation_agent(mock_result, empty_data_dir, file_edits):
            await run_conversation_turn(
                conversation_id=conv_id,
                user_content="Update values",
                store=store,
                emitter=emitter,
                data_dir=empty_data_dir,
            )

        pending = store.get_pending_cascade()
        assert pending is not None
        assert pending.starting_layer == "values"

    @pytest.mark.asyncio
    async def test_situational_awareness_edit_creates_pending_cascade(
        self,
        store: PolicyStore,
        emitter: EventEmitter,
        empty_data_dir: Path,
    ) -> None:
        """Edit to situational-awareness creates pending cascade."""
        from policy_factory.conversation.runner import run_conversation_turn

        conv_id = store.create_conversation("situational-awareness")
        store.add_message(conv_id, "user", "Update SA")

        file_edits = [("situational-awareness/geopolitics.md", "write")]
        mock_result = _make_mock_conversation_agent_result(
            "Updated SA.",
            file_edits=file_edits,
        )

        with mock_conversation_agent(mock_result, empty_data_dir, file_edits):
            await run_conversation_turn(
                conversation_id=conv_id,
                user_content="Update SA",
                store=store,
                emitter=emitter,
                data_dir=empty_data_dir,
            )

        pending = store.get_pending_cascade()
        assert pending is not None
        assert pending.starting_layer == "situational-awareness"

    @pytest.mark.asyncio
    async def test_strategic_objectives_edit_no_pending_cascade(
        self,
        store: PolicyStore,
        emitter: EventEmitter,
        empty_data_dir: Path,
    ) -> None:
        """Edit to strategic-objectives does NOT create pending cascade."""
        from policy_factory.conversation.runner import run_conversation_turn

        conv_id = store.create_conversation("strategic-objectives")
        store.add_message(conv_id, "user", "Update strategic objectives")

        file_edits = [("strategic-objectives/goal.md", "write")]
        mock_result = _make_mock_conversation_agent_result(
            "Updated strategic objectives.",
            file_edits=file_edits,
        )

        with mock_conversation_agent(mock_result, empty_data_dir, file_edits):
            await run_conversation_turn(
                conversation_id=conv_id,
                user_content="Update strategic objectives",
                store=store,
                emitter=emitter,
                data_dir=empty_data_dir,
            )

        pending = store.get_pending_cascade()
        assert pending is None

    @pytest.mark.asyncio
    async def test_tactical_objectives_edit_no_pending_cascade(
        self,
        store: PolicyStore,
        emitter: EventEmitter,
        empty_data_dir: Path,
    ) -> None:
        """Edit to tactical-objectives does NOT create pending cascade."""
        from policy_factory.conversation.runner import run_conversation_turn

        conv_id = store.create_conversation("tactical-objectives")
        store.add_message(conv_id, "user", "Update tactical objectives")

        file_edits = [("tactical-objectives/action.md", "write")]
        mock_result = _make_mock_conversation_agent_result(
            "Updated tactical objectives.",
            file_edits=file_edits,
        )

        with mock_conversation_agent(mock_result, empty_data_dir, file_edits):
            await run_conversation_turn(
                conversation_id=conv_id,
                user_content="Update tactical objectives",
                store=store,
                emitter=emitter,
                data_dir=empty_data_dir,
            )

        pending = store.get_pending_cascade()
        assert pending is None

    @pytest.mark.asyncio
    async def test_policies_edit_no_pending_cascade(
        self,
        store: PolicyStore,
        emitter: EventEmitter,
        empty_data_dir: Path,
    ) -> None:
        """Edit to policies does NOT create pending cascade."""
        from policy_factory.conversation.runner import run_conversation_turn

        conv_id = store.create_conversation("policies")
        store.add_message(conv_id, "user", "Update policies")

        file_edits = [("policies/policy.md", "write")]
        mock_result = _make_mock_conversation_agent_result(
            "Updated policies.",
            file_edits=file_edits,
        )

        with mock_conversation_agent(mock_result, empty_data_dir, file_edits):
            await run_conversation_turn(
                conversation_id=conv_id,
                user_content="Update policies",
                store=store,
                emitter=emitter,
                data_dir=empty_data_dir,
            )

        pending = store.get_pending_cascade()
        assert pending is None

    @pytest.mark.asyncio
    async def test_multiple_edits_same_layer_no_duplicate_pending(
        self,
        store: PolicyStore,
        emitter: EventEmitter,
        empty_data_dir: Path,
    ) -> None:
        """Multiple edits to same foundational layer do not create duplicate pending cascades."""
        from policy_factory.conversation.runner import run_conversation_turn

        conv_id = store.create_conversation("values")

        # First turn
        store.add_message(conv_id, "user", "Update first value")
        file_edits1 = [("values/value1.md", "write")]
        mock_result1 = _make_mock_conversation_agent_result(
            "Updated value 1.",
            file_edits=file_edits1,
        )

        with mock_conversation_agent(mock_result1, empty_data_dir, file_edits1):
            await run_conversation_turn(
                conversation_id=conv_id,
                user_content="Update first value",
                store=store,
                emitter=emitter,
                data_dir=empty_data_dir,
            )

        # Second turn
        store.add_message(conv_id, "user", "Update second value")
        file_edits2 = [("values/value2.md", "write")]
        mock_result2 = _make_mock_conversation_agent_result(
            "Updated value 2.",
            file_edits=file_edits2,
        )

        with mock_conversation_agent(mock_result2, empty_data_dir, file_edits2):
            await run_conversation_turn(
                conversation_id=conv_id,
                user_content="Update second value",
                store=store,
                emitter=emitter,
                data_dir=empty_data_dir,
            )

        # Should still only have one pending cascade
        pending = store.get_pending_cascade()
        assert pending is not None
        assert pending.starting_layer == "values"
        assert "values" in pending.affected_layers

    @pytest.mark.asyncio
    async def test_lower_layer_edit_updates_starting_layer(
        self,
        store: PolicyStore,
        emitter: EventEmitter,
        empty_data_dir: Path,
    ) -> None:
        """Edit to lower foundational layer updates pending cascade starting_layer."""
        from policy_factory.conversation.runner import run_conversation_turn

        # First, edit values layer
        conv_id = store.create_conversation("values")
        store.add_message(conv_id, "user", "Update values")
        file_edits1 = [("values/value.md", "write")]
        mock_result1 = _make_mock_conversation_agent_result(
            "Updated values.",
            file_edits=file_edits1,
        )

        with mock_conversation_agent(mock_result1, empty_data_dir, file_edits1):
            await run_conversation_turn(
                conversation_id=conv_id,
                user_content="Update values",
                store=store,
                emitter=emitter,
                data_dir=empty_data_dir,
            )

        pending = store.get_pending_cascade()
        assert pending.starting_layer == "values"

        # Now edit philosophy layer (lower)
        conv_id2 = store.create_conversation("philosophy")
        store.add_message(conv_id2, "user", "Update philosophy")
        file_edits2 = [("philosophy/axiom.md", "write")]
        mock_result2 = _make_mock_conversation_agent_result(
            "Updated philosophy.",
            file_edits=file_edits2,
        )

        with mock_conversation_agent(mock_result2, empty_data_dir, file_edits2):
            await run_conversation_turn(
                conversation_id=conv_id2,
                user_content="Update philosophy",
                store=store,
                emitter=emitter,
                data_dir=empty_data_dir,
            )

        # Starting layer should now be philosophy (lower)
        pending = store.get_pending_cascade()
        assert pending.starting_layer == "philosophy"

    def test_trigger_pending_cascade_endpoint(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        store: PolicyStore,
    ) -> None:
        """POST /api/cascade/trigger-pending starts cascade from pending record."""
        # Create pending cascade
        store.create_or_update_pending_cascade(
            conversation_id="test-conv-id",
            starting_layer="values",
        )

        # Mock trigger_cascade to avoid actual cascade execution
        with patch(
            "policy_factory.server.routers.cascade.trigger_cascade",
            new_callable=AsyncMock,
        ) as mock_trigger:
            mock_trigger.return_value = ("cascade-id-123", True)

            resp = client.post(
                "/api/cascade/trigger-pending",
                headers=auth_headers,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["cascade_id"] == "cascade-id-123"
        assert data["is_cascade"] is True

        # Pending cascade should be cleared
        assert store.get_pending_cascade() is None

    def test_trigger_pending_no_pending_returns_404(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        store: PolicyStore,
    ) -> None:
        """POST /api/cascade/trigger-pending returns 404 when no pending exists."""
        resp = client.post(
            "/api/cascade/trigger-pending",
            headers=auth_headers,
        )
        assert resp.status_code == 404
        assert "No pending cascade" in resp.json()["detail"]

    def test_dismiss_pending_cascade_endpoint(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        store: PolicyStore,
    ) -> None:
        """DELETE /api/cascade/pending clears pending without running cascade."""
        # Create pending cascade
        store.create_or_update_pending_cascade(
            conversation_id="test-conv-id",
            starting_layer="values",
        )

        resp = client.delete(
            "/api/cascade/pending",
            headers=auth_headers,
        )
        assert resp.status_code == 204

        # Pending cascade should be cleared
        assert store.get_pending_cascade() is None

    @pytest.mark.asyncio
    async def test_pending_cascade_persists_across_turns(
        self,
        store: PolicyStore,
        emitter: EventEmitter,
        empty_data_dir: Path,
    ) -> None:
        """Pending cascade persists across multiple conversation turns."""
        from policy_factory.conversation.runner import run_conversation_turn

        conv_id = store.create_conversation("values")

        # Turn 1: Edit that creates pending
        store.add_message(conv_id, "user", "Update value")
        file_edits1 = [("values/value.md", "write")]
        mock_result1 = _make_mock_conversation_agent_result(
            "Updated.",
            file_edits=file_edits1,
        )

        with mock_conversation_agent(mock_result1, empty_data_dir, file_edits1):
            await run_conversation_turn(
                conversation_id=conv_id,
                user_content="Update value",
                store=store,
                emitter=emitter,
                data_dir=empty_data_dir,
            )

        pending1 = store.get_pending_cascade()
        assert pending1 is not None

        # Turn 2: Discussion without edit
        store.add_message(conv_id, "user", "Tell me about the changes")
        mock_result2 = _make_mock_conversation_agent_result(
            "I made these changes...",
            file_edits=None,
        )

        with mock_conversation_agent(mock_result2):
            await run_conversation_turn(
                conversation_id=conv_id,
                user_content="Tell me about the changes",
                store=store,
                emitter=emitter,
                data_dir=empty_data_dir,
            )

        # Pending cascade should still exist
        pending2 = store.get_pending_cascade()
        assert pending2 is not None
        assert pending2.id == pending1.id


# ---------------------------------------------------------------------------
# TestPhilosophyLayerInCascade
# ---------------------------------------------------------------------------


class TestPhilosophyLayerInCascade:
    """Tests for philosophy layer cascade integration."""

    def test_philosophy_layer_exists(self) -> None:
        """Philosophy layer exists in LAYERS list."""
        slugs = [layer.slug for layer in LAYERS]
        assert "philosophy" in slugs

    def test_philosophy_layer_position_1(self) -> None:
        """Philosophy layer is at position 1 (bottommost)."""
        philosophy = next((l for l in LAYERS if l.slug == "philosophy"), None)
        assert philosophy is not None
        assert philosophy.position == 1

    def test_philosophy_is_foundational(self) -> None:
        """Philosophy is included in FOUNDATIONAL_LAYERS."""
        assert "philosophy" in FOUNDATIONAL_LAYERS

    def test_six_layers_total(self) -> None:
        """There are exactly 6 layers in the stack."""
        assert len(LAYERS) == 6

    def test_layer_order_bottom_to_top(self) -> None:
        """Layers are ordered bottom (philosophy) to top (policies)."""
        expected_order = [
            "philosophy",
            "values",
            "situational-awareness",
            "strategic-objectives",
            "tactical-objectives",
            "policies",
        ]
        actual_order = [layer.slug for layer in sorted(LAYERS, key=lambda l: l.position)]
        assert actual_order == expected_order

    def test_cascade_from_philosophy_all_layers(self) -> None:
        """Full cascade from philosophy processes all 6 layers in order."""
        from policy_factory.cascade.orchestrator import layers_from

        # The orchestrator has a helper to get layers to process
        # We test that starting from philosophy includes all layers
        layers_to_process = layers_from("philosophy")
        assert len(layers_to_process) == 6
        assert layers_to_process[0] == "philosophy"
        assert layers_to_process[5] == "policies"

    def test_cascade_from_values_excludes_philosophy(self) -> None:
        """Cascade from values does NOT include philosophy in processing."""
        from policy_factory.cascade.orchestrator import layers_from

        layers_to_process = layers_from("values")
        assert "philosophy" not in layers_to_process
        assert len(layers_to_process) == 5
        assert layers_to_process[0] == "values"

    def test_philosophy_in_values_generation_context(self) -> None:
        """Philosophy content appears in values generation context.

        When generating the values layer, the orchestrator should include
        philosophy layer content as context (layers_below).
        """
        from policy_factory.cascade.orchestrator import layers_below

        # layers_below("values") should include philosophy
        context_layers = layers_below("values")
        assert "philosophy" in context_layers
        assert context_layers == ["philosophy"]  # Only philosophy is below values

    def test_philosophy_directory_in_layer_slugs(self) -> None:
        """Philosophy is a valid layer slug."""
        assert "philosophy" in LAYER_SLUGS


# ---------------------------------------------------------------------------
# TestConversationWebSocketEvents
# ---------------------------------------------------------------------------


class TestConversationWebSocketEvents:
    """Tests for WebSocket event broadcasting during conversations."""

    @pytest.mark.asyncio
    async def test_conversation_started_event(
        self,
        store: PolicyStore,
        emitter: EventEmitter,
        empty_data_dir: Path,
        captured_events: EventCapture,
    ) -> None:
        """ConversationStarted event broadcasts with correct conversation_id."""
        from policy_factory.conversation.runner import run_conversation_turn

        conv_id = store.create_conversation("values")
        store.add_message(conv_id, "user", "Hello")

        mock_result = _make_mock_conversation_agent_result("Hi there!")

        with mock_conversation_agent(mock_result):
            await run_conversation_turn(
                conversation_id=conv_id,
                user_content="Hello",
                store=store,
                emitter=emitter,
                data_dir=empty_data_dir,
            )

        started_events = captured_events.get_events_of_type("conversation_started")
        assert len(started_events) == 1
        event = started_events[0]
        assert isinstance(event, ConversationStarted)
        assert event.conversation_id == conv_id

    @pytest.mark.asyncio
    async def test_conversation_file_edit_event(
        self,
        store: PolicyStore,
        emitter: EventEmitter,
        empty_data_dir: Path,
        captured_events: EventCapture,
    ) -> None:
        """ConversationFileEdit events broadcast for each file operation."""
        from policy_factory.conversation.runner import run_conversation_turn

        conv_id = store.create_conversation("values")
        store.add_message(conv_id, "user", "Update files")

        file_edits = [
            ("values/file1.md", "write"),
            ("values/file2.md", "write"),
        ]
        mock_result = _make_mock_conversation_agent_result(
            "Updated files.",
            file_edits=file_edits,
        )

        with mock_conversation_agent(mock_result, empty_data_dir, file_edits):
            await run_conversation_turn(
                conversation_id=conv_id,
                user_content="Update files",
                store=store,
                emitter=emitter,
                data_dir=empty_data_dir,
            )

        file_edit_events = captured_events.get_events_of_type("conversation_file_edit")
        assert len(file_edit_events) == 2
        filenames = [e.filename for e in file_edit_events]
        assert "file1.md" in filenames
        assert "file2.md" in filenames

    @pytest.mark.asyncio
    async def test_conversation_turn_complete_event(
        self,
        store: PolicyStore,
        emitter: EventEmitter,
        empty_data_dir: Path,
        captured_events: EventCapture,
    ) -> None:
        """ConversationTurnComplete event broadcasts when turn finishes."""
        from policy_factory.conversation.runner import run_conversation_turn

        conv_id = store.create_conversation("values")
        store.add_message(conv_id, "user", "Hello")

        file_edits = [("values/test.md", "write")]
        mock_result = _make_mock_conversation_agent_result(
            "Done!",
            file_edits=file_edits,
        )

        with mock_conversation_agent(mock_result, empty_data_dir, file_edits):
            await run_conversation_turn(
                conversation_id=conv_id,
                user_content="Hello",
                store=store,
                emitter=emitter,
                data_dir=empty_data_dir,
            )

        complete_events = captured_events.get_events_of_type("conversation_turn_complete")
        assert len(complete_events) == 1
        event = complete_events[0]
        assert isinstance(event, ConversationTurnComplete)
        assert event.conversation_id == conv_id
        assert "values/test.md" in event.files_edited

    @pytest.mark.asyncio
    async def test_conversation_cascade_pending_event(
        self,
        store: PolicyStore,
        emitter: EventEmitter,
        empty_data_dir: Path,
        captured_events: EventCapture,
    ) -> None:
        """ConversationCascadePending event broadcasts for foundational edits."""
        from policy_factory.conversation.runner import run_conversation_turn

        conv_id = store.create_conversation("values")
        store.add_message(conv_id, "user", "Update values")

        file_edits = [("values/value.md", "write")]
        mock_result = _make_mock_conversation_agent_result(
            "Updated.",
            file_edits=file_edits,
        )

        with mock_conversation_agent(mock_result, empty_data_dir, file_edits):
            await run_conversation_turn(
                conversation_id=conv_id,
                user_content="Update values",
                store=store,
                emitter=emitter,
                data_dir=empty_data_dir,
            )

        pending_events = captured_events.get_events_of_type("conversation_cascade_pending")
        assert len(pending_events) == 1
        event = pending_events[0]
        assert isinstance(event, ConversationCascadePending)
        assert event.conversation_id == conv_id
        assert event.starting_layer == "values"

    @pytest.mark.asyncio
    async def test_events_include_db_id(
        self,
        store: PolicyStore,
        emitter: EventEmitter,
        empty_data_dir: Path,
        captured_events: EventCapture,
    ) -> None:
        """Events include correct db_id for frontend deduplication."""
        from policy_factory.conversation.runner import run_conversation_turn

        conv_id = store.create_conversation("values")
        store.add_message(conv_id, "user", "Hello")

        mock_result = _make_mock_conversation_agent_result("Hi!")

        with mock_conversation_agent(mock_result):
            await run_conversation_turn(
                conversation_id=conv_id,
                user_content="Hello",
                store=store,
                emitter=emitter,
                data_dir=empty_data_dir,
            )

        # All events should have unique IDs
        event_ids = [e.id for e in captured_events.events]
        assert len(event_ids) == len(set(event_ids)), "Duplicate event IDs found"

    @pytest.mark.asyncio
    async def test_conversation_turn_error_event(
        self,
        store: PolicyStore,
        emitter: EventEmitter,
        empty_data_dir: Path,
        captured_events: EventCapture,
    ) -> None:
        """ConversationTurnError event broadcasts when agent fails."""
        from policy_factory.conversation.runner import run_conversation_turn

        conv_id = store.create_conversation("values")
        store.add_message(conv_id, "user", "Do something")

        mock_result = _make_mock_failing_agent_result("Connection timeout")

        with mock_conversation_agent(mock_result):
            await run_conversation_turn(
                conversation_id=conv_id,
                user_content="Do something",
                store=store,
                emitter=emitter,
                data_dir=empty_data_dir,
            )

        error_events = captured_events.get_events_of_type("conversation_turn_error")
        assert len(error_events) == 1
        event = error_events[0]
        assert isinstance(event, ConversationTurnError)
        assert event.conversation_id == conv_id
        assert "timeout" in event.error_message.lower()


# ---------------------------------------------------------------------------
# TestValuesPromptFix
# ---------------------------------------------------------------------------


class TestValuesPromptFix:
    """Tests verifying updated values prompt produces correct output format."""

    @pytest.fixture
    def values_prompt_path(self) -> Path:
        """Return the path to the values prompt file."""
        # The prompts directory is at src/policy_factory/prompts/
        import policy_factory.prompts
        prompts_dir = Path(policy_factory.prompts.__file__).parent
        return prompts_dir / "generators" / "values.md"

    def test_values_prompt_exists(self, values_prompt_path: Path) -> None:
        """Values generator prompt file exists."""
        assert values_prompt_path.exists()

    def test_values_prompt_requires_vs_format(self, values_prompt_path: Path) -> None:
        """Values prompt explicitly requires 'X vs. Y' format."""
        content = values_prompt_path.read_text()

        # Check for key format requirements
        assert "vs." in content
        assert "X vs. Y" in content or '"X vs. Y"' in content

    def test_values_prompt_rejects_single_topic(self, values_prompt_path: Path) -> None:
        """Values prompt explicitly rejects single-topic titles."""
        content = values_prompt_path.read_text()

        # Check for anti-patterns mentioned
        assert "Single-topic" in content or "single topic" in content.lower()

    def test_values_prompt_requires_tension_pairs(self, values_prompt_path: Path) -> None:
        """Values prompt requires genuine tension-pairs between opposing priorities."""
        content = values_prompt_path.read_text()

        # Check for tension-pair requirements
        assert "tension" in content.lower()
        assert "opposing" in content.lower() or "two priorities" in content.lower()

    def test_values_prompt_includes_bad_examples(self, values_prompt_path: Path) -> None:
        """Values prompt includes examples of bad titles to reject."""
        content = values_prompt_path.read_text()

        # Check for bad examples section
        assert "Bad Titles" in content or "bad titles" in content.lower()
        # Check for specific bad examples mentioned
        assert "Social Welfare" in content or "Environmental Sustainability" in content

    def test_values_prompt_includes_good_examples(self, values_prompt_path: Path) -> None:
        """Values prompt includes examples of good tension-pair titles."""
        content = values_prompt_path.read_text()

        # Check for good examples with vs. format
        assert "Good Titles" in content or "good titles" in content.lower()
        # Check for specific good examples with vs.
        assert "vs." in content

    def test_values_prompt_multi_perspective_requirement(self, values_prompt_path: Path) -> None:
        """Values prompt requires arguments from multiple political perspectives."""
        content = values_prompt_path.read_text()

        # Check for multi-perspective requirements
        assert "Conservative" in content
        assert "Progressive" in content
        assert "Libertarian" in content
        assert "Communitarian" in content

    def test_values_prompt_anti_consensus_filter(self, values_prompt_path: Path) -> None:
        """Values prompt includes anti-consensus filter criteria."""
        content = values_prompt_path.read_text()

        # Check for anti-consensus filter
        assert "Anti-Consensus" in content or "anti-consensus" in content.lower()
        assert "consensus" in content.lower()

    def test_values_prompt_philosophy_grounding(self, values_prompt_path: Path) -> None:
        """Values prompt references philosophy layer as foundation."""
        content = values_prompt_path.read_text()

        # Check for philosophy layer reference
        assert "Philosophy" in content or "philosophy" in content.lower()
        assert "position 1" in content.lower() or "foundational" in content.lower()
