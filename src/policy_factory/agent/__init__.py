"""Agent framework for Policy Factory.

Public API:
- ``AgentSession`` — Claude Code SDK session wrapper with streaming and retry.
- ``AgentConfig`` — Session configuration dataclass.
- ``AgentResult`` — Structured result from an agent run.
- ``AgentError`` — General agent error.
- ``ContextOverflowError`` — Context window exceeded.
- ``MeditationFilter`` — Meditation content filter for streamed output.
- ``resolve_model`` — Resolve model name for an agent role.
- ``resolve_tools`` — Resolve tool configuration for an agent role.
- ``build_agent_prompt`` — Assemble meditation preamble + agent template.
- File tools: ``list_files``, ``read_file``, ``write_file``, ``delete_file``
- Tool definitions: ``FILE_TOOLS``, ``READ_ONLY_TOOLS``, ``TOOL_FUNCTIONS``
- ``SandboxViolationError`` — Path validation error.
- ``validate_path`` — Validate path within sandbox.
"""

from policy_factory.agent.config import AgentConfig, resolve_model, resolve_tools
from policy_factory.agent.errors import AgentError, ContextOverflowError
from policy_factory.agent.meditation_filter import MeditationFilter
from policy_factory.agent.prompts import build_agent_prompt
from policy_factory.agent.session import AgentResult, AgentSession
from policy_factory.agent.tools import (
    FILE_TOOLS,
    READ_ONLY_TOOLS,
    TOOL_FUNCTIONS,
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
    "FILE_TOOLS",
    "MeditationFilter",
    "READ_ONLY_TOOLS",
    "SandboxViolationError",
    "TOOL_FUNCTIONS",
    "build_agent_prompt",
    "delete_file",
    "list_files",
    "read_file",
    "resolve_model",
    "resolve_tools",
    "validate_path",
    "write_file",
]
