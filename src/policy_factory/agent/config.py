"""Session configuration and per-agent model resolution.

Provides:
- ``AgentConfig`` dataclass for configuring Claude Code SDK sessions.
- ``resolve_model()`` for mapping agent roles to model names via
  environment variables with sensible defaults.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

# Type for the SDK permission mode parameter
PermissionMode = Literal["default", "acceptEdits", "plan", "bypassPermissions"]

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


def _default_data_dir() -> Path:
    """Return the default data directory (``data/`` in the project root)."""
    return Path.cwd() / "data"


@dataclass
class AgentConfig:
    """Configuration for a single Claude Code agent session.

    Attributes:
        cwd: Working directory for the agent. Defaults to ``data/``.
        model: Model name. When ``None`` the SDK uses its default.
        max_turns: Maximum conversation turns (``None`` = SDK default).
        system_prompt: Optional system prompt override.
        permission_mode: SDK permission mode. Defaults to
            ``"bypassPermissions"`` since agents need to read/write
            markdown files in the data directory.
    """

    cwd: Path = field(default_factory=_default_data_dir)
    model: str | None = None
    max_turns: int | None = None
    system_prompt: str | None = None
    permission_mode: PermissionMode = "bypassPermissions"
