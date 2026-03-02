"""Tests for the AgentSession wrapper.

These tests mock the Anthropic SDK to test the session wrapper's behaviour
without making actual API calls.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from policy_factory.agent.config import AgentConfig
from policy_factory.agent.errors import AgentError, ContextOverflowError
from policy_factory.agent.session import (
    MAX_RETRIES,
    RETRY_BASE_DELAY,
    AgentResult,
    AgentSession,
    _is_transient_error,
)
from policy_factory.events import AgentTextChunk, EventEmitter


# ---------------------------------------------------------------------------
# Mock helpers for Anthropic SDK streaming
# ---------------------------------------------------------------------------


@dataclass
class MockTextBlock:
    """Mock for anthropic text content block."""

    type: str = "text"
    text: str = ""


@dataclass
class MockToolUseBlock:
    """Mock for anthropic tool_use content block."""

    type: str = "tool_use"
    id: str = "tool_123"
    name: str = ""
    input: dict[str, Any] = field(default_factory=dict)


@dataclass
class MockTextDelta:
    """Mock for text delta in streaming."""

    type: str = "text_delta"
    text: str = ""


@dataclass
class MockInputJsonDelta:
    """Mock for input JSON delta in streaming."""

    type: str = "input_json_delta"
    partial_json: str = ""


@dataclass
class MockMessageDelta:
    """Mock for message delta with stop reason."""

    stop_reason: str | None = None


@dataclass
class MockUsage:
    """Mock for usage statistics."""

    input_tokens: int = 100
    output_tokens: int = 50


@dataclass
class MockFinalMessage:
    """Mock for the final message with usage stats."""

    usage: MockUsage = field(default_factory=MockUsage)


class MockStreamEvent:
    """Generic mock stream event."""

    def __init__(
        self,
        event_type: str,
        content_block: Any = None,
        delta: Any = None,
        index: int = 0,
    ) -> None:
        self.type = event_type
        self.content_block = content_block
        self.delta = delta
        self.index = index


def create_text_stream_events(text: str, stop_reason: str = "end_turn") -> list[MockStreamEvent]:
    """Create stream events for a simple text response.

    Args:
        text: The text to stream.
        stop_reason: The stop reason for the message.

    Returns:
        List of mock stream events simulating a text response.
    """
    events = [
        MockStreamEvent("content_block_start", content_block=MockTextBlock(text="")),
        MockStreamEvent("content_block_delta", delta=MockTextDelta(text=text)),
        MockStreamEvent("content_block_stop"),
        MockStreamEvent("message_delta", delta=MockMessageDelta(stop_reason=stop_reason)),
    ]
    return events


def create_tool_use_stream_events(
    tool_id: str,
    tool_name: str,
    tool_input: dict[str, Any],
    text_before: str = "",
    stop_reason: str = "tool_use",
) -> list[MockStreamEvent]:
    """Create stream events for a tool use response.

    Args:
        tool_id: The tool use block ID.
        tool_name: Name of the tool being called.
        tool_input: Input parameters for the tool.
        text_before: Optional text to stream before tool use.
        stop_reason: The stop reason for the message.

    Returns:
        List of mock stream events simulating a tool use response.
    """
    events = []

    # Optional text block before tool use
    if text_before:
        events.extend([
            MockStreamEvent("content_block_start", content_block=MockTextBlock(text="")),
            MockStreamEvent("content_block_delta", delta=MockTextDelta(text=text_before)),
            MockStreamEvent("content_block_stop"),
        ])

    # Tool use block
    events.extend([
        MockStreamEvent(
            "content_block_start",
            content_block=MockToolUseBlock(type="tool_use", id=tool_id, name=tool_name),
        ),
        MockStreamEvent(
            "content_block_delta",
            delta=MockInputJsonDelta(partial_json=json.dumps(tool_input)),
        ),
        MockStreamEvent("content_block_stop"),
        MockStreamEvent("message_delta", delta=MockMessageDelta(stop_reason=stop_reason)),
    ])

    return events


class MockStreamContextManager:
    """Mock async context manager for Anthropic streaming responses."""

    def __init__(
        self,
        events: list[MockStreamEvent],
        final_message: MockFinalMessage | None = None,
    ) -> None:
        self._events = events
        self._final_message = final_message or MockFinalMessage()

    async def __aenter__(self) -> MockStreamContextManager:
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass

    async def __aiter__(self):
        for event in self._events:
            yield event

    async def get_final_message(self) -> MockFinalMessage:
        return self._final_message


def create_mock_anthropic_client(
    stream_responses: list[list[MockStreamEvent]] | None = None,
    final_messages: list[MockFinalMessage] | None = None,
) -> MagicMock:
    """Create a mock AsyncAnthropic client.

    Args:
        stream_responses: List of event lists, one per API call.
        final_messages: List of final messages, one per API call.

    Returns:
        Mock client with messages.stream() configured.
    """
    if stream_responses is None:
        stream_responses = [create_text_stream_events("Default response")]

    if final_messages is None:
        final_messages = [MockFinalMessage() for _ in stream_responses]

    call_count = 0

    def make_stream(**kwargs: Any) -> MockStreamContextManager:
        nonlocal call_count
        events = stream_responses[min(call_count, len(stream_responses) - 1)]
        final_msg = final_messages[min(call_count, len(final_messages) - 1)]
        call_count += 1
        return MockStreamContextManager(events, final_msg)

    mock_client = MagicMock()
    mock_client.messages.stream = MagicMock(side_effect=make_stream)

    return mock_client


# ---------------------------------------------------------------------------
# _is_transient_error tests
# ---------------------------------------------------------------------------


class TestIsTransientError:
    """Tests for the transient error classification function."""

    def test_500_internal_server_error_is_transient(self) -> None:
        assert _is_transient_error(Exception("500 internal server error")) is True

    def test_500_api_error_is_transient(self) -> None:
        assert _is_transient_error(Exception("500 api_error")) is True

    def test_502_is_transient(self) -> None:
        assert _is_transient_error(Exception("502 bad gateway")) is True

    def test_503_is_transient(self) -> None:
        assert _is_transient_error(Exception("503 service unavailable")) is True

    def test_529_is_transient(self) -> None:
        assert _is_transient_error(Exception("529 overloaded")) is True

    def test_overloaded_message_is_transient(self) -> None:
        assert _is_transient_error(Exception("API is overloaded")) is True

    def test_rate_limit_message_is_transient(self) -> None:
        assert _is_transient_error(Exception("rate limit exceeded")) is True

    def test_auth_failure_is_not_transient(self) -> None:
        assert _is_transient_error(Exception("authentication failed")) is False

    def test_context_overflow_is_not_transient(self) -> None:
        assert _is_transient_error(Exception("prompt is too long")) is False

    def test_generic_error_is_not_transient(self) -> None:
        assert _is_transient_error(Exception("something went wrong")) is False

    def test_404_is_not_transient(self) -> None:
        assert _is_transient_error(Exception("404 not found")) is False

    def test_bare_500_without_context_is_not_transient(self) -> None:
        # "500" alone without "internal server error" or "api_error" is not transient
        assert _is_transient_error(Exception("error code 500")) is False

    def test_rate_limit_error_type_is_transient(self) -> None:
        """RateLimitError exception type should be transient."""

        class RateLimitError(Exception):
            pass

        assert _is_transient_error(RateLimitError("Too many requests")) is True

    def test_overloaded_error_type_is_transient(self) -> None:
        """OverloadedError exception type should be transient."""

        class OverloadedError(Exception):
            pass

        assert _is_transient_error(OverloadedError("Server busy")) is True

    def test_authentication_error_type_is_not_transient(self) -> None:
        """AuthenticationError exception type should not be transient."""

        class AuthenticationError(Exception):
            pass

        assert _is_transient_error(AuthenticationError("Invalid key")) is False

    def test_error_with_status_code_429_is_transient(self) -> None:
        """Exception with status_code attribute 429 should be transient."""
        exc = Exception("Rate limited")
        exc.status_code = 429  # type: ignore[attr-defined]
        assert _is_transient_error(exc) is True

    def test_error_with_status_code_500_is_transient(self) -> None:
        """Exception with status_code attribute 500 should be transient."""
        exc = Exception("Server error")
        exc.status_code = 500  # type: ignore[attr-defined]
        assert _is_transient_error(exc) is True


# ---------------------------------------------------------------------------
# AgentResult tests
# ---------------------------------------------------------------------------


class TestAgentResult:
    """Tests for the AgentResult dataclass."""

    def test_default_values(self) -> None:
        result = AgentResult()
        assert result.is_error is False
        assert result.result_text == ""
        assert result.total_cost_usd is None
        assert result.num_turns is None
        assert result.full_output == ""

    def test_custom_values(self) -> None:
        result = AgentResult(
            is_error=True,
            result_text="error occurred",
            total_cost_usd=0.05,
            num_turns=3,
            full_output="full output here",
        )
        assert result.is_error is True
        assert result.result_text == "error occurred"
        assert result.total_cost_usd == 0.05
        assert result.num_turns == 3
        assert result.full_output == "full output here"


# ---------------------------------------------------------------------------
# AgentSession tests (with mocked Anthropic SDK)
# ---------------------------------------------------------------------------


class TestAgentSessionInit:
    """Tests for AgentSession initialization."""

    def test_accepts_config_and_emitter(self) -> None:
        config = AgentConfig()
        emitter = EventEmitter()
        mock_client = create_mock_anthropic_client()
        session = AgentSession(
            config, emitter, context_id="ctx-1", agent_label="Test", client=mock_client
        )
        assert session._config is config
        assert session._emitter is emitter
        assert session._context_id == "ctx-1"
        assert session._agent_label == "Test"
        assert session._client is mock_client

    def test_default_context_id_and_label(self) -> None:
        config = AgentConfig()
        emitter = EventEmitter()
        session = AgentSession(config, emitter)
        assert session._context_id == ""
        assert session._agent_label == ""


class TestAgentSessionRun:
    """Tests for AgentSession.run() with mocked Anthropic SDK."""

    @pytest.mark.asyncio
    async def test_single_turn_returns_agent_result(self) -> None:
        """Simulate a successful single-turn agent run (no tool calls)."""
        config = AgentConfig()
        emitter = EventEmitter()

        # Create mock client with simple text response
        events = create_text_stream_events("Analysis complete. No issues found.")
        mock_client = create_mock_anthropic_client([events])

        session = AgentSession(
            config, emitter, agent_label="Test agent", client=mock_client
        )
        result = await session.run("test prompt")

        assert isinstance(result, AgentResult)
        assert result.is_error is False
        assert "Analysis complete" in result.result_text
        assert "Analysis complete" in result.full_output
        assert result.num_turns == 1

    @pytest.mark.asyncio
    async def test_multi_turn_with_tool_calls(self, tmp_path: Path) -> None:
        """Verify multi-turn conversation with tool calls works correctly."""
        config = AgentConfig()
        emitter = EventEmitter()

        # First turn: model requests a tool
        tool_events = create_tool_use_stream_events(
            tool_id="tool_abc123",
            tool_name="list_files",
            tool_input={"path": "values"},
            text_before="Let me check the files. ",
            stop_reason="tool_use",
        )

        # Second turn: model responds with final answer after tool result
        final_events = create_text_stream_events(
            "Found 2 files in the values directory.", stop_reason="end_turn"
        )

        mock_client = create_mock_anthropic_client([tool_events, final_events])

        # Create a data directory with some files
        data_dir = tmp_path / "data"
        values_dir = data_dir / "values"
        values_dir.mkdir(parents=True)
        (values_dir / "value1.md").write_text("# Value 1")
        (values_dir / "value2.md").write_text("# Value 2")

        session = AgentSession(
            config, emitter, agent_label="Test", client=mock_client, data_dir=data_dir
        )
        result = await session.run("List the values files")

        assert isinstance(result, AgentResult)
        assert result.is_error is False
        assert result.num_turns == 2
        assert "Let me check the files" in result.full_output
        assert "Found 2 files" in result.full_output

        # Verify API was called twice (once per turn)
        assert mock_client.messages.stream.call_count == 2

    @pytest.mark.asyncio
    async def test_run_emits_text_chunk_events(self) -> None:
        """Verify that text chunks are emitted via EventEmitter."""
        config = AgentConfig()
        emitter = EventEmitter()
        received_events: list[AgentTextChunk] = []

        async def handler(event: Any) -> None:
            if isinstance(event, AgentTextChunk):
                received_events.append(event)

        emitter.subscribe(handler)

        # Create response with enough text to trigger streaming
        # The meditation filter needs 500+ chars before it starts streaming
        long_text = "Analysis content here. " * 30  # ~720 chars
        events = create_text_stream_events(long_text)
        mock_client = create_mock_anthropic_client([events])

        session = AgentSession(
            config,
            emitter,
            context_id="cascade-1",
            agent_label="Values gen",
            client=mock_client,
        )
        await session.run("test prompt")

        assert len(received_events) > 0
        assert received_events[0].cascade_id == "cascade-1"
        assert received_events[0].agent_label == "Values gen"

    @pytest.mark.asyncio
    async def test_run_captures_full_output_including_meditation(self) -> None:
        """Full output should include all text, even meditation content."""
        config = AgentConfig()
        emitter = EventEmitter()

        # Simulate meditation countdown pattern
        meditation_text = "10. I notice my initial assumptions. "
        regular_text = "Now for the actual analysis."

        # Create events for meditation + regular text in sequence
        events = [
            MockStreamEvent("content_block_start", content_block=MockTextBlock(text="")),
            MockStreamEvent("content_block_delta", delta=MockTextDelta(text=meditation_text)),
            MockStreamEvent("content_block_delta", delta=MockTextDelta(text=regular_text)),
            MockStreamEvent("content_block_stop"),
            MockStreamEvent("message_delta", delta=MockMessageDelta(stop_reason="end_turn")),
        ]
        mock_client = create_mock_anthropic_client([events])

        session = AgentSession(config, emitter, client=mock_client)
        result = await session.run("test prompt")

        # Full output should contain both meditation and regular text
        assert "10. I notice my initial assumptions" in result.full_output
        assert "actual analysis" in result.full_output

    @pytest.mark.asyncio
    async def test_meditation_content_filtered_from_events(self) -> None:
        """Meditation content should be filtered from emitted events."""
        config = AgentConfig()
        emitter = EventEmitter()
        received_chunks: list[str] = []

        async def handler(event: Any) -> None:
            if isinstance(event, AgentTextChunk):
                received_chunks.append(event.text)

        emitter.subscribe(handler)

        # Create meditation countdown pattern followed by regular text
        # The filter looks for "10." pattern at start
        meditation_events = [
            MockStreamEvent("content_block_start", content_block=MockTextBlock(text="")),
            MockStreamEvent(
                "content_block_delta", delta=MockTextDelta(text="10. I observe ")
            ),
            MockStreamEvent(
                "content_block_delta", delta=MockTextDelta(text="9. I notice ")
            ),
            MockStreamEvent(
                "content_block_delta", delta=MockTextDelta(text="8. I see ")
            ),
            MockStreamEvent("content_block_delta", delta=MockTextDelta(text="7. ")),
            MockStreamEvent("content_block_delta", delta=MockTextDelta(text="6. ")),
            MockStreamEvent("content_block_delta", delta=MockTextDelta(text="5. ")),
            MockStreamEvent("content_block_delta", delta=MockTextDelta(text="4. ")),
            MockStreamEvent("content_block_delta", delta=MockTextDelta(text="3. ")),
            MockStreamEvent("content_block_delta", delta=MockTextDelta(text="2. ")),
            MockStreamEvent(
                "content_block_delta", delta=MockTextDelta(text="1.\n")
            ),
            # After "1." the filter should start streaming
            MockStreamEvent(
                "content_block_delta",
                delta=MockTextDelta(text="Now for the actual content."),
            ),
            MockStreamEvent("content_block_stop"),
            MockStreamEvent("message_delta", delta=MockMessageDelta(stop_reason="end_turn")),
        ]
        mock_client = create_mock_anthropic_client([meditation_events])

        session = AgentSession(config, emitter, client=mock_client)
        result = await session.run("test")

        # Full output contains everything
        assert "10. I observe" in result.full_output
        assert "actual content" in result.full_output

        # Emitted chunks should NOT contain meditation numbers
        emitted_text = "".join(received_chunks)
        # After filtering, only post-meditation content should be in emitted chunks
        # The meditation content (10. through 1.) should be suppressed
        assert "10. I observe" not in emitted_text


class TestAgentSessionToolExecution:
    """Tests for tool execution during agent sessions."""

    @pytest.mark.asyncio
    async def test_tool_results_passed_back_to_model(self, tmp_path: Path) -> None:
        """Verify tool results are correctly formatted and passed back."""
        config = AgentConfig()
        emitter = EventEmitter()

        # Create data directory with a file
        data_dir = tmp_path / "data"
        values_dir = data_dir / "values"
        values_dir.mkdir(parents=True)
        (values_dir / "test.md").write_text("# Test\n\nContent here.")

        # First turn: model calls read_file
        tool_events = create_tool_use_stream_events(
            tool_id="tool_read_123",
            tool_name="read_file",
            tool_input={"path": "values/test.md"},
            stop_reason="tool_use",
        )

        # Second turn: model responds after seeing tool result
        final_events = create_text_stream_events(
            "The file contains test content.", stop_reason="end_turn"
        )

        mock_client = create_mock_anthropic_client([tool_events, final_events])

        session = AgentSession(
            config, emitter, client=mock_client, data_dir=data_dir
        )
        result = await session.run("Read the test file")

        # Verify the API was called twice (once per turn)
        calls = mock_client.messages.stream.call_args_list
        assert len(calls) == 2

        # Check second call has tool result in messages
        second_call_kwargs = calls[1][1]
        messages = second_call_kwargs["messages"]

        # Messages should have at least: user prompt, assistant (tool_use), user (tool_result)
        # Note: The messages list may be mutated after the call, so we check minimum length
        assert len(messages) >= 3
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"
        assert messages[2]["role"] == "user"

        # The tool result should be in the third message (user with tool_result)
        tool_result_content = messages[2]["content"]
        assert len(tool_result_content) == 1
        assert tool_result_content[0]["type"] == "tool_result"
        assert tool_result_content[0]["tool_use_id"] == "tool_read_123"

        # Verify the tool result contains the file content
        result_data = json.loads(tool_result_content[0]["content"])
        assert result_data["success"] is True
        assert "Content here" in result_data["data"]

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error_to_model(self) -> None:
        """Unknown tool names should return error result to model."""
        config = AgentConfig()
        emitter = EventEmitter()

        # Model calls an unknown tool
        tool_events = create_tool_use_stream_events(
            tool_id="tool_unknown_123",
            tool_name="unknown_tool_xyz",
            tool_input={"foo": "bar"},
            stop_reason="tool_use",
        )

        # Model responds after seeing error
        final_events = create_text_stream_events(
            "I encountered an error with that tool.", stop_reason="end_turn"
        )

        mock_client = create_mock_anthropic_client([tool_events, final_events])

        session = AgentSession(config, emitter, client=mock_client)
        result = await session.run("Do something")

        # Verify the tool result contained an error
        calls = mock_client.messages.stream.call_args_list
        second_call_kwargs = calls[1][1]
        messages = second_call_kwargs["messages"]

        tool_result_content = messages[2]["content"][0]["content"]
        result_data = json.loads(tool_result_content)
        assert "error" in result_data
        assert "Unknown tool" in result_data["error"]

    @pytest.mark.asyncio
    async def test_write_file_tool_creates_file(self, tmp_path: Path) -> None:
        """Verify write_file tool creates files correctly."""
        config = AgentConfig()
        emitter = EventEmitter()

        data_dir = tmp_path / "data"
        values_dir = data_dir / "values"
        values_dir.mkdir(parents=True)

        # Model calls write_file
        tool_events = create_tool_use_stream_events(
            tool_id="tool_write_123",
            tool_name="write_file",
            tool_input={
                "path": "values/new-item.md",
                "content": "---\ntitle: New Item\n---\n\nContent here.",
            },
            stop_reason="tool_use",
        )

        final_events = create_text_stream_events(
            "File created successfully.", stop_reason="end_turn"
        )

        mock_client = create_mock_anthropic_client([tool_events, final_events])

        session = AgentSession(
            config, emitter, client=mock_client, data_dir=data_dir
        )
        await session.run("Create a new file")

        # Verify file was created
        created_file = values_dir / "new-item.md"
        assert created_file.exists()
        content = created_file.read_text()
        assert "title: New Item" in content

    @pytest.mark.asyncio
    async def test_delete_file_tool_removes_file(self, tmp_path: Path) -> None:
        """Verify delete_file tool removes files correctly."""
        config = AgentConfig()
        emitter = EventEmitter()

        data_dir = tmp_path / "data"
        values_dir = data_dir / "values"
        values_dir.mkdir(parents=True)
        file_to_delete = values_dir / "to-delete.md"
        file_to_delete.write_text("# To Delete")

        assert file_to_delete.exists()

        # Model calls delete_file
        tool_events = create_tool_use_stream_events(
            tool_id="tool_del_123",
            tool_name="delete_file",
            tool_input={"path": "values/to-delete.md"},
            stop_reason="tool_use",
        )

        final_events = create_text_stream_events(
            "File deleted.", stop_reason="end_turn"
        )

        mock_client = create_mock_anthropic_client([tool_events, final_events])

        session = AgentSession(
            config, emitter, client=mock_client, data_dir=data_dir
        )
        await session.run("Delete the file")

        # Verify file was deleted
        assert not file_to_delete.exists()


class TestAgentSessionRetry:
    """Tests for retry logic."""

    @pytest.mark.asyncio
    async def test_retries_on_transient_error(self) -> None:
        """Transient errors should trigger retries with backoff."""
        config = AgentConfig()
        emitter = EventEmitter()
        mock_client = create_mock_anthropic_client()
        session = AgentSession(config, emitter, client=mock_client)

        call_count = 0

        async def mock_run_once(prompt: str) -> AgentResult:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("503 service unavailable")
            return AgentResult(result_text="Success on attempt 3")

        with patch.object(session, "_run_once", side_effect=mock_run_once):
            with patch("policy_factory.agent.session.asyncio.sleep", new_callable=AsyncMock):
                result = await session.run("test")

        assert call_count == 3
        assert result.result_text == "Success on attempt 3"

    @pytest.mark.asyncio
    async def test_no_retry_on_context_overflow(self) -> None:
        """ContextOverflowError should NOT be retried."""
        config = AgentConfig()
        emitter = EventEmitter()
        mock_client = create_mock_anthropic_client()
        session = AgentSession(config, emitter, client=mock_client)

        call_count = 0

        async def mock_run_once(prompt: str) -> AgentResult:
            nonlocal call_count
            call_count += 1
            raise ContextOverflowError("prompt is too long")

        with patch.object(session, "_run_once", side_effect=mock_run_once):
            with pytest.raises(ContextOverflowError):
                await session.run("test")

        assert call_count == 1  # No retries

    @pytest.mark.asyncio
    async def test_no_retry_on_auth_error(self) -> None:
        """Authentication errors should NOT be retried."""
        config = AgentConfig()
        emitter = EventEmitter()
        mock_client = create_mock_anthropic_client()
        session = AgentSession(config, emitter, client=mock_client)

        call_count = 0

        async def mock_run_once(prompt: str) -> AgentResult:
            nonlocal call_count
            call_count += 1
            raise Exception("authentication failed: invalid token")

        with patch.object(session, "_run_once", side_effect=mock_run_once):
            with pytest.raises(AgentError, match="Authentication failed"):
                await session.run("test")

        assert call_count == 1  # No retries

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self) -> None:
        """After MAX_RETRIES attempts, the error should propagate."""
        config = AgentConfig()
        emitter = EventEmitter()
        mock_client = create_mock_anthropic_client()
        session = AgentSession(config, emitter, client=mock_client)

        call_count = 0

        async def mock_run_once(prompt: str) -> AgentResult:
            nonlocal call_count
            call_count += 1
            raise Exception("503 service unavailable")

        with patch.object(session, "_run_once", side_effect=mock_run_once):
            with patch("policy_factory.agent.session.asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(AgentError, match="failed after"):
                    await session.run("test")

        assert call_count == MAX_RETRIES

    @pytest.mark.asyncio
    async def test_exponential_backoff_delays(self) -> None:
        """Verify exponential backoff delays between retries."""
        config = AgentConfig()
        emitter = EventEmitter()
        mock_client = create_mock_anthropic_client()
        session = AgentSession(config, emitter, client=mock_client)

        sleep_calls: list[float] = []

        async def mock_sleep(delay: float) -> None:
            sleep_calls.append(delay)

        call_count = 0

        async def mock_run_once(prompt: str) -> AgentResult:
            nonlocal call_count
            call_count += 1
            raise Exception("502 bad gateway")

        with patch.object(session, "_run_once", side_effect=mock_run_once):
            with patch("policy_factory.agent.session.asyncio.sleep", side_effect=mock_sleep):
                with pytest.raises(AgentError):
                    await session.run("test")

        # Should have MAX_RETRIES - 1 sleep calls (no sleep after last attempt)
        assert len(sleep_calls) == MAX_RETRIES - 1
        # Verify exponential backoff: 2, 4
        assert sleep_calls[0] == RETRY_BASE_DELAY
        assert sleep_calls[1] == RETRY_BASE_DELAY * 2

    @pytest.mark.asyncio
    async def test_rate_limit_error_triggers_retry(self) -> None:
        """Rate limit errors (429) should trigger retries."""
        config = AgentConfig()
        emitter = EventEmitter()
        mock_client = create_mock_anthropic_client()
        session = AgentSession(config, emitter, client=mock_client)

        call_count = 0

        async def mock_run_once(prompt: str) -> AgentResult:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                exc = Exception("Rate limit exceeded")
                exc.status_code = 429  # type: ignore[attr-defined]
                raise exc
            return AgentResult(result_text="Success after rate limit")

        with patch.object(session, "_run_once", side_effect=mock_run_once):
            with patch("policy_factory.agent.session.asyncio.sleep", new_callable=AsyncMock):
                result = await session.run("test")

        assert call_count == 2
        assert result.result_text == "Success after rate limit"

    @pytest.mark.asyncio
    async def test_server_error_triggers_retry(self) -> None:
        """Server errors (500, 502, 503) should trigger retries."""
        config = AgentConfig()
        emitter = EventEmitter()
        mock_client = create_mock_anthropic_client()
        session = AgentSession(config, emitter, client=mock_client)

        call_count = 0

        async def mock_run_once(prompt: str) -> AgentResult:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("500 internal server error")
            return AgentResult(result_text="Success after server error")

        with patch.object(session, "_run_once", side_effect=mock_run_once):
            with patch("policy_factory.agent.session.asyncio.sleep", new_callable=AsyncMock):
                result = await session.run("test")

        assert call_count == 2
        assert result.result_text == "Success after server error"


class TestAgentSessionConfig:
    """Tests for session config handling."""

    @pytest.mark.asyncio
    async def test_config_model_passed_to_api(self) -> None:
        """Verify that the model from config is passed to API call."""
        config = AgentConfig(model="claude-opus-4-20250514")
        emitter = EventEmitter()
        mock_client = create_mock_anthropic_client()

        session = AgentSession(config, emitter, client=mock_client)
        await session.run("test")

        # Check the API call included the model
        call_kwargs = mock_client.messages.stream.call_args[1]
        assert call_kwargs["model"] == "claude-opus-4-20250514"

    @pytest.mark.asyncio
    async def test_system_prompt_passed_to_api(self) -> None:
        """Verify that system prompt is passed to API call when configured."""
        config = AgentConfig(system_prompt="You are a helpful assistant.")
        emitter = EventEmitter()
        mock_client = create_mock_anthropic_client()

        session = AgentSession(config, emitter, client=mock_client)
        await session.run("test")

        call_kwargs = mock_client.messages.stream.call_args[1]
        assert call_kwargs["system"] == "You are a helpful assistant."

    @pytest.mark.asyncio
    async def test_tools_passed_to_api_when_configured(self) -> None:
        """Verify that tools are passed to API call when configured."""
        # Create config with tools
        from policy_factory.agent.tools import FILE_TOOLS

        config = AgentConfig(tools=FILE_TOOLS)
        emitter = EventEmitter()
        mock_client = create_mock_anthropic_client()

        session = AgentSession(config, emitter, client=mock_client)
        await session.run("test")

        call_kwargs = mock_client.messages.stream.call_args[1]
        assert "tools" in call_kwargs
        assert len(call_kwargs["tools"]) > 0

    @pytest.mark.asyncio
    async def test_no_tools_when_empty_config(self) -> None:
        """Verify that tools are not passed when config has empty tools list."""
        config = AgentConfig(tools=[])
        emitter = EventEmitter()
        mock_client = create_mock_anthropic_client()

        session = AgentSession(config, emitter, client=mock_client)
        await session.run("test")

        call_kwargs = mock_client.messages.stream.call_args[1]
        assert "tools" not in call_kwargs

    @pytest.mark.asyncio
    async def test_default_model_used_when_not_configured(self) -> None:
        """Verify default model is used when config doesn't specify one."""
        config = AgentConfig(model=None)
        emitter = EventEmitter()
        mock_client = create_mock_anthropic_client()

        session = AgentSession(config, emitter, client=mock_client)
        await session.run("test")

        call_kwargs = mock_client.messages.stream.call_args[1]
        assert call_kwargs["model"] == "claude-sonnet-4-20250514"


