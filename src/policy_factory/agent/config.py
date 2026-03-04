"""Session configuration and per-agent model/tool resolution.

Provides:
- ``AgentConfig`` dataclass for configuring Claude Code SDK agent sessions.
- ``resolve_model()`` for mapping agent roles to model names via
  environment variables with sensible defaults.
- ``resolve_allowed_tools()`` for mapping agent roles to the
  ``allowed_tools`` string list used by ``ClaudeAgentOptions``.
- ``resolve_tool_set()`` for mapping agent roles to the MCP tool set
  identifier used by the MCP server factory.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

from policy_factory.agent.tools import TOOL_SET_FULL, TOOL_SET_NONE, TOOL_SET_READ_ONLY

# MCP server reference string — follows the ``mcp__<server-name>`` convention.
# The server name matches the one in ``tools.create_tools_server()``.
MCP_SERVER_REF = "mcp__policy-factory-tools"

# Supported agent roles
AgentRole = Literal[
    "generator",
    "critic",
    "synthesis",
    "heartbeat-skim",
    "heartbeat-triage",
    "heartbeat-sa-update",
    "classifier",
    "idea-evaluator",
    "idea-generator",
    "seed",
    "values-seed",
    "strategic-seed",
    "tactical-seed",
    "policies-seed",
]

# Default model assignments per role.
#
# Roles that don't need tools (MCP/WebSearch) use Gemini Flash models —
# they're ~40x cheaper and fast enough for text-in/text-out tasks.
# Roles that need Claude CLI tools (MCP file tools, WebSearch) must use
# Claude models since the claude-agent-sdk wraps the Claude CLI binary.
#
# Model tiers:
#   Claude Opus  — heavyweight generation (generator, heartbeat-sa-update)
#   Claude Sonnet — mid-tier Claude tasks needing tools
#   Gemini 2.5 Flash — cheap text-in/text-out (synthesis, ideas, values-seed)
#   Gemini 2.5 Flash Lite — cheapest tier (classifier)
_DEFAULT_MODELS: dict[str, str | None] = {
    # --- Claude SDK roles (use CLI default model, currently Opus 4.6) ---
    "generator": None,
    "critic": None,
    "heartbeat-sa-update": None,
    "seed": None,
    "strategic-seed": None,
    "tactical-seed": None,
    "policies-seed": None,
    # --- Gemini models (heartbeat skim/triage get RSS news in prompt) ---
    "heartbeat-skim": "gemini-2.5-flash",
    "heartbeat-triage": "gemini-2.5-flash",
    # --- Gemini models (text-only, cheap) ---
    "synthesis": "gemini-2.5-flash",
    "classifier": "gemini-2.5-flash-lite",
    "idea-evaluator": "gemini-2.5-flash",
    "idea-generator": "gemini-2.5-flash",
    "values-seed": "gemini-2.5-flash",
}

# Environment variable names per role
_ENV_VAR_MAP: dict[str, str] = {
    "generator": "POLICY_FACTORY_MODEL_GENERATOR",
    "critic": "POLICY_FACTORY_MODEL_CRITIC",
    "synthesis": "POLICY_FACTORY_MODEL_SYNTHESIS",
    "heartbeat-skim": "POLICY_FACTORY_MODEL_HEARTBEAT_SKIM",
    "heartbeat-triage": "POLICY_FACTORY_MODEL_HEARTBEAT_TRIAGE",
    "heartbeat-sa-update": "POLICY_FACTORY_MODEL_HEARTBEAT_SA_UPDATE",
    "classifier": "POLICY_FACTORY_MODEL_CLASSIFIER",
    "idea-evaluator": "POLICY_FACTORY_MODEL_IDEA_EVALUATOR",
    "idea-generator": "POLICY_FACTORY_MODEL_IDEA_GENERATOR",
    "seed": "POLICY_FACTORY_MODEL_SEED",
    "values-seed": "POLICY_FACTORY_MODEL_VALUES_SEED",
    "strategic-seed": "POLICY_FACTORY_MODEL_STRATEGIC_SEED",
    "tactical-seed": "POLICY_FACTORY_MODEL_TACTICAL_SEED",
    "policies-seed": "POLICY_FACTORY_MODEL_POLICIES_SEED",
}


def resolve_model(role: str) -> str | None:
    """Resolve the model name for an agent role.

    Checks for an environment variable override first, then falls back
    to the built-in default.  When the default is ``None`` (CLI-default
    roles) and no env var override is set, ``None`` is returned — the
    caller should omit the model argument so the CLI picks its own
    default.

    Args:
        role: Agent role (e.g. ``"generator"``, ``"critic"``).

    Returns:
        The resolved model name string, or ``None`` for CLI-default roles
        with no env var override.

    Raises:
        ValueError: If the role is not recognised.
    """
    if role not in _DEFAULT_MODELS:
        valid = ", ".join(sorted(_DEFAULT_MODELS))
        raise ValueError(f"Unknown agent role: {role!r}. Valid roles: {valid}")

    env_var = _ENV_VAR_MAP[role]
    override = os.environ.get(env_var)
    if override:
        return override
    return _DEFAULT_MODELS[role]


# ---------------------------------------------------------------------------
# Per-role allowed_tools mapping
# ---------------------------------------------------------------------------

# Each role maps to a tuple of (list of allowed_tools strings).
# - MCP_SERVER_REF grants access to all tools from the MCP server.
# - "WebSearch" grants access to Claude Code's built-in web search.
# - Empty list means no tools are provisioned.
_ALLOWED_TOOLS_BY_ROLE: dict[str, list[str]] = {
    # Generators need full file access to write layer content
    "generator": [MCP_SERVER_REF],
    # Critics only need to read files (read-only access via MCP)
    "critic": [MCP_SERVER_REF],
    # Synthesis agents process existing data, no tools needed
    "synthesis": [],
    # Classifier agents analyze content, no tools needed
    "classifier": [],
    # Heartbeat skim: news pre-fetched via RSS, pure text analysis
    "heartbeat-skim": [],
    # Heartbeat triage: receives flagged items in prompt, pure text analysis
    "heartbeat-triage": [],
    # Heartbeat SA update needs file tools and web search
    "heartbeat-sa-update": [MCP_SERVER_REF, "WebSearch"],
    # Seed agent needs file tools and web search
    "seed": [MCP_SERVER_REF, "WebSearch"],
    # Values seed uses Claude's knowledge, no tools needed
    "values-seed": [],
    # Idea evaluator analyzes ideas, no tools needed
    "idea-evaluator": [],
    # Idea generator creates ideas from context, no tools needed
    "idea-generator": [],
    # Upper-layer seed agents need file tools only (no WebSearch)
    "strategic-seed": [MCP_SERVER_REF],
    "tactical-seed": [MCP_SERVER_REF],
    "policies-seed": [MCP_SERVER_REF],
}

# ---------------------------------------------------------------------------
# Per-role MCP tool set mapping
# ---------------------------------------------------------------------------

# Each role maps to the tool set identifier understood by
# ``tools.create_tools_server()``.
_TOOL_SET_BY_ROLE: dict[str, str] = {
    "generator": TOOL_SET_FULL,
    "critic": TOOL_SET_READ_ONLY,
    "synthesis": TOOL_SET_NONE,
    "classifier": TOOL_SET_NONE,
    "heartbeat-skim": TOOL_SET_NONE,
    "heartbeat-triage": TOOL_SET_NONE,
    "heartbeat-sa-update": TOOL_SET_FULL,
    "seed": TOOL_SET_FULL,
    "values-seed": TOOL_SET_NONE,
    "idea-evaluator": TOOL_SET_NONE,
    "idea-generator": TOOL_SET_NONE,
    "strategic-seed": TOOL_SET_FULL,
    "tactical-seed": TOOL_SET_FULL,
    "policies-seed": TOOL_SET_FULL,
}


# ---------------------------------------------------------------------------
# Per-role Google Search grounding flag
# ---------------------------------------------------------------------------

_USE_SEARCH_BY_ROLE: dict[str, bool] = {
    "generator": False,
    "critic": False,
    "synthesis": False,
    "classifier": False,
    "heartbeat-skim": True,
    "heartbeat-triage": True,
    "heartbeat-sa-update": False,
    "seed": False,
    "values-seed": False,
    "idea-evaluator": False,
    "idea-generator": False,
    "strategic-seed": False,
    "tactical-seed": False,
    "policies-seed": False,
}


def resolve_use_search(role: str) -> bool:
    """Resolve whether a role needs Google Search grounding."""
    if role not in _USE_SEARCH_BY_ROLE:
        valid = ", ".join(sorted(_USE_SEARCH_BY_ROLE))
        raise ValueError(f"Unknown agent role: {role!r}. Valid roles: {valid}")
    return _USE_SEARCH_BY_ROLE[role]

def resolve_allowed_tools(role: str) -> list[str]:
    """Resolve the ``allowed_tools`` list for a ``ClaudeAgentOptions``.

    Each role has a specific set of allowed tools:

    - Roles with file tools get the MCP server reference
      (``"mcp__policy-factory-tools"``).
    - Roles with web search get ``"WebSearch"``.
    - Roles with no tools get an empty list.

    Args:
        role: Agent role (e.g. ``"generator"``, ``"critic"``).

    Returns:
        A list of allowed tool strings suitable for
        ``ClaudeAgentOptions.allowed_tools``.

    Raises:
        ValueError: If the role is not recognised.
    """
    if role not in _ALLOWED_TOOLS_BY_ROLE:
        valid = ", ".join(sorted(_ALLOWED_TOOLS_BY_ROLE))
        raise ValueError(f"Unknown agent role: {role!r}. Valid roles: {valid}")

    # Return a copy to prevent mutation of the internal mapping
    return list(_ALLOWED_TOOLS_BY_ROLE[role])


def resolve_tool_set(role: str) -> str:
    """Resolve the MCP tool set identifier for a given role.

    This determines which file tools to include in the MCP server:

    - ``"full"`` — all four file tools (list, read, write, delete)
    - ``"read_only"`` — list_files and read_file only
    - ``"none"`` — no file tools (no MCP server needed)

    Args:
        role: Agent role (e.g. ``"generator"``, ``"critic"``).

    Returns:
        One of the tool set identifier strings (``TOOL_SET_FULL``,
        ``TOOL_SET_READ_ONLY``, or ``TOOL_SET_NONE``).

    Raises:
        ValueError: If the role is not recognised.
    """
    if role not in _TOOL_SET_BY_ROLE:
        valid = ", ".join(sorted(_TOOL_SET_BY_ROLE))
        raise ValueError(f"Unknown agent role: {role!r}. Valid roles: {valid}")

    # Return the string value directly — strings are immutable, no copy needed.
    return _TOOL_SET_BY_ROLE[role]


@dataclass
class AgentConfig:
    """Configuration for a single Claude Code SDK agent session.

    Attributes:
        model: Model name. When ``None`` the SDK uses its default.
        system_prompt: Optional system prompt override.
        role: Agent role identifier for tool resolution.  When set,
            ``AgentSession`` uses it to determine the MCP tool set
            and ``allowed_tools`` list.  When ``None``, no tools
            are provisioned (equivalent to an empty tool set).
    """

    model: str | None = None
    system_prompt: str | None = None
    role: str | None = None
