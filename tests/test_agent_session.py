"""Tests for the AgentSession wrapper.

These tests mock the Claude SDK to test the session wrapper's behaviour
without making actual API calls.
"""

from __future__ import annotations

import sys
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
# Helpers for mocking the SDK
# ---------------------------------------------------------------------------


@dataclass
class MockTextBlock:
    text: str


@dataclass
class MockAssistantMessage:
    content: list[MockTextBlock] = field(default_factory=list)


@dataclass
class MockResultMessage:
    is_error: bool = False
    result: str | None = None
    total_cost_usd: float | None = None
    num_turns: int | None = None


async def _async_iter(items):
    """Create an async iterator from a list."""
    for item in items:
        yield item


def _create_mock_sdk(messages, capture_options=None):
    """Create a mock claude_agent_sdk module with a mock client.

    Args:
        messages: List of mock messages for the receive_response stream.
        capture_options: Optional dict to capture ClaudeAgentOptions kwargs.

    Returns:
        A tuple of (mock_sdk_module, mock_client).
    """
    mock_client = AsyncMock()
    mock_client.query = AsyncMock()
    mock_client.receive_response = MagicMock(return_value=_async_iter(messages))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    def mock_options_factory(**kwargs):
        if capture_options is not None:
            capture_options.update(kwargs)
        return MagicMock()

    mock_sdk = MagicMock()
    mock_sdk.ClaudeSDKClient = MagicMock(return_value=mock_client)
    mock_sdk.ClaudeAgentOptions = mock_options_factory

    return mock_sdk, mock_client


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
# AgentSession tests (with mocked SDK)
# ---------------------------------------------------------------------------


class TestAgentSessionInit:
    """Tests for AgentSession initialization."""

    def test_accepts_config_and_emitter(self) -> None:
        config = AgentConfig()
        emitter = EventEmitter()
        session = AgentSession(config, emitter, context_id="ctx-1", agent_label="Test")
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


class TestAgentSessionRun:
    """Tests for AgentSession.run() with mocked SDK."""

    @pytest.mark.asyncio
    async def test_run_returns_agent_result_on_success(self) -> None:
        """Simulate a successful agent run."""
        config = AgentConfig()
        emitter = EventEmitter()
        session = AgentSession(config, emitter, agent_label="Test agent")

        messages = [
            MockAssistantMessage(content=[MockTextBlock(text="Analysis begins here.")]),
            MockResultMessage(is_error=False, result="Done", total_cost_usd=0.01, num_turns=2),
        ]
        mock_sdk, _ = _create_mock_sdk(messages)

        with patch.dict(sys.modules, {"claude_agent_sdk": mock_sdk}):
            result = await session.run("test prompt")

        assert isinstance(result, AgentResult)
        assert result.is_error is False
        assert result.result_text == "Done"
        assert result.total_cost_usd == 0.01
        assert result.num_turns == 2
        assert "Analysis begins here." in result.full_output

    @pytest.mark.asyncio
    async def test_run_emits_text_chunk_events(self) -> None:
        """Verify that text chunks are emitted via EventEmitter."""
        config = AgentConfig()
        emitter = EventEmitter()
        received_events: list[AgentTextChunk] = []

        async def handler(event):
            if isinstance(event, AgentTextChunk):
                received_events.append(event)

        emitter.subscribe(handler)

        session = AgentSession(config, emitter, context_id="cascade-1", agent_label="Values gen")

        # Send enough text to exceed detection threshold (500 chars)
        long_text = "Analysis content. " * 40  # ~720 chars
        messages = [
            MockAssistantMessage(content=[MockTextBlock(text=long_text)]),
            MockResultMessage(is_error=False, result="Done"),
        ]
        mock_sdk, _ = _create_mock_sdk(messages)

        with patch.dict(sys.modules, {"claude_agent_sdk": mock_sdk}):
            await session.run("test prompt")

        assert len(received_events) > 0
        assert received_events[0].cascade_id == "cascade-1"
        assert received_events[0].agent_label == "Values gen"

    @pytest.mark.asyncio
    async def test_run_captures_full_output_including_meditation(self) -> None:
        """Full output should include all text, even meditation content."""
        config = AgentConfig()
        emitter = EventEmitter()
        session = AgentSession(config, emitter)

        messages = [
            MockAssistantMessage(content=[MockTextBlock(text="10. I notice my bias")]),
            MockAssistantMessage(content=[MockTextBlock(text="Regular analysis")]),
            MockResultMessage(is_error=False, result="Done"),
        ]
        mock_sdk, _ = _create_mock_sdk(messages)

        with patch.dict(sys.modules, {"claude_agent_sdk": mock_sdk}):
            result = await session.run("test prompt")

        # Full output should contain everything
        assert "10. I notice my bias" in result.full_output
        assert "Regular analysis" in result.full_output

    @pytest.mark.asyncio
    async def test_run_raises_context_overflow_on_is_error_result(self) -> None:
        """ContextOverflowError should be raised on 'prompt is too long' result."""
        config = AgentConfig()
        emitter = EventEmitter()
        session = AgentSession(config, emitter)

        messages = [
            MockResultMessage(is_error=True, result="Error: prompt is too long"),
        ]
        mock_sdk, _ = _create_mock_sdk(messages)

        with patch.dict(sys.modules, {"claude_agent_sdk": mock_sdk}):
            with pytest.raises(ContextOverflowError, match="prompt is too long"):
                await session.run("test prompt")

    @pytest.mark.asyncio
    async def test_run_raises_agent_error_on_no_result(self) -> None:
        """AgentError should be raised if no result message is received."""
        config = AgentConfig()
        emitter = EventEmitter()
        session = AgentSession(config, emitter)

        messages = [
            MockAssistantMessage(content=[MockTextBlock(text="some text")]),
        ]
        mock_sdk, _ = _create_mock_sdk(messages)

        with patch.dict(sys.modules, {"claude_agent_sdk": mock_sdk}):
            with pytest.raises(AgentError, match="without result"):
                await session.run("test prompt")