class TestAgentSessionContextOverflow:
    """Tests for context overflow error handling."""

    @pytest.mark.asyncio
    async def test_context_overflow_raises_error(self) -> None:
        """Context overflow should raise ContextOverflowError."""
        config = AgentConfig()
        emitter = EventEmitter()
        mock_client = create_mock_anthropic_client()
        session = AgentSession(config, emitter, client=mock_client)

        async def mock_run_once(prompt: str) -> AgentResult:
            raise Exception("context_length_exceeded: prompt too long")

        with patch.object(session, "_run_once", side_effect=mock_run_once):
            with pytest.raises(ContextOverflowError, match="context_length_exceeded"):
                await session.run("test")

    @pytest.mark.asyncio
    async def test_prompt_too_long_raises_context_overflow(self) -> None:
        """'prompt is too long' error should raise ContextOverflowError."""
        config = AgentConfig()
        emitter = EventEmitter()
        mock_client = create_mock_anthropic_client()
        session = AgentSession(config, emitter, client=mock_client)

        async def mock_run_once(prompt: str) -> AgentResult:
            raise Exception("Error: prompt is too long for model")

        with patch.object(session, "_run_once", side_effect=mock_run_once):
            with pytest.raises(ContextOverflowError, match="prompt is too long"):
                await session.run("test")

    @pytest.mark.asyncio
    async def test_too_many_tokens_raises_context_overflow(self) -> None:
        """'too many tokens' error should raise ContextOverflowError."""
        config = AgentConfig()
        emitter = EventEmitter()
        mock_client = create_mock_anthropic_client()
        session = AgentSession(config, emitter, client=mock_client)

        async def mock_run_once(prompt: str) -> AgentResult:
            raise Exception("Request has too many tokens")

        with patch.object(session, "_run_once", side_effect=mock_run_once):
            with pytest.raises(ContextOverflowError, match="too many tokens"):
                await session.run("test")


