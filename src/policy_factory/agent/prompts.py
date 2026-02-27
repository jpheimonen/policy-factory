"""Prompt construction helper for agent sessions.

Assembles complete agent prompts by combining the shared meditation
preamble with agent-specific templates and dynamic variables.  This
ensures every agent prompt consistently includes the meditation
preamble without callers needing to remember to include it.
"""

from __future__ import annotations

from policy_factory.prompts import load_prompt, load_section

# Separator between meditation preamble and agent template
_SECTION_SEPARATOR = "\n\n---\n\n"


def build_agent_prompt(
    category: str,
    name: str,
    **variables: str,
) -> str:
    """Assemble a complete agent prompt with meditation preamble.

    Loads the meditation preamble section, then the agent-specific
    template with variable substitution, and concatenates them.

    Args:
        category: Prompt subdirectory (e.g. ``"generators"``,
            ``"critics"``).
        name: Template file name without extension (e.g. ``"values"``,
            ``"realist"``).
        **variables: Dynamic template variables to substitute into the
            agent template.

    Returns:
        The assembled prompt string: meditation + separator + template.

    Raises:
        FileNotFoundError: If the meditation section or template file
            does not exist.
    """
    meditation = load_section("meditation")
    template = load_prompt(category, name, **variables)
    return f"{meditation}{_SECTION_SEPARATOR}{template}"
