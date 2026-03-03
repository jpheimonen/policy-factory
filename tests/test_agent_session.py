"""Tests for the AgentSession wrapper (ClaudeSDKClient-based).

These tests mock the ``ClaudeSDKClient`` lifecycle to test the session
wrapper's behaviour without spawning real CLI processes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from claude_agent_sdk._errors import CLIConnectionError, MessageParseError

from policy_factory.agent.config import AgentConfig
from policy_factory.agent.errors import AgentError, ContextOverflowError
from policy_factory.agent.session import (
    MAX_RETRIES,
    RETRY_BASE_DELAY,
    AgentResult,
    AgentSession,
    _is_context_overflow,
    _is_transient_error,
)
from policy_factory.events import AgentTextChunk, EventEmitter

# ---------------------------------------------------------------------------
# Mock helpers for ClaudeSDKClient messages
# ---------------------------------------------------------------------------


class _MockTextBlock:
    """Simulates a text block inside an AssistantMessage."""

    def __init__(self, text: str) -> None:
        self.text = text


class _MockToolUseBlock:
    """Simulates a tool_use block inside an AssistantMessage (no text attr)."""

    def __init__(self, name: str) -> None:
        self.name = name


class MockAssistantMessage:
    """Simulates an ``AssistantMessage`` from the SDK.

    The class is named so that ``type(msg).__name__ == "MockAssistantMessage"``
    but the session code checks for ``"AssistantMessage"`` via duck-typing
    on ``hasattr(message, "content")``.  We also give the mock class
    the right ``__name__`` by subclassing a dynamically-created type so
    that ``type(msg).__name__`` returns ``"AssistantMessage"``.

    For simplicity we just set the ``content`` attribute and let the session
    code use ``hasattr(message, "content")`` together with
    ``type(message).__name__ == "AssistantMessage"``.  To make the name check
    work we use a dynamic metaclass trick.
    """

    def __init__(
        self,
        text_blocks: list[str] | None = None,
        tool_blocks: list[str] | None = None,
    ) -> None:
        blocks: list[Any] = []
        for text in (text_blocks or []):
            blocks.append(_MockTextBlock(text))
        for name in (tool_blocks or []):
            blocks.append(_MockToolUseBlock(name))
        self.content = blocks


# Make type(msg).__name__ return "AssistantMessage" for duck-typed detection
MockAssistantMessage.__name__ = "AssistantMessage"  # type: ignore[attr-defined]
MockAssistantMessage.__qualname__ = "AssistantMessage"  # type: ignore[attr-defined]


class MockResultMessage:
    """Simulates a ``ResultMessage`` from the SDK.

    The session detects this via ``hasattr(message, "is_error")``.
    """

    def __init__(
        self,
        is_error: bool = False,
        result: str | None = None,
        total_cost_usd: float | None = None,
        num_turns: int | None = None,
        session_id: str | None = None,
    ) -> None:
        self.is_error = is_error
        self.result = result
        self.total_cost_usd = total_cost_usd
        self.num_turns = num_turns
        self.session_id = session_id


async def async_messages(*messages: Any):
    """Async generator yielding mock messages to simulate ``receive_response()``."""
    for msg in messages:
        yield msg


def _make_mock_client(messages: list[Any]) -> MagicMock:
    """Create a mock ``ClaudeSDKClient`` that yields the given messages.

    Returns a mock whose constructor returns an async context manager.
    Inside that context manager, ``query()`` is a no-op and
    ``receive_response()`` yields the given messages.
    """
    mock_client_instance = AsyncMock()
    mock_client_instance.query = AsyncMock()
    mock_client_instance.receive_response = MagicMock(
        return_value=async_messages(*messages)
    )

    # Make the client work as an async context manager
    mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
    mock_client_instance.__aexit__ = AsyncMock(return_value=None)

    return mock_client_instance


# ---------------------------------------------------------------------------
# _is_transient_error tests
# ---------------------------------------------------------------------------


class TestIsTransientError:
    """Tests for the transient error classification function."""

    def test_cli_connection_error_is_transient(self) -> None:
        """CLIConnectionError should be transient."""
        assert _is_transient_error(CLIConnectionError("CLI died")) is True

    def test_message_parse_error_is_not_transient(self) -> None:
        """MessageParseError should NOT be transient."""
        assert _is_transient_error(MessageParseError("bad message")) is False

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

    def test_generic_error_is_not_transient(self) -> None:
        assert _is_transient_error(Exception("something went wrong")) is False

    def test_404_is_not_transient(self) -> None:
        assert _is_transient_error(Exception("404 not found")) is False

    def test_bare_500_without_context_is_not_transient(self) -> None:
        # "500" alone without "internal server error" or "api_error" is not transient
        assert _is_transient_error(Exception("error code 500")) is False

    def test_context_overflow_is_not_transient(self) -> None:
        """Context overflow strings are not transient (handled separately)."""
        assert _is_transient_error(Exception("prompt is too long")) is False

    def test_auth_failure_is_not_transient(self) -> None:
        """Auth strings are not transient (handled separately in run())."""
        assert _is_transient_error(Exception("authentication failed")) is False


# ---------------------------------------------------------------------------
# _is_context_overflow tests
# ---------------------------------------------------------------------------


class TestIsContextOverflow:
    """Tests for context overflow detection."""

    def test_prompt_too_long(self) -> None:
        assert _is_context_overflow(Exception("prompt is too long")) is True

    def test_context_length_exceeded(self) -> None:
        assert _is_context_overflow(Exception("context_length_exceeded")) is True

    def test_maximum_context_length(self) -> None:
        assert _is_context_overflow(Exception("maximum context length")) is True

    def test_too_many_tokens(self) -> None:
        assert _is_context_overflow(Exception("too many tokens")) is True

    def test_generic_error_is_not_overflow(self) -> None:
        assert _is_context_overflow(Exception("something went wrong")) is False


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
        assert result.session_id is None

    def test_custom_values(self) -> None:
        result = AgentResult(
            is_error=True,
            result_text="error occurred",
            total_cost_usd=0.05,
            num_turns=3,
            full_output="full output here",
            session_id="sess-123",
        )
        assert result.is_error is True
        assert result.result_text == "error occurred"
        assert result.total_cost_usd == 0.05
        assert result.num_turns == 3
        assert result.full_output == "full output here"
        assert result.session_id == "sess-123"


# ---------------------------------------------------------------------------
# AgentSession init tests
# ---------------------------------------------------------------------------


class TestAgentSessionInit:
    """Tests for AgentSession initialization."""

    def test_accepts_config_and_emitter(self) -> None:
        config = AgentConfig()
        emitter = EventEmitter()
        session = AgentSession(
            config, emitter, context_id="ctx-1", agent_label="Test"
        )
        assert session._config is config
        assert session._emitter is emitter
        assert session._context_id == "ctx-1"
        assert session._agent_label == "Test"

    def test_default_context_id_and_label(self) -> None:
        config = AgentConfig()
        emitter = EventEmitter()
        session = AgentSession(config, emitter)
        assert session._context_id == ""
        assert session._agent_label == ""

    def test_no_client_parameter(self) -> None:
        """AgentSession should not accept a ``client`` parameter."""
        import inspect

        sig = inspect.signature(AgentSession.__init__)
        param_names = list(sig.parameters.keys())
        assert "client" not in param_names

    def test_accepts_data_dir(self) -> None:
        config = AgentConfig()
        emitter = EventEmitter()
        data_dir = Path("/tmp/test-data")
        session = AgentSession(config, emitter, data_dir=data_dir)
        assert session._data_dir == data_dir

    def test_default_data_dir(self) -> None:
        config = AgentConfig()
        emitter = EventEmitter()
        session = AgentSession(config, emitter)
        assert session._data_dir == Path.cwd() / "data"


# ---------------------------------------------------------------------------
# AgentSession.run() tests — mocked ClaudeSDKClient
# ---------------------------------------------------------------------------


class TestAgentSessionRun:
    """Tests for AgentSession.run() with mocked ClaudeSDKClient."""

    @pytest.mark.asyncio
    async def test_single_turn_returns_agent_result(self) -> None:
        """Successful single-turn session returns a proper AgentResult."""
        config = AgentConfig()
        emitter = EventEmitter()
        session = AgentSession(config, emitter, agent_label="Test agent")

        messages = [
            MockAssistantMessage(text_blocks=["Analysis complete. No issues found."]),
            MockResultMessage(
                is_error=False,
                result="Analysis complete. No issues found.",
                total_cost_usd=0.01,
                num_turns=1,
                session_id="sess-abc",
            ),
        ]
        mock_client = _make_mock_client(messages)

        with patch("policy_factory.agent.session.ClaudeSDKClient", return_value=mock_client):
            result = await session.run("test prompt")

        assert isinstance(result, AgentResult)
        assert result.is_error is False
        assert "Analysis complete" in result.result_text
        assert "Analysis complete" in result.full_output
        assert result.num_turns == 1
        assert result.session_id == "sess-abc"
        assert result.total_cost_usd == 0.01

    @pytest.mark.asyncio
    async def test_text_event_emission(self) -> None:
        """Text blocks emit AgentTextChunk events with correct attributes."""
        config = AgentConfig()
        emitter = EventEmitter()
        received_events: list[AgentTextChunk] = []

        async def handler(event: Any) -> None:
            if isinstance(event, AgentTextChunk):
                received_events.append(event)

        emitter.subscribe(handler)

        messages = [
            MockAssistantMessage(text_blocks=["Here is the analysis."]),
            MockResultMessage(is_error=False, result="Done"),
        ]
        mock_client = _make_mock_client(messages)

        session = AgentSession(
            config,
            emitter,
            context_id="cascade-1",
            agent_label="Values gen",
        )

        with patch("policy_factory.agent.session.ClaudeSDKClient", return_value=mock_client):
            await session.run("test prompt")

        assert len(received_events) == 1
        assert received_events[0].cascade_id == "cascade-1"
        assert received_events[0].agent_label == "Values gen"
        assert received_events[0].text == "Here is the analysis."

    @pytest.mark.asyncio
    async def test_tool_use_blocks_do_not_emit_events(self) -> None:
        """Blocks without text (e.g., tool_use) should not emit AgentTextChunk."""
        config = AgentConfig()
        emitter = EventEmitter()
        received_events: list[AgentTextChunk] = []

        async def handler(event: Any) -> None:
            if isinstance(event, AgentTextChunk):
                received_events.append(event)

        emitter.subscribe(handler)

        messages = [
            MockAssistantMessage(text_blocks=[], tool_blocks=["list_files"]),
            MockAssistantMessage(text_blocks=["Final result."]),
            MockResultMessage(is_error=False, result="Done"),
        ]
        mock_client = _make_mock_client(messages)

        session = AgentSession(config, emitter)
        with patch("policy_factory.agent.session.ClaudeSDKClient", return_value=mock_client):
            await session.run("test")

        # Only one event from the text block, not from the tool use block
        assert len(received_events) == 1
        assert received_events[0].text == "Final result."

    @pytest.mark.asyncio
    async def test_empty_text_blocks_do_not_emit_events(self) -> None:
        """Empty or whitespace-only text blocks should not emit events."""
        config = AgentConfig()
        emitter = EventEmitter()
        received_events: list[AgentTextChunk] = []

        async def handler(event: Any) -> None:
            if isinstance(event, AgentTextChunk):
                received_events.append(event)

        emitter.subscribe(handler)

        messages = [
            MockAssistantMessage(text_blocks=["", "   ", "Real content."]),
            MockResultMessage(is_error=False),
        ]
        mock_client = _make_mock_client(messages)

        session = AgentSession(config, emitter)
        with patch("policy_factory.agent.session.ClaudeSDKClient", return_value=mock_client):
            await session.run("test")

        assert len(received_events) == 1
        assert received_events[0].text == "Real content."

    @pytest.mark.asyncio
    async def test_full_output_captures_all_text(self) -> None:
        """full_output should contain text from all AssistantMessage blocks."""
        config = AgentConfig()
        emitter = EventEmitter()

        messages = [
            MockAssistantMessage(text_blocks=["Turn 1 text."]),
            MockAssistantMessage(text_blocks=["Turn 2 text."]),
            MockResultMessage(is_error=False, result="Final result"),
        ]
        mock_client = _make_mock_client(messages)

        session = AgentSession(config, emitter)
        with patch("policy_factory.agent.session.ClaudeSDKClient", return_value=mock_client):
            result = await session.run("test")

        assert "Turn 1 text." in result.full_output
        assert "Turn 2 text." in result.full_output

    @pytest.mark.asyncio
    async def test_multi_turn_text_events(self) -> None:
        """Multiple AssistantMessages each emit their own AgentTextChunk."""
        config = AgentConfig()
        emitter = EventEmitter()
        received_events: list[AgentTextChunk] = []

        async def handler(event: Any) -> None:
            if isinstance(event, AgentTextChunk):
                received_events.append(event)

        emitter.subscribe(handler)

        messages = [
            MockAssistantMessage(text_blocks=["First turn."]),
            MockAssistantMessage(text_blocks=["Second turn."]),
            MockResultMessage(is_error=False),
        ]
        mock_client = _make_mock_client(messages)

        session = AgentSession(config, emitter)
        with patch("policy_factory.agent.session.ClaudeSDKClient", return_value=mock_client):
            await session.run("test")

        assert len(received_events) == 2
        assert received_events[0].text == "First turn."
        assert received_events[1].text == "Second turn."

    @pytest.mark.asyncio
    async def test_cost_from_result_message(self) -> None:
        """total_cost_usd should come from ResultMessage."""
        config = AgentConfig()
        emitter = EventEmitter()

        messages = [
            MockAssistantMessage(text_blocks=["Output."]),
            MockResultMessage(is_error=False, total_cost_usd=0.05),
        ]
        mock_client = _make_mock_client(messages)

        session = AgentSession(config, emitter)
        with patch("policy_factory.agent.session.ClaudeSDKClient", return_value=mock_client):
            result = await session.run("test")

        assert result.total_cost_usd == 0.05

    @pytest.mark.asyncio
    async def test_session_id_from_result_message(self) -> None:
        """session_id should come from ResultMessage."""
        config = AgentConfig()
        emitter = EventEmitter()

        messages = [
            MockAssistantMessage(text_blocks=["Output."]),
            MockResultMessage(is_error=False, session_id="sess-xyz-123"),
        ]
        mock_client = _make_mock_client(messages)

        session = AgentSession(config, emitter)
        with patch("policy_factory.agent.session.ClaudeSDKClient", return_value=mock_client):
            result = await session.run("test")

        assert result.session_id == "sess-xyz-123"

    @pytest.mark.asyncio
    async def test_error_result(self) -> None:
        """A ResultMessage with is_error=True produces an error AgentResult."""
        config = AgentConfig()
        emitter = EventEmitter()

        messages = [
            MockResultMessage(is_error=True, result="Something went wrong"),
        ]
        mock_client = _make_mock_client(messages)

        session = AgentSession(config, emitter)
        with patch("policy_factory.agent.session.ClaudeSDKClient", return_value=mock_client):
            result = await session.run("test")

        assert result.is_error is True
        assert result.result_text == "Something went wrong"

    @pytest.mark.asyncio
    async def test_result_text_falls_back_to_full_output(self) -> None:
        """When ResultMessage.result is None, result_text falls back to full_output."""
        config = AgentConfig()
        emitter = EventEmitter()

        messages = [
            MockAssistantMessage(text_blocks=["The actual text."]),
            MockResultMessage(is_error=False, result=None),
        ]
        mock_client = _make_mock_client(messages)

        session = AgentSession(config, emitter)
        with patch("policy_factory.agent.session.ClaudeSDKClient", return_value=mock_client):
            result = await session.run("test")

        assert result.result_text == "The actual text."

    @pytest.mark.asyncio
    async def test_sdk_client_lifecycle(self) -> None:
        """Verify ClaudeSDKClient is used as async context manager with query()."""
        config = AgentConfig()
        emitter = EventEmitter()

        messages = [
            MockAssistantMessage(text_blocks=["Output."]),
            MockResultMessage(is_error=False),
        ]
        mock_client = _make_mock_client(messages)

        session = AgentSession(config, emitter)
        with patch("policy_factory.agent.session.ClaudeSDKClient", return_value=mock_client):
            await session.run("my test prompt")

        # Client was used as context manager
        mock_client.__aenter__.assert_awaited_once()
        mock_client.__aexit__.assert_awaited_once()
        # query() was called with the prompt
        mock_client.query.assert_awaited_once_with("my test prompt")
        # receive_response() was called
        mock_client.receive_response.assert_called_once()


# ---------------------------------------------------------------------------
# Retry tests
# ---------------------------------------------------------------------------


class TestAgentSessionRetry:
    """Tests for retry logic."""

    @pytest.mark.asyncio
    async def test_retries_on_transient_error(self) -> None:
        """CLIConnectionError should trigger retries with eventual success."""
        config = AgentConfig()
        emitter = EventEmitter()
        session = AgentSession(config, emitter)

        call_count = 0
        success_messages = [
            MockAssistantMessage(text_blocks=["Success."]),
            MockResultMessage(is_error=False, result="Success on attempt 3"),
        ]

        def mock_client_factory(*args: Any, **kwargs: Any) -> MagicMock:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                # Simulate failure: the client context raises CLIConnectionError
                mock = AsyncMock()
                mock.__aenter__ = AsyncMock(side_effect=CLIConnectionError("CLI died"))
                mock.__aexit__ = AsyncMock(return_value=None)
                return mock
            return _make_mock_client(success_messages)

        with patch("policy_factory.agent.session.ClaudeSDKClient", side_effect=mock_client_factory):
            with patch("policy_factory.agent.session.asyncio.sleep", new_callable=AsyncMock):
                result = await session.run("test")

        assert call_count == 3
        assert result.result_text == "Success on attempt 3"

    @pytest.mark.asyncio
    async def test_no_retry_on_context_overflow_exception(self) -> None:
        """ContextOverflowError from exception should NOT be retried."""
        config = AgentConfig()
        emitter = EventEmitter()
        session = AgentSession(config, emitter)

        call_count = 0

        def mock_client_factory(*args: Any, **kwargs: Any) -> MagicMock:
            nonlocal call_count
            call_count += 1
            mock = AsyncMock()
            mock.__aenter__ = AsyncMock(
                side_effect=Exception("prompt is too long for this model")
            )
            mock.__aexit__ = AsyncMock(return_value=None)
            return mock

        with patch("policy_factory.agent.session.ClaudeSDKClient", side_effect=mock_client_factory):
            with pytest.raises(ContextOverflowError, match="prompt is too long"):
                await session.run("test")

        assert call_count == 1  # No retries

    @pytest.mark.asyncio
    async def test_no_retry_on_auth_error(self) -> None:
        """Auth errors should NOT be retried."""
        config = AgentConfig()
        emitter = EventEmitter()
        session = AgentSession(config, emitter)

        call_count = 0

        def mock_client_factory(*args: Any, **kwargs: Any) -> MagicMock:
            nonlocal call_count
            call_count += 1
            mock = AsyncMock()
            mock.__aenter__ = AsyncMock(
                side_effect=Exception("authentication failed: invalid token")
            )
            mock.__aexit__ = AsyncMock(return_value=None)
            return mock

        with patch("policy_factory.agent.session.ClaudeSDKClient", side_effect=mock_client_factory):
            with pytest.raises(AgentError, match="Authentication failed"):
                await session.run("test")

        assert call_count == 1  # No retries

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self) -> None:
        """After MAX_RETRIES attempts, AgentError should be raised."""
        config = AgentConfig()
        emitter = EventEmitter()
        session = AgentSession(config, emitter)

        call_count = 0

        def mock_client_factory(*args: Any, **kwargs: Any) -> MagicMock:
            nonlocal call_count
            call_count += 1
            mock = AsyncMock()
            mock.__aenter__ = AsyncMock(
                side_effect=CLIConnectionError("503 service unavailable")
            )
            mock.__aexit__ = AsyncMock(return_value=None)
            return mock

        with patch("policy_factory.agent.session.ClaudeSDKClient", side_effect=mock_client_factory):
            with patch("policy_factory.agent.session.asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(AgentError, match="failed after"):
                    await session.run("test")

        assert call_count == MAX_RETRIES

    @pytest.mark.asyncio
    async def test_exponential_backoff_delays(self) -> None:
        """Verify exponential backoff delays between retries."""
        config = AgentConfig()
        emitter = EventEmitter()
        session = AgentSession(config, emitter)

        sleep_calls: list[float] = []

        async def mock_sleep(delay: float) -> None:
            sleep_calls.append(delay)

        def mock_client_factory(*args: Any, **kwargs: Any) -> MagicMock:
            mock = AsyncMock()
            mock.__aenter__ = AsyncMock(
                side_effect=CLIConnectionError("502 bad gateway")
            )
            mock.__aexit__ = AsyncMock(return_value=None)
            return mock

        with patch("policy_factory.agent.session.ClaudeSDKClient", side_effect=mock_client_factory):
            with patch("policy_factory.agent.session.asyncio.sleep", side_effect=mock_sleep):
                with pytest.raises(AgentError):
                    await session.run("test")

        # Should have MAX_RETRIES - 1 sleep calls (no sleep after last attempt)
        assert len(sleep_calls) == MAX_RETRIES - 1
        # Verify exponential backoff: 2, 4
        assert sleep_calls[0] == RETRY_BASE_DELAY
        assert sleep_calls[1] == RETRY_BASE_DELAY * 2

    @pytest.mark.asyncio
    async def test_agent_error_includes_role_and_cascade_id(self) -> None:
        """AgentError raised after max retries should have role and cascade_id."""
        config = AgentConfig()
        emitter = EventEmitter()
        session = AgentSession(
            config, emitter, context_id="cascade-42", agent_label="Test agent"
        )

        def mock_client_factory(*args: Any, **kwargs: Any) -> MagicMock:
            mock = AsyncMock()
            mock.__aenter__ = AsyncMock(
                side_effect=CLIConnectionError("CLI died")
            )
            mock.__aexit__ = AsyncMock(return_value=None)
            return mock

        with patch("policy_factory.agent.session.ClaudeSDKClient", side_effect=mock_client_factory):
            with patch("policy_factory.agent.session.asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(AgentError) as exc_info:
                    await session.run("test")

        assert exc_info.value.agent_role == "Test agent"
        assert exc_info.value.cascade_id == "cascade-42"


# ---------------------------------------------------------------------------
# Config / _build_options tests
# ---------------------------------------------------------------------------


class TestAgentSessionConfig:
    """Tests for _build_options() producing correct ClaudeAgentOptions."""

    def test_model_passed_to_options(self) -> None:
        """Config model should appear in ClaudeAgentOptions."""
        config = AgentConfig(model="claude-opus-4-0-20250514")
        emitter = EventEmitter()
        session = AgentSession(config, emitter)
        options = session._build_options()
        assert options.model == "claude-opus-4-0-20250514"

    def test_system_prompt_passed_to_options(self) -> None:
        """Config system_prompt should appear in ClaudeAgentOptions."""
        config = AgentConfig(system_prompt="Be helpful.")
        emitter = EventEmitter()
        session = AgentSession(config, emitter)
        options = session._build_options()
        assert options.system_prompt == "Be helpful."

    def test_empty_system_prompt_default(self) -> None:
        """When no system_prompt, options should get empty string."""
        config = AgentConfig()
        emitter = EventEmitter()
        session = AgentSession(config, emitter)
        options = session._build_options()
        assert options.system_prompt == ""

    def test_permission_mode_is_bypass(self) -> None:
        """Permission mode should be 'bypassPermissions'."""
        config = AgentConfig()
        emitter = EventEmitter()
        session = AgentSession(config, emitter)
        options = session._build_options()
        assert options.permission_mode == "bypassPermissions"

    def test_cwd_is_data_dir(self) -> None:
        """cwd should be set to the data_dir path."""
        config = AgentConfig()
        emitter = EventEmitter()
        data_dir = Path("/tmp/test-data")
        session = AgentSession(config, emitter, data_dir=data_dir)
        options = session._build_options()
        assert options.cwd == str(data_dir)

    def test_allowed_tools_for_generator_role(self) -> None:
        """Generator role should get MCP server reference."""
        config = AgentConfig(role="generator")
        emitter = EventEmitter()
        session = AgentSession(config, emitter)
        options = session._build_options()
        assert "mcp__policy-factory-tools" in options.allowed_tools
        assert "WebSearch" not in options.allowed_tools

    def test_allowed_tools_for_critic_role(self) -> None:
        """Critic role should get MCP server reference (read-only tools)."""
        config = AgentConfig(role="critic")
        emitter = EventEmitter()
        session = AgentSession(config, emitter)
        options = session._build_options()
        assert "mcp__policy-factory-tools" in options.allowed_tools
        assert "WebSearch" not in options.allowed_tools

    def test_allowed_tools_for_heartbeat_skim(self) -> None:
        """heartbeat-skim should get WebSearch only."""
        config = AgentConfig(role="heartbeat-skim")
        emitter = EventEmitter()
        session = AgentSession(config, emitter)
        options = session._build_options()
        assert "WebSearch" in options.allowed_tools
        assert "mcp__policy-factory-tools" not in options.allowed_tools

    def test_allowed_tools_for_seed_role(self) -> None:
        """Seed role should get both MCP server reference and WebSearch."""
        config = AgentConfig(role="seed")
        emitter = EventEmitter()
        session = AgentSession(config, emitter)
        options = session._build_options()
        assert "mcp__policy-factory-tools" in options.allowed_tools
        assert "WebSearch" in options.allowed_tools

    def test_empty_allowed_tools_for_synthesis(self) -> None:
        """Synthesis role (no tools) should get empty allowed_tools."""
        config = AgentConfig(role="synthesis")
        emitter = EventEmitter()
        session = AgentSession(config, emitter)
        options = session._build_options()
        assert options.allowed_tools == []

    def test_empty_allowed_tools_for_no_role(self) -> None:
        """No role should get empty allowed_tools."""
        config = AgentConfig()
        emitter = EventEmitter()
        session = AgentSession(config, emitter)
        options = session._build_options()
        assert options.allowed_tools == []

    def test_mcp_server_created_for_generator(self) -> None:
        """Generator role should have MCP server in options."""
        config = AgentConfig(role="generator")
        emitter = EventEmitter()
        session = AgentSession(config, emitter)
        options = session._build_options()
        assert "policy-factory-tools" in options.mcp_servers

    def test_mcp_server_created_for_critic(self) -> None:
        """Critic role (read-only) should have MCP server in options."""
        config = AgentConfig(role="critic")
        emitter = EventEmitter()
        session = AgentSession(config, emitter)
        options = session._build_options()
        assert "policy-factory-tools" in options.mcp_servers

    def test_no_mcp_server_for_synthesis(self) -> None:
        """Synthesis role should have no MCP server."""
        config = AgentConfig(role="synthesis")
        emitter = EventEmitter()
        session = AgentSession(config, emitter)
        options = session._build_options()
        assert options.mcp_servers == {}

    def test_no_mcp_server_for_no_role(self) -> None:
        """No role should have no MCP server."""
        config = AgentConfig()
        emitter = EventEmitter()
        session = AgentSession(config, emitter)
        options = session._build_options()
        assert options.mcp_servers == {}


# ---------------------------------------------------------------------------
# Context overflow tests
# ---------------------------------------------------------------------------


class TestAgentSessionContextOverflow:
    """Tests for context overflow error handling."""

    @pytest.mark.asyncio
    async def test_context_overflow_from_result_message(self) -> None:
        """Context overflow in ResultMessage error text should raise ContextOverflowError."""
        config = AgentConfig()
        emitter = EventEmitter()
        session = AgentSession(config, emitter)

        messages = [
            MockResultMessage(
                is_error=True,
                result="Error: prompt is too long for this model",
                session_id="sess-overflow",
            ),
        ]
        mock_client = _make_mock_client(messages)

        with patch("policy_factory.agent.session.ClaudeSDKClient", return_value=mock_client):
            with pytest.raises(ContextOverflowError, match="prompt is too long"):
                await session.run("test")

    @pytest.mark.asyncio
    async def test_context_overflow_from_exception(self) -> None:
        """Exception with 'context_length_exceeded' should raise ContextOverflowError."""
        config = AgentConfig()
        emitter = EventEmitter()
        session = AgentSession(config, emitter)

        def mock_client_factory(*args: Any, **kwargs: Any) -> MagicMock:
            mock = AsyncMock()
            mock.__aenter__ = AsyncMock(
                side_effect=Exception("context_length_exceeded: too many tokens")
            )
            mock.__aexit__ = AsyncMock(return_value=None)
            return mock

        with patch("policy_factory.agent.session.ClaudeSDKClient", side_effect=mock_client_factory):
            with pytest.raises(ContextOverflowError, match="context_length_exceeded"):
                await session.run("test")

    @pytest.mark.asyncio
    async def test_too_many_tokens_raises_overflow(self) -> None:
        """Exception with 'too many tokens' should raise ContextOverflowError."""
        config = AgentConfig()
        emitter = EventEmitter()
        session = AgentSession(config, emitter)

        def mock_client_factory(*args: Any, **kwargs: Any) -> MagicMock:
            mock = AsyncMock()
            mock.__aenter__ = AsyncMock(
                side_effect=Exception("Request has too many tokens")
            )
            mock.__aexit__ = AsyncMock(return_value=None)
            return mock

        with patch("policy_factory.agent.session.ClaudeSDKClient", side_effect=mock_client_factory):
            with pytest.raises(ContextOverflowError, match="too many tokens"):
                await session.run("test")

    @pytest.mark.asyncio
    async def test_context_overflow_not_retried(self) -> None:
        """ContextOverflowError should NOT be retried (single attempt only)."""
        config = AgentConfig()
        emitter = EventEmitter()
        session = AgentSession(config, emitter)

        call_count = 0

        def mock_client_factory(*args: Any, **kwargs: Any) -> MagicMock:
            nonlocal call_count
            call_count += 1
            mock = AsyncMock()
            mock.__aenter__ = AsyncMock(
                side_effect=Exception("prompt is too long")
            )
            mock.__aexit__ = AsyncMock(return_value=None)
            return mock

        with patch("policy_factory.agent.session.ClaudeSDKClient", side_effect=mock_client_factory):
            with pytest.raises(ContextOverflowError):
                await session.run("test")

        assert call_count == 1


# ---------------------------------------------------------------------------
# Gemini routing tests
# ---------------------------------------------------------------------------


class TestGeminiRouting:
    """Tests for automatic Gemini model routing in AgentSession.run()."""

    @pytest.mark.asyncio
    async def test_gemini_model_uses_gemini_path(self) -> None:
        """A Gemini model should route to _run_gemini, not ClaudeSDKClient."""
        config = AgentConfig(model="gemini-2.5-flash")
        emitter = EventEmitter()
        session = AgentSession(config, emitter, agent_label="Test gemini")

        with patch(
            "policy_factory.agent.session.gemini_generate",
            new_callable=AsyncMock,
            return_value="Gemini response text.",
        ) as mock_gen:
            result = await session.run("test prompt")

        mock_gen.assert_awaited_once_with(
            prompt="test prompt",
            model="gemini-2.5-flash",
            system_prompt=None,
        )
        assert result.is_error is False
        assert result.full_output == "Gemini response text."
        assert result.result_text == "Gemini response text."
        assert result.num_turns == 1
        assert result.session_id is None
        assert result.total_cost_usd is None

    @pytest.mark.asyncio
    async def test_gemini_model_with_system_prompt(self) -> None:
        """System prompt should be forwarded to gemini_generate."""
        config = AgentConfig(model="gemini-2.5-flash-lite", system_prompt="You are a classifier.")
        emitter = EventEmitter()
        session = AgentSession(config, emitter)

        with patch(
            "policy_factory.agent.session.gemini_generate",
            new_callable=AsyncMock,
            return_value="Classification result.",
        ) as mock_gen:
            result = await session.run("classify this")

        mock_gen.assert_awaited_once_with(
            prompt="classify this",
            model="gemini-2.5-flash-lite",
            system_prompt="You are a classifier.",
        )
        assert result.full_output == "Classification result."

    @pytest.mark.asyncio
    async def test_gemini_emits_text_chunk_event(self) -> None:
        """Gemini path should emit an AgentTextChunk for the response."""
        config = AgentConfig(model="gemini-2.5-flash")
        emitter = EventEmitter()
        received_events: list[AgentTextChunk] = []

        async def handler(event: Any) -> None:
            if isinstance(event, AgentTextChunk):
                received_events.append(event)

        emitter.subscribe(handler)

        session = AgentSession(
            config, emitter, context_id="ctx-gemini", agent_label="Gemini agent"
        )

        with patch(
            "policy_factory.agent.session.gemini_generate",
            new_callable=AsyncMock,
            return_value="Some output.",
        ):
            await session.run("test")

        assert len(received_events) == 1
        assert received_events[0].text == "Some output."
        assert received_events[0].cascade_id == "ctx-gemini"
        assert received_events[0].agent_label == "Gemini agent"

    @pytest.mark.asyncio
    async def test_gemini_empty_response_no_event(self) -> None:
        """Empty Gemini response should not emit an event."""
        config = AgentConfig(model="gemini-2.5-flash")
        emitter = EventEmitter()
        received_events: list[AgentTextChunk] = []

        async def handler(event: Any) -> None:
            if isinstance(event, AgentTextChunk):
                received_events.append(event)

        emitter.subscribe(handler)

        session = AgentSession(config, emitter)

        with patch(
            "policy_factory.agent.session.gemini_generate",
            new_callable=AsyncMock,
            return_value="",
        ):
            result = await session.run("test")

        assert len(received_events) == 0
        assert result.full_output == ""

    @pytest.mark.asyncio
    async def test_gemini_retries_on_transient_error(self) -> None:
        """Gemini path should retry on transient errors."""
        config = AgentConfig(model="gemini-2.5-flash")
        emitter = EventEmitter()
        session = AgentSession(config, emitter)

        call_count = 0

        async def failing_then_success(prompt: str, model: str, system_prompt: str | None = None) -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("503 Service Unavailable")
            return "Success after retries."

        with patch(
            "policy_factory.agent.session.gemini_generate",
            side_effect=failing_then_success,
        ):
            with patch("policy_factory.agent.session.asyncio.sleep", new_callable=AsyncMock):
                result = await session.run("test")

        assert call_count == 3
        assert result.full_output == "Success after retries."

    @pytest.mark.asyncio
    async def test_gemini_no_retry_on_api_key_error(self) -> None:
        """API key errors should not be retried."""
        config = AgentConfig(model="gemini-2.5-flash")
        emitter = EventEmitter()
        session = AgentSession(config, emitter, agent_label="Test")

        with patch(
            "policy_factory.agent.session.gemini_generate",
            new_callable=AsyncMock,
            side_effect=RuntimeError("No Google API key found."),
        ):
            with pytest.raises(AgentError, match="API key"):
                await session.run("test")

    @pytest.mark.asyncio
    async def test_gemini_raises_after_max_retries(self) -> None:
        """Gemini path should raise AgentError after MAX_RETRIES."""
        config = AgentConfig(model="gemini-2.5-flash")
        emitter = EventEmitter()
        session = AgentSession(config, emitter)

        with patch(
            "policy_factory.agent.session.gemini_generate",
            new_callable=AsyncMock,
            side_effect=RuntimeError("transient failure"),
        ):
            with patch("policy_factory.agent.session.asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(AgentError, match="Gemini agent failed after"):
                    await session.run("test")

    @pytest.mark.asyncio
    async def test_non_gemini_model_uses_claude_path(self) -> None:
        """A Claude model should NOT use the Gemini path."""
        config = AgentConfig(model="claude-sonnet-4-20250514")
        emitter = EventEmitter()
        session = AgentSession(config, emitter)

        messages = [
            MockAssistantMessage(text_blocks=["Claude output."]),
            MockResultMessage(is_error=False, result="Claude output."),
        ]
        mock_client = _make_mock_client(messages)

        with patch("policy_factory.agent.session.ClaudeSDKClient", return_value=mock_client):
            result = await session.run("test")

        assert result.result_text == "Claude output."

    @pytest.mark.asyncio
    async def test_none_model_uses_claude_path(self) -> None:
        """A None model should use the Claude CLI path (SDK default)."""
        config = AgentConfig(model=None)
        emitter = EventEmitter()
        session = AgentSession(config, emitter)

        messages = [
            MockAssistantMessage(text_blocks=["Default model output."]),
            MockResultMessage(is_error=False, result="Default model output."),
        ]
        mock_client = _make_mock_client(messages)

        with patch("policy_factory.agent.session.ClaudeSDKClient", return_value=mock_client):
            result = await session.run("test")

        assert result.result_text == "Default model output."
