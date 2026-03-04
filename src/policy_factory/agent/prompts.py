"""Prompt construction helper for agent sessions.

Loads agent-specific templates with dynamic variable substitution
and auto-prepends the anti-slop preamble to every agent prompt.
"""

from __future__ import annotations

from policy_factory.prompts import load_prompt, load_section


def build_agent_prompt(
    category: str,
    name: str,
    **variables: str,
) -> str:
    """Assemble a complete agent prompt from a template.

    Loads the anti-slop preamble section and prepends it to the
    agent-specific template (with variable substitution applied to
    the template body only).

    Args:
        category: Prompt subdirectory (e.g. ``"generators"``,
            ``"critics"``).
        name: Template file name without extension (e.g. ``"values"``,
            ``"realist"``).
        **variables: Dynamic template variables to substitute into the
            agent template.

    Returns:
        The assembled prompt string with the anti-slop preamble
        prepended, separated from the template body by a double
        newline.

    Raises:
        FileNotFoundError: If the anti-slop section file or the
            template file does not exist.
    """
    preamble = load_section("anti-slop")
    body = load_prompt(category, name, **variables)
    return preamble + "\n\n" + body
