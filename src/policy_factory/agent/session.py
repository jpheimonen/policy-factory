"""Claude Code session wrapper for Policy Factory agents.

Wraps ``claude-agent-sdk`` to run Claude Code sessions against the
``data/`` directory.  Streams SDK messages, emits text chunks as typed
events through the EventEmitter, handles transient errors with retries,
and returns a structured result.

This is a simplified adaptation of cc-runner's ``ClaudeCodeSession``,
retaining streaming, retry/backoff, and transient error classification
while dropping Ralph loops, HITL, MCP servers, guardrails, session
resume, tool permission hooks, and quota sleep.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from policy_factory.events import AgentTextChunk, EventEmitter

from .config import AgentConfig
from .errors import AgentError, ContextOverflowError
from .meditation_filter import MeditationFilter

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0  # seconds, doubled each retry


@dataclass
class AgentResult:
    """Structured result from an agent session run.

    Attributes:
        is_error: Whether the agent terminated with an error.
        result_text: The final result text from the SDK.
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

    Non-transient errors (should NOT be retried):
    - Authentication failures
    - Context overflow ("prompt is too long")
    """
    error_str = str(error).lower()

    # API server errors
    if "500" in error_str and ("internal server error" in error_str or "api_error" in error_str):
        return True
    if any(code in error_str for code in ("502", "503", "529")):
        return True

    # Overload / rate limit
    if "overloaded" in error_str or "rate limit" in error_str:
        return True

    return False


class AgentSession:
    """Wraps the Claude Code SDK to run a single agent prompt to completion.

    Args:
        config: Session configuration (model, cwd, etc.).
        emitter: EventEmitter for broadcasting text chunks.
        context_id: Cascade or operation ID for event attribution.
        agent_label: Human-readable label (e.g. "Values layer generator").
    """

    def __init__(
        self,
        config: AgentConfig,
        emitter: EventEmitter,
        context_id: str = "",
        agent_label: str = "",
    ) -> None:
        self._config = config
        self._emitter = emitter
        self._context_id = context_id
        self._agent_label = agent_label

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
                error_str = str(exc).lower()

                # Non-transient: auth failure
                if "auth" in error_str or "login" in error_str or "token" in error_str:
                    raise AgentError(
                        f"Authentication failed: {exc}",
                        agent_role=self._agent_label,
                        cascade_id=self._context_id,
                    ) from exc

                # Non-transient: context overflow from exception
                if "prompt is too long" in error_str:
                    raise ContextOverflowError(str(exc)) from exc

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

        Builds SDK options, streams messages, filters meditation content,
        and emits text chunk events.
        """
        # Lazy import — only needed when actually running agents
        from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

        options = ClaudeAgentOptions(
            cwd=str(self._config.cwd),
            permission_mode=self._config.permission_mode,
            model=self._config.model,
            max_turns=self._config.max_turns,
            system_prompt=self._config.system_prompt or "",
            allowed_tools=["WebSearch", "WebFetch"],
        )

        meditation_filter = MeditationFilter()
        full_output: list[str] = []
        result: dict[str, Any] | None = None

        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt)

            async for message in client.receive_response():
                # Extract text from AssistantMessage content blocks
                text = self._extract_text(message)
                if text:
                    full_output.append(text)

                    # Apply meditation filter
                    should_stream = meditation_filter.process(text)
                    if should_stream:
                        await self._emitter.emit(
                            AgentTextChunk(
                                cascade_id=self._context_id,
                                agent_label=self._agent_label,
                                text=text,
                            )
                        )

                # Capture result message
                if hasattr(message, "is_error"):
                    result = {
                        "is_error": message.is_error,
                        "result": getattr(message, "result", None),
                        "total_cost_usd": getattr(message, "total_cost_usd", None),
                        "num_turns": getattr(message, "num_turns", None),
                    }

                    # Detect context overflow
                    if result.get("is_error") and result.get("result"):
                        result_text = str(result["result"])
                        if "prompt is too long" in result_text.lower():
                            raise ContextOverflowError(result_text)

        if result is None:
            raise AgentError(
                "Session ended without result message",
                agent_role=self._agent_label,
                cascade_id=self._context_id,
            )

        full_text = "".join(full_output)

        return AgentResult(
            is_error=bool(result.get("is_error")),
            result_text=str(result.get("result") or ""),
            total_cost_usd=result.get("total_cost_usd"),
            num_turns=result.get("num_turns"),
            full_output=full_text,
        )

    @staticmethod
    def _extract_text(message: Any) -> str | None:
        """Extract text content from an SDK message.

        Handles ``AssistantMessage`` content blocks that have a ``text``
        attribute.
        """
        if hasattr(message, "content"):
            texts = [
                str(block.text) for block in message.content if hasattr(block, "text")
            ]
            return " ".join(texts) if texts else None
        return None
