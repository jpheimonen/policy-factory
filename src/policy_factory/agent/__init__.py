"""Agent framework for Policy Factory.

Public API:
- ``AgentSession`` — Claude Code SDK session wrapper with retry.
- ``AgentConfig`` — Session configuration dataclass.
- ``AgentResult`` — Structured result from an agent run.
- ``AgentError`` — General agent error.
- ``ContextOverflowError`` — Context window exceeded.
- ``resolve_model`` — Resolve model name for an agent role.
- ``build_agent_prompt`` — Load an agent template with variable substitution.
- File tools: ``list_files``, ``read_file``, ``write_file``, ``delete_file``
- ``SandboxViolationError`` — Path validation error.
- ``validate_path`` — Validate path within sandbox.
"""

# ---------------------------------------------------------------------------
# Transitional guards (steps 002-003)
#
# config.py still imports removed Anthropic-format constants from tools.py,
# and session.py imports from config.py + removed TOOL_FUNCTIONS.
# These will be rewritten in steps 003-004.  Guard imports to keep the
# package importable so tool tests can run.
# ---------------------------------------------------------------------------
try:
    from policy_factory.agent.config import AgentConfig, resolve_model, resolve_tools
except ImportError:  # pragma: no cover – transitional until step 003
    AgentConfig = None  # type: ignore[assignment, misc]
    resolve_model = None  # type: ignore[assignment]
    resolve_tools = None  # type: ignore[assignment]

from policy_factory.agent.errors import AgentError, ContextOverflowError
from policy_factory.agent.prompts import build_agent_prompt

try:
    from policy_factory.agent.session import AgentResult, AgentSession
except ImportError:  # pragma: no cover – transitional until step 004
    AgentResult = None  # type: ignore[assignment, misc]
    AgentSession = None  # type: ignore[assignment, misc]

from policy_factory.agent.tools import (
    SandboxViolationError,
    delete_file,
    list_files,
    read_file,
    validate_path,
    write_file,
)

__all__ = [
    "AgentConfig",
    "AgentError",
    "AgentResult",
    "AgentSession",
    "ContextOverflowError",
    "SandboxViolationError",
    "build_agent_prompt",
    "delete_file",
    "list_files",
    "read_file",
    "resolve_model",
    "resolve_tools",
    "validate_path",
    "write_file",
]
