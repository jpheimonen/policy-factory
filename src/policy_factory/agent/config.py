"""Session configuration and per-agent model resolution.

Provides:
- ``AgentConfig`` dataclass for configuring Anthropic SDK agent sessions.
- ``resolve_model()`` for mapping agent roles to model names via
  environment variables with sensible defaults.
- ``resolve_tools()`` for mapping agent roles to tool configurations.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Literal

from policy_factory.agent.tools import (
    FILE_TOOLS,
    FILE_TOOLS_WITH_WEB_SEARCH,
    READ_ONLY_TOOLS,
    WEB_SEARCH_ONLY,
)

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
]

# Default model assignments per role
_DEFAULT_MODELS: dict[str, str] = {
    "generator": "claude-opus-4-0-20250514",
    "critic": "claude-sonnet-4-20250514",
    "synthesis": "claude-sonnet-4-20250514",
    "heartbeat-skim": "claude-haiku-4-20250514",
    "heartbeat-triage": "claude-haiku-4-20250514",
    "heartbeat-sa-update": "claude-opus-4-0-20250514",
    "classifier": "claude-sonnet-4-20250514",
    "idea-evaluator": "claude-sonnet-4-20250514",
    "idea-generator": "claude-sonnet-4-20250514",
    "seed": "claude-sonnet-4-20250514",
    "values-seed": "claude-sonnet-4-20250514",
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
}


def resolve_model(role: str) -> str:
    """Resolve the model name for an agent role.

    Checks for an environment variable override first, then falls back
    to the built-in default.

    Args:
        role: Agent role (e.g. ``"generator"``, ``"critic"``).

    Returns:
        The resolved model name string.

    Raises:
        ValueError: If the role is not recognised.
    """
    if role not in _DEFAULT_MODELS:
        valid = ", ".join(sorted(_DEFAULT_MODELS))
        raise ValueError(f"Unknown agent role: {role!r}. Valid roles: {valid}")

    env_var = _ENV_VAR_MAP[role]
    return os.environ.get(env_var) or _DEFAULT_MODELS[role]


# Tool configurations per role
_TOOLS_BY_ROLE: dict[str, list[dict[str, Any]]] = {
    # Generators need full file access to write layer content
    "generator": FILE_TOOLS,
    # Critics only need to read files (read-only access)
    "critic": READ_ONLY_TOOLS,
    # Synthesis agents process existing data, no tools needed
    "synthesis": [],
    # Classifier agents analyze content, no tools needed
    "classifier": [],
    # Heartbeat skim uses web search to find relevant news
    "heartbeat-skim": WEB_SEARCH_ONLY,
    # Heartbeat triage evaluates items using web search
    "heartbeat-triage": WEB_SEARCH_ONLY,
    # Heartbeat SA update needs file tools and web search
    "heartbeat-sa-update": FILE_TOOLS_WITH_WEB_SEARCH,
    # Seed agent needs file tools and web search
    "seed": FILE_TOOLS_WITH_WEB_SEARCH,
    # Values seed uses Claude's knowledge, no tools needed
    "values-seed": [],
    # Idea evaluator analyzes ideas, no tools needed
    "idea-evaluator": [],
    # Idea generator creates ideas from context, no tools needed
    "idea-generator": [],
}


def resolve_tools(role: str) -> list[dict[str, Any]]:
    """Resolve the tool configuration for an agent role.

    Each role has a specific set of tools appropriate for its function:
    - Generator agents get full file tools
    - Critic agents get read-only tools
    - Heartbeat agents get web search
    - Values-seed, synthesis, classifier, and idea agents get no tools

    Args:
        role: Agent role (e.g. ``"generator"``, ``"critic"``).

    Returns:
        A list of tool definitions in Anthropic API format.

    Raises:
        ValueError: If the role is not recognised.
    """
    if role not in _TOOLS_BY_ROLE:
        valid = ", ".join(sorted(_TOOLS_BY_ROLE))
        raise ValueError(f"Unknown agent role: {role!r}. Valid roles: {valid}")

    # Return a copy to prevent mutation of the original
    return list(_TOOLS_BY_ROLE[role])


@dataclass
class AgentConfig:
    """Configuration for a single Anthropic SDK agent session.

    Attributes:
        model: Model name. When ``None`` the SDK uses its default.
        system_prompt: Optional system prompt override.
        tools: List of tool definitions in Anthropic API format.
            Each tool has name, description, and input_schema fields.
            For custom tools, each has name, description, and input_schema.
            For server-side tools like web_search, uses type field instead.
    """

    model: str | None = None
    system_prompt: str | None = None
    tools: list[dict[str, Any]] = field(default_factory=list)
