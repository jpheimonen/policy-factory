"""Agent-specific exception types.

These exceptions enable callers to distinguish between recoverable and
non-recoverable agent failures.
"""

from __future__ import annotations


class AgentError(Exception):
    """General agent error for non-transient failures.

    Attributes:
        message: Description of the failure.
        agent_role: The agent role that failed (e.g. "generator", "critic").
        cascade_id: Optional cascade ID for diagnostics.
    """

    def __init__(
        self,
        message: str,
        *,
        agent_role: str | None = None,
        cascade_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.agent_role = agent_role
        self.cascade_id = cascade_id


class ContextOverflowError(AgentError):
    """Raised when the agent's context window is exceeded.

    The Claude CLI returns an ``is_error`` result with text containing
    "prompt is too long" when the context limit is hit.  This error is
    non-transient and should not be retried.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
