"""Agent session wrapper for Policy Factory agents.

Wraps the ``claude-agent-sdk`` to run agent sessions against the
``data/`` directory.  Processes SDK message streams, emits text chunks as
typed events through the EventEmitter, handles transient errors with retries,
and returns a structured result.

The session creates a ``ClaudeSDKClient`` per run, sends the prompt via
``query()``, iterates ``receive_response()`` to process messages, emits
``AgentTextChunk`` events from ``AssistantMessage`` text blocks, and
populates ``AgentResult`` from ``ResultMessage`` fields.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
from claude_agent_sdk._errors import CLIConnectionError, MessageParseError

from policy_factory.events import AgentTextChunk, EventEmitter

from .config import AgentConfig, resolve_allowed_tools, resolve_tool_set
from .errors import AgentError, ContextOverflowError
from .tools import TOOL_SET_NONE, create_tools_server

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0  # seconds, doubled each retry


@dataclass
class AgentResult:
    """Structured result from an agent session run.

    Attributes:
        is_error: Whether the agent terminated with an error.
        result_text: The final result text from the agent.
        total_cost_usd: Reported cost (may be ``None``).
        num_turns: Number of conversation turns used.
        full_output: Complete output from the agent session.
        session_id: Session identifier from the SDK for diagnostics.
    """

    is_error: bool = False
    result_text: str = ""
    total_cost_usd: float | None = None
    num_turns: int | None = None
    full_output: str = ""
    session_id: str | None = None


def _is_transient_error(error: Exception) -> bool:
    """Check whether an error is transient and worth retrying.

    Transient errors:
    - ``CLIConnectionError`` — the CLI process died or disconnected.
    - API 500 + "internal server error" or "api_error"
    - Status codes 502, 503, 529
    - "overloaded" or "rate limit" messages

    Non-transient errors (should NOT be retried):
    - ``MessageParseError`` — SDK couldn't parse a message type.
    - Authentication failures (handled separately in ``run()``).
    - Context overflow (handled separately in ``run()``).
    """
    # CLI process died or disconnected — retryable
    if isinstance(error, CLIConnectionError):
        return True

    # SDK couldn't parse a message type — not retryable
    if isinstance(error, MessageParseError):
        return False

    error_str = str(error).lower()

    # API server errors
    if "500" in error_str and (
        "internal server error" in error_str or "api_error" in error_str
    ):
        return True
    if any(code in error_str for code in ("502", "503", "529")):
        return True

    # Overload / rate limit
    if "overloaded" in error_str or "rate limit" in error_str:
        return True

    return False


def _is_context_overflow(error: Exception) -> bool:
    """Check if the error indicates context length exceeded."""
    error_str = str(error).lower()

    if "prompt is too long" in error_str:
        return True
    if "context_length_exceeded" in error_str:
        return True
    if "maximum context length" in error_str:
        return True
    if "too many tokens" in error_str:
        return True

    return False


class AgentSession:
    """Wraps the Claude Code SDK to run a single agent prompt to completion.

    Each ``run()`` call creates a fresh ``ClaudeSDKClient``, sends the prompt,
    processes the SDK's message stream, emits ``AgentTextChunk`` events for
    text blocks, and returns an ``AgentResult`` populated from the
    ``ResultMessage``.

    Args:
        config: Session configuration (model, system prompt, role).
        emitter: EventEmitter for broadcasting text chunks.
        context_id: Cascade or operation ID for event attribution.
        agent_label: Human-readable label (e.g. "Values layer generator").
        data_dir: Path to the data directory for file tool operations.
    """

    def __init__(
        self,
        config: AgentConfig,
        emitter: EventEmitter,
        context_id: str = "",
        agent_label: str = "",
        data_dir: Path | None = None,
    ) -> None:
        self._config = config
        self._emitter = emitter
        self._context_id = context_id
        self._agent_label = agent_label
        self._data_dir = data_dir or Path.cwd() / "data"

    def _build_options(self) -> ClaudeAgentOptions:
        """Construct ``ClaudeAgentOptions`` for the SDK.

        Resolves the ``allowed_tools`` list and MCP tool set from the config's
        role, creates the MCP server when file tools are needed, and returns
        fully configured options.
        """
        role = self._config.role

        # Resolve tools from the role
        if role is not None:
            allowed_tools = resolve_allowed_tools(role)
            tool_set = resolve_tool_set(role)
        else:
            allowed_tools: list[str] = []
            tool_set = TOOL_SET_NONE

        # Create MCP server when the role needs file tools
        mcp_servers: dict[str, Any] = {}
        if tool_set != TOOL_SET_NONE:
            mcp_servers = create_tools_server(
                data_dir=self._data_dir,
                tool_set=tool_set,
            )

        options = ClaudeAgentOptions(
            model=self._config.model,
            system_prompt=self._config.system_prompt or "",
            allowed_tools=allowed_tools,
            mcp_servers=mcp_servers,
            permission_mode="bypassPermissions",
            cwd=str(self._data_dir),
        )

        return options

    async def run(self, prompt: str) -> AgentResult:
        """Run a prompt to completion with retry logic.

        Creates a ``ClaudeSDKClient`` per attempt, sends the prompt via
        ``query()``, iterates ``receive_response()`` to process messages,
        and returns an ``AgentResult``.

        Args:
            prompt: The full prompt string to send to the agent.

        Returns:
            An ``AgentResult`` with the session outcome.

        Raises:
            ContextOverflowError: If the prompt exceeds the context window.
            AgentError: On non-transient failures after retries exhausted.
        """
        options = self._build_options()
        last_error: Exception | None = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                # --- SDK client lifecycle ---
                full_output_parts: list[str] = []
                result_is_error: bool = False
                result_text: str | None = None
                result_cost: float | None = None
                result_num_turns: int | None = None
                result_session_id: str | None = None

                async with ClaudeSDKClient(options=options) as client:
                    await client.query(prompt)

                    async for message in client.receive_response():
                        msg_type = type(message).__name__

                        # --- AssistantMessage: emit text chunk events ---
                        if msg_type == "AssistantMessage" and hasattr(message, "content"):
                            for block in message.content:
                                if hasattr(block, "text"):
                                    text = str(block.text)
                                    if text.strip():
                                        full_output_parts.append(text)
                                        await self._emitter.emit(
                                            AgentTextChunk(
                                                cascade_id=self._context_id,
                                                agent_label=self._agent_label,
                                                text=text,
                                            )
                                        )

                        # --- ResultMessage: extract result fields ---
                        if hasattr(message, "is_error"):
                            result_is_error = bool(message.is_error)
                            result_text = getattr(message, "result", None)
                            result_cost = getattr(message, "total_cost_usd", None)
                            result_num_turns = getattr(message, "num_turns", None)
                            result_session_id = getattr(message, "session_id", None)

                            # Check for context overflow in error result
                            if result_is_error and result_text:
                                if _is_context_overflow(
                                    Exception(result_text)
                                ):
                                    raise ContextOverflowError(
                                        str(result_text),
                                        session_id=result_session_id,
                                    )

                # Build the full output from all text blocks
                full_output = "\n\n".join(full_output_parts)

                # result_text falls back to full_output when None or empty
                if not result_text:
                    result_text = full_output

                return AgentResult(
                    is_error=result_is_error,
                    result_text=result_text or "",
                    total_cost_usd=result_cost,
                    num_turns=result_num_turns,
                    full_output=full_output,
                    session_id=result_session_id,
                )

            except ContextOverflowError:
                raise  # Never retry context overflow

            except Exception as exc:
                last_error = exc

                # Check for context overflow in exception message
                if _is_context_overflow(exc):
                    raise ContextOverflowError(str(exc)) from exc

                # Check for authentication failure (non-transient)
                error_str = str(exc).lower()
                if any(
                    kw in error_str
                    for kw in ("not found", "not installed", "auth", "login", "token")
                ):
                    raise AgentError(
                        f"Authentication failed: {exc}",
                        agent_role=self._agent_label,
                        cascade_id=self._context_id,
                    ) from exc

                # Transient check
                if attempt < MAX_RETRIES and _is_transient_error(exc):
                    delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                    logger.warning(
                        "Agent %r transient error (attempt %d/%d), "
                        "retrying in %.1fs: %s",
                        self._agent_label,
                        attempt,
                        MAX_RETRIES,
                        delay,
                        exc,
                    )
                    await asyncio.sleep(delay)
                    continue

                # Not transient or last attempt — raise
                if attempt >= MAX_RETRIES:
                    break

                raise AgentError(
                    str(exc),
                    agent_role=self._agent_label,
                    cascade_id=self._context_id,
                ) from exc

        # All retries exhausted
        raise AgentError(
            f"Agent failed after {MAX_RETRIES} attempts: {last_error}",
            agent_role=self._agent_label,
            cascade_id=self._context_id,
        ) from last_error
