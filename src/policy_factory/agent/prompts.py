"""Prompt construction helper for agent sessions.

Loads agent-specific templates with dynamic variable substitution.
This is a thin wrapper around ``load_prompt()`` that provides a
convenient call site for agent callers.
"""

from __future__ import annotations

from policy_factory.prompts import load_prompt


def build_agent_prompt(
    category: str,
    name: str,
    **variables: str,
) -> str:
    """Assemble a complete agent prompt from a template.

    Loads the agent-specific template with variable substitution and
    returns the result directly.

    Args:
        category: Prompt subdirectory (e.g. ``"generators"``,
            ``"critics"``).
        name: Template file name without extension (e.g. ``"values"``,
            ``"realist"``).
        **variables: Dynamic template variables to substitute into the
            agent template.

    Returns:
        The assembled prompt string with variables substituted.

    Raises:
        FileNotFoundError: If the template file does not exist.
    """
    return load_prompt(category, name, **variables)