class TestAgentSessionRetry:
    """Tests for retry logic."""

    @pytest.mark.asyncio
    async def test_retries_on_transient_error(self) -> None:
        """Transient errors should trigger retries with backoff."""
        config = AgentConfig()
        emitter = EventEmitter()
        session = AgentSession(config, emitter)

        call_count = 0

        async def mock_run_once(prompt):
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
        session = AgentSession(config, emitter)

        call_count = 0

        async def mock_run_once(prompt):
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
        session = AgentSession(config, emitter)

        call_count = 0

        async def mock_run_once(prompt):
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
        session = AgentSession(config, emitter)

        call_count = 0

        async def mock_run_once(prompt):
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
        session = AgentSession(config, emitter)

        sleep_calls: list[float] = []

        async def mock_sleep(delay):
            sleep_calls.append(delay)

        call_count = 0

        async def mock_run_once(prompt):
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


class TestAgentSessionConfig:
    """Tests for session config being passed to SDK."""

    @pytest.mark.asyncio
    async def test_config_model_passed_to_sdk(self) -> None:
        """Verify that the model from config is passed to SDK options."""
        config = AgentConfig(model="claude-opus-4-0-20250514")
        emitter = EventEmitter()
        session = AgentSession(config, emitter)

        captured_options: dict[str, Any] = {}
        messages = [MockResultMessage(is_error=False, result="Done")]
        mock_sdk, _ = _create_mock_sdk(messages, captured_options)

        with patch.dict(sys.modules, {"claude_agent_sdk": mock_sdk}):
            await session.run("test")

        assert captured_options["model"] == "claude-opus-4-0-20250514"

    @pytest.mark.asyncio
    async def test_config_cwd_passed_to_sdk(self) -> None:
        """Verify that the working directory is passed to SDK options."""
        config = AgentConfig()
        emitter = EventEmitter()
        session = AgentSession(config, emitter)

        captured_options: dict[str, Any] = {}
        messages = [MockResultMessage(is_error=False, result="Done")]
        mock_sdk, _ = _create_mock_sdk(messages, captured_options)

        with patch.dict(sys.modules, {"claude_agent_sdk": mock_sdk}):
            await session.run("test")

        assert captured_options["cwd"] == "/tmp/custom-data"

    @pytest.mark.asyncio
    async def test_web_search_in_allowed_tools(self) -> None:
        """Verify that web search tools are included in allowed_tools."""
        config = AgentConfig()
        emitter = EventEmitter()
        session = AgentSession(config, emitter)

        captured_options: dict[str, Any] = {}
        messages = [MockResultMessage(is_error=False, result="Done")]
        mock_sdk, _ = _create_mock_sdk(messages, captured_options)

        with patch.dict(sys.modules, {"claude_agent_sdk": mock_sdk}):
            await session.run("test")

        assert "WebSearch" in captured_options.get("allowed_tools", [])
