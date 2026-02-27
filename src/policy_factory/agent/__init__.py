"""Agent framework for Policy Factory.

Public API:
- ``AgentSession`` — Claude Code SDK session wrapper with streaming and retry.
- ``AgentConfig`` — Session configuration dataclass.
- ``AgentResult`` — Structured result from an agent run.
- ``AgentError`` — General agent error.
- ``ContextOverflowError`` — Context window exceeded.
- ``MeditationFilter`` — Meditation content filter for streamed output.
- ``resolve_model`` — Resolve model name for an agent role.
- ``build_agent_prompt`` — Assemble meditation preamble + agent template.
"""

from policy_factory.agent.config import AgentConfig, resolve_model
from policy_factory.agent.errors import AgentError, ContextOverflowError
from policy_factory.agent.meditation_filter import MeditationFilter
from policy_factory.agent.prompts import build_agent_prompt
from policy_factory.agent.session import AgentResult, AgentSession

__all__ = [
    "AgentConfig",
    "AgentError",
    "AgentResult",
    "AgentSession",
    "ContextOverflowError",
    "MeditationFilter",
    "build_agent_prompt",
    "resolve_model",
]
