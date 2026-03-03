"""Critic archetype definitions for the 6-perspective critic system.

Defines the six ideological critic archetypes used throughout the system:
the critic runner, synthesis runner, prompt templates, layer detail page,
and idea evaluation pipeline.

Each archetype has:
- A slug (used as the prompt template filename and database key).
- A display name (human-readable for UI rendering).
- An agent label (used in streaming events and agent run records).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CriticArchetype:
    """Definition of a single critic perspective.

    Attributes:
        slug: Machine-readable identifier, matches the prompt template
            filename (e.g. ``prompts/critics/{slug}.md``) and is stored
            in the database as the archetype key.
        display_name: Human-readable name for UI display.
        agent_label: Label used in agent streaming events and run records
            (e.g. "Realist critic").
    """

    slug: str
    display_name: str
    agent_label: str


# The 6 critic archetypes in canonical order
CRITIC_ARCHETYPES: list[CriticArchetype] = [
    CriticArchetype(
        slug="realist",
        display_name="Realist / Security hawk",
        agent_label="Realist critic",
    ),
    CriticArchetype(
        slug="liberal-institutionalist",
        display_name="Liberal-institutionalist",
        agent_label="Liberal-institutionalist critic",
    ),
    CriticArchetype(
        slug="nationalist-conservative",
        display_name="Nationalist-conservative",
        agent_label="Nationalist-conservative critic",
    ),
    CriticArchetype(
        slug="social-democratic",
        display_name="Social-democratic",
        agent_label="Social-democratic critic",
    ),
    CriticArchetype(
        slug="libertarian",
        display_name="Libertarian / Free-market",
        agent_label="Libertarian critic",
    ),
    CriticArchetype(
        slug="green-ecological",
        display_name="Green / Ecological",
        agent_label="Green/Ecological critic",
    ),
]

# Lookup helpers
_ARCHETYPE_BY_SLUG: dict[str, CriticArchetype] = {
    a.slug: a for a in CRITIC_ARCHETYPES
}


def get_archetype(slug: str) -> CriticArchetype | None:
    """Return the archetype for the given slug, or ``None`` if unknown."""
    return _ARCHETYPE_BY_SLUG.get(slug)


def get_archetype_slugs() -> list[str]:
    """Return all critic archetype slugs in canonical order."""
    return [a.slug for a in CRITIC_ARCHETYPES]


def get_all_archetypes() -> list[CriticArchetype]:
    """Return all critic archetypes in canonical order."""
    return list(CRITIC_ARCHETYPES)
