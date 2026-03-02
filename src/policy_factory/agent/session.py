"""Anthropic SDK session wrapper for Policy Factory agents.

Wraps the official Anthropic Python SDK to run agent sessions against the
``data/`` directory. Streams API responses, emits text chunks as typed
events through the EventEmitter, handles transient errors with retries,
and returns a structured result.

This implements a custom streaming agentic loop that:
- Uses ``AsyncAnthropic.messages.stream()`` for real-time token streaming
- Handles tool_use blocks by executing file tools and feeding results back
- Continues until the model signals end_turn without pending tool calls
- Preserves the meditation filter for suppressing countdown content
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from policy_factory.events import AgentTextChunk, EventEmitter

from .config import AgentConfig
from .errors import AgentError, ContextOverflowError
from .meditation_filter import MeditationFilter
from .tools import TOOL_FUNCTIONS

if TYPE_CHECKING:
    from anthropic import AsyncAnthropic

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0  # seconds, doubled each retry

# Maximum tokens for responses
MAX_TOKENS = 8192


@dataclass
class AgentResult:
    """Structured result from an agent session run.

    Attributes:
        is_error: Whether the agent terminated with an error.
        result_text: The final result text from the agent.
        total_cost_usd: Reported cost (may be ``None``).
        num_turns: Number of conversation turns used.
        full_output: Complete unfiltered output including meditation.
    """

    is_error: bool = False
    result_text: str = ""
    total_cost_usd: float | None = None
    num_turns: int | None = None
    full_output: str = ""


def _is_transient_error(error: Exception) -> bool:
    """Check whether an error is transient and worth retrying.

    Transient errors:
    - Anthropic API 500, 502, 503, 529 status codes
    - "overloaded" or "rate limit" messages
    - RateLimitError exceptions

    Non-transient errors (should NOT be retried):
    - Authentication failures
    - Context overflow ("prompt is too long" or context_length_exceeded)
    """
    # Check for Anthropic SDK exception types
    error_type = type(error).__name__

    # Rate limit errors are transient
    if error_type == "RateLimitError":
        return True

    # Overloaded errors are transient
    if error_type == "OverloadedError":
        return True

    # Authentication errors are NOT transient
    if error_type == "AuthenticationError":
        return False

    # Check status code if available
    if hasattr(error, "status_code"):
        status = getattr(error, "status_code", None)
        if status in (429, 500, 502, 503, 529):
            return True

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

    # Check for common context overflow indicators
    if "prompt is too long" in error_str:
        return True
    if "context_length_exceeded" in error_str:
        return True
    if "maximum context length" in error_str:
        return True
    if "too many tokens" in error_str:
        return True

    return False


def _is_auth_error(error: Exception) -> bool:
    """Check if the error is an authentication failure."""
    error_type = type(error).__name__
    if error_type == "AuthenticationError":
        return True

    error_str = str(error).lower()
    return (
        "authentication" in error_str
        or "invalid api key" in error_str
        or "invalid x-api-key" in error_str
    )


class AgentSession:
    """Wraps the Anthropic SDK to run a single agent prompt to completion.

    Args:
        config: Session configuration (model, tools, etc.).
        emitter: EventEmitter for broadcasting text chunks.
        context_id: Cascade or operation ID for event attribution.
        agent_label: Human-readable label (e.g. "Values layer generator").
        client: The shared AsyncAnthropic client instance.
        data_dir: Path to the data directory for file tool operations.
    """

    def __init__(
        self,
        config: AgentConfig,
        emitter: EventEmitter,
        context_id: str = "",
        agent_label: str = "",
        client: AsyncAnthropic | None = None,
        data_dir: Path | None = None,
    ) -> None:
        self._config = config
        self._emitter = emitter
        self._context_id = context_id
        self._agent_label = agent_label
        self._client = client
        self._data_dir = data_dir or Path.cwd() / "data"

    async def run(self, prompt: str) -> AgentResult:
        """Run a prompt to completion with retry logic.

        Args:
            prompt: The full prompt string to send to the agent.

        Returns:
            An ``AgentResult`` with the session outcome.

        Raises:
            ContextOverflowError: If the prompt exceeds the context window.
            AgentError: On non-transient failures after retries exhausted.
        """
        last_error: Exception | None = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                return await self._run_once(prompt)

            except ContextOverflowError:
                raise  # Never retry context overflow

            except Exception as exc:
                last_error = exc

                # Check for context overflow
                if _is_context_overflow(exc):
                    raise ContextOverflowError(str(exc)) from exc

                # Check for authentication failure (non-transient)
                if _is_auth_error(exc):
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

    async def _run_once(self, prompt: str) -> AgentResult:
        """Execute a single attempt of the agent prompt.

        Implements a streaming agentic loop that:
        1. Sends messages to the API with available tools
        2. Streams text deltas through the meditation filter
        3. Handles tool_use blocks by executing tools
        4. Continues until stop_reason is "end_turn" with no tool calls
        """
        # Lazy import to avoid startup failures if API key not configured
        from anthropic import AsyncAnthropic

        # Use provided client or create a new one
        client = self._client
        if client is None:
            client = AsyncAnthropic()

        # Build tool definitions based on config
        tools = self._config.tools if self._config.tools else []

        # Initialize conversation with user prompt
        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]

        meditation_filter = MeditationFilter()
        full_output: list[str] = []
        num_turns = 0
        total_input_tokens = 0
        total_output_tokens = 0

        # Agentic loop: continue until model signals end_turn without tool calls
        while True:
            num_turns += 1

            # Build API call parameters
            api_params: dict[str, Any] = {
                "model": self._config.model or "claude-sonnet-4-20250514",
                "max_tokens": MAX_TOKENS,
                "messages": messages,
            }

            # Add system prompt if configured
            if self._config.system_prompt:
                api_params["system"] = self._config.system_prompt

            # Add tools if any are configured
            if tools:
                api_params["tools"] = tools

            # Stream the response
            assistant_content: list[dict[str, Any]] = []
            current_text_block: str = ""
            current_tool_use: dict[str, Any] | None = None
            current_tool_input_json: str = ""
            stop_reason: str | None = None

            async with client.messages.stream(**api_params) as stream:
                async for event in stream:
                    # Handle different event types
                    if event.type == "content_block_start":
                        block = event.content_block
                        if block.type == "text":
                            current_text_block = ""
                        elif block.type == "tool_use":
                            current_tool_use = {
                                "type": "tool_use",
                                "id": block.id,
                                "name": block.name,
                                "input": {},
                            }
                            current_tool_input_json = ""

                    elif event.type == "content_block_delta":
                        delta = event.delta
                        if delta.type == "text_delta":
                            text = delta.text
                            current_text_block += text
                            full_output.append(text)

                            # Apply meditation filter and emit if allowed
                            should_stream = meditation_filter.process(text)
                            if should_stream:
                                await self._emitter.emit(
                                    AgentTextChunk(
                                        cascade_id=self._context_id,
                                        agent_label=self._agent_label,
                                        text=text,
                                    )
                                )

                        elif delta.type == "input_json_delta":
                            current_tool_input_json += delta.partial_json

                    elif event.type == "content_block_stop":
                        # Finalize the content block
                        if current_text_block:
                            assistant_content.append(
                                {"type": "text", "text": current_text_block}
                            )
                            current_text_block = ""

                        if current_tool_use is not None:
                            # Parse the accumulated JSON input
                            if current_tool_input_json:
                                try:
                                    current_tool_use["input"] = json.loads(
                                        current_tool_input_json
                                    )
                                except json.JSONDecodeError:
                                    current_tool_use["input"] = {}
                            assistant_content.append(current_tool_use)
                            current_tool_use = None
                            current_tool_input_json = ""

                    elif event.type == "message_delta":
                        stop_reason = event.delta.stop_reason

                # Get final message for usage stats
                final_message = await stream.get_final_message()
                total_input_tokens += final_message.usage.input_tokens
                total_output_tokens += final_message.usage.output_tokens

            # Add assistant message to conversation
            messages.append({"role": "assistant", "content": assistant_content})

            # Check for tool use blocks
            tool_use_blocks = [
                block for block in assistant_content if block.get("type") == "tool_use"
            ]

            # If no tool calls or stop_reason is end_turn, we're done
            if not tool_use_blocks or stop_reason == "end_turn":
                break

            # Execute tools and add results
            tool_results: list[dict[str, Any]] = []
            for tool_block in tool_use_blocks:
                tool_name = tool_block["name"]
                tool_input = tool_block["input"]
                tool_id = tool_block["id"]

                # Execute the tool
                result = self._execute_tool(tool_name, tool_input)

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": json.dumps(result),
                    }
                )

            # Add tool results to conversation
            messages.append({"role": "user", "content": tool_results})

        # Calculate approximate cost (rough estimates)
        # Claude Sonnet: $3/M input, $15/M output
        # This is a rough approximation
        input_cost = total_input_tokens * 3.0 / 1_000_000
        output_cost = total_output_tokens * 15.0 / 1_000_000
        total_cost = input_cost + output_cost

        full_text = "".join(full_output)

        return AgentResult(
            is_error=False,
            result_text=full_text,
            total_cost_usd=total_cost,
            num_turns=num_turns,
            full_output=full_text,
        )

    def _execute_tool(self, tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
        """Execute a tool and return the result.

        Args:
            tool_name: Name of the tool to execute.
            tool_input: Input parameters for the tool.

        Returns:
            A dict with the tool result (success or error).
        """
        if tool_name not in TOOL_FUNCTIONS:
            return {"error": f"Unknown tool: {tool_name}"}

        tool_func = TOOL_FUNCTIONS[tool_name]

        try:
            # All file tools take data_dir as first argument
            if tool_name == "list_files":
                return tool_func(self._data_dir, tool_input.get("path", ""))
            elif tool_name == "read_file":
                return tool_func(self._data_dir, tool_input.get("path", ""))
            elif tool_name == "write_file":
                return tool_func(
                    self._data_dir,
                    tool_input.get("path", ""),
                    tool_input.get("content", ""),
                )
            elif tool_name == "delete_file":
                return tool_func(self._data_dir, tool_input.get("path", ""))
            else:
                return {"error": f"Tool not implemented: {tool_name}"}
        except Exception as e:
            logger.exception("Tool %s execution failed", tool_name)
            return {"error": f"Tool execution failed: {e}"}
