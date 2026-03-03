"""Agent framework for Policy Factory.

Public API:
- ``AgentSession`` — Claude Code SDK session wrapper with retry.
- ``AgentConfig`` — Session configuration dataclass.
- ``AgentResult`` — Structured result from an agent run.
- ``AgentError`` — General agent error.
- ``ContextOverflowError`` — Context window exceeded.
- ``resolve_model`` — Resolve model name for an agent role.
- ``resolve_allowed_tools`` — Resolve allowed_tools list for a role.
- ``resolve_tool_set`` — Resolve MCP tool set identifier for a role.
- ``build_agent_prompt`` — Load an agent template with variable substitution.
- File tools: ``list_files``, ``read_file``, ``write_file``, ``delete_file``
- ``SandboxViolationError`` — Path validation error.
- ``validate_path`` — Validate path within sandbox.
"""

from policy_factory.agent.config import (
    AgentConfig,
    resolve_allowed_tools,
    resolve_model,
    resolve_tool_set,
)
from policy_factory.agent.errors import AgentError, ContextOverflowError
from policy_factory.agent.prompts import build_agent_prompt
from policy_factory.agent.session import AgentResult, AgentSession
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
    "resolve_allowed_tools",
    "resolve_model",
    "resolve_tool_set",
    "validate_path",
    "write_file",
]