class TestAgentSessionEndTurn:
    """Tests for conversation termination on end_turn."""

    @pytest.mark.asyncio
    async def test_terminates_on_end_turn_without_tool_calls(self) -> None:
        """Conversation should terminate when model signals end_turn without tool calls."""
        config = AgentConfig()
        emitter = EventEmitter()

        events = create_text_stream_events(
            "Final response.", stop_reason="end_turn"
        )
        mock_client = create_mock_anthropic_client([events])

        session = AgentSession(config, emitter, client=mock_client)
        result = await session.run("test")

        # Should only make one API call
        assert mock_client.messages.stream.call_count == 1
        assert result.num_turns == 1

    @pytest.mark.asyncio
    async def test_terminates_on_end_turn_even_with_tool_calls(self) -> None:
        """If stop_reason is end_turn, should terminate even if there were tool calls."""
        config = AgentConfig()
        emitter = EventEmitter()

        # This simulates a case where the model made a tool call but also signals end_turn
        # In practice this shouldn't happen, but the code should handle it gracefully
        tool_events = create_tool_use_stream_events(
            tool_id="tool_123",
            tool_name="list_files",
            tool_input={"path": "values"},
            stop_reason="end_turn",  # end_turn despite tool call
        )
        mock_client = create_mock_anthropic_client([tool_events])

        session = AgentSession(config, emitter, client=mock_client)
        result = await session.run("test")

        # Should terminate after first turn due to end_turn stop reason
        assert mock_client.messages.stream.call_count == 1
        assert result.num_turns == 1
