"""Seed router — Values and Situational Awareness population.

The seed endpoints trigger specialized agents to populate the foundational
layers of the policy stack:

- POST /api/seed/values — Uses Claude's knowledge to synthesize axiomatic
  Finnish policy values (no tools needed, uses training data)
- POST /api/seed/ — Uses web search to research Finland's current tech
  policy landscape and populate the Situational Awareness layer

Both seeding operations are re-runnable and will clear existing content
before writing new items.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

import yaml
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from policy_factory.cascade.orchestrator import trigger_cascade
from policy_factory.data.git import commit_changes
from policy_factory.data.layers import delete_item, list_items, write_item
from policy_factory.server.deps import (
    get_current_user,
    get_data_dir,
    get_event_emitter,
    get_store,
)
from policy_factory.store.auth import UserPublic

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/seed", tags=["seed"])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class SeedResponse(BaseModel):
    """Response for the seed trigger endpoint."""

    success: bool
    cascade_id: str | None = None
    message: str = ""


class SeedStatusResponse(BaseModel):
    """Response for the seed status endpoint."""

    seeded: bool
    item_count: int = 0


class ValuesSeedResponse(BaseModel):
    """Response for the values seed endpoint."""

    success: bool
    values_created: int = 0
    message: str = ""


# ---------------------------------------------------------------------------
# Helper: check if SA layer has been seeded
# ---------------------------------------------------------------------------


def _is_seeded(data_dir: Path) -> tuple[bool, int]:
    """Check whether the SA layer already has content beyond pre-seeded items.

    Returns:
        Tuple of (is_seeded, item_count).
    """
    items = list_items(data_dir, "situational-awareness")
    # If there are any items, consider it seeded
    return len(items) > 0, len(items)


# ---------------------------------------------------------------------------
# Helper: slugify title for filename
# ---------------------------------------------------------------------------


def _slugify(text: str) -> str:
    """Convert a title to a valid filename slug.

    Converts to lowercase, replaces spaces with hyphens, removes special
    characters, and normalizes unicode to ASCII.

    Args:
        text: The title text to slugify.

    Returns:
        A slug suitable for use as a filename (without .md extension).
    """
    # Normalize unicode to ASCII-compatible form (remove accents, etc.)
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")

    # Convert to lowercase
    text = text.lower()

    # Replace spaces and underscores with hyphens
    text = re.sub(r"[\s_]+", "-", text)

    # Remove any character that isn't alphanumeric or hyphen
    text = re.sub(r"[^a-z0-9\-]", "", text)

    # Collapse multiple hyphens
    text = re.sub(r"-+", "-", text)

    # Strip leading/trailing hyphens
    text = text.strip("-")

    return text


# ---------------------------------------------------------------------------
# Helper: parse values from agent output
# ---------------------------------------------------------------------------


def _parse_values_output(output: str) -> list[tuple[dict, str]]:
    """Parse individual value documents from the agent's response.

    The agent produces output with multiple value documents, each starting
    with YAML frontmatter delimited by ``---``. Format:

        ---
        title: "Value Title"
        tensions:
          - "Other Value 1"
          - "Other Value 2"
        ---

        Body content describing the value...

        ---
        title: "Next Value"
        ...

    Args:
        output: The complete agent output text.

    Returns:
        A list of (frontmatter_dict, body_string) tuples for each
        successfully parsed value. Malformed blocks are skipped.
    """
    values: list[tuple[dict, str]] = []

    # Split on frontmatter delimiters
    # Each value starts with --- followed by YAML, then ---, then body
    # Pattern: find all blocks that start with ---\n and have content
    # Use regex to find frontmatter blocks
    # Match: ---\n<yaml>\n---\n<body until next --- or end>
    pattern = r"---\s*\n(.*?)\n---\s*\n(.*?)(?=\n---\s*\n|\Z)"

    matches = re.findall(pattern, output, re.DOTALL)

    for yaml_content, body in matches:
        try:
            frontmatter = yaml.safe_load(yaml_content)
        except yaml.YAMLError:
            logger.warning("Failed to parse YAML frontmatter, skipping block")
            continue

        if not isinstance(frontmatter, dict):
            logger.warning("Frontmatter is not a dict, skipping block")
            continue

        # Check required fields
        title = frontmatter.get("title")
        if not title:
            logger.warning("Value block missing title, skipping")
            continue

        # Body is the content after closing ---
        body_text = body.strip()

        values.append((frontmatter, body_text))

    return values


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/values")
async def seed_values(
    _current_user: Annotated[UserPublic, Depends(get_current_user)],
) -> ValuesSeedResponse:
    """Seed the values layer with axiomatic Finnish policy values.

    Uses an agent with Claude's training knowledge (no tools) to synthesize
    foundational policy values. Clears any existing values before writing
    new ones.

    This endpoint is re-runnable — calling it multiple times will replace
    the existing values each time.

    Returns:
        ValuesSeedResponse with success status and count of values created.
    """
    store = get_store()
    emitter = get_event_emitter()
    data_dir = get_data_dir()

    # Import agent framework lazily
    from policy_factory.agent.config import AgentConfig, resolve_model, resolve_tools
    from policy_factory.agent.prompts import build_agent_prompt
    from policy_factory.agent.session import AgentSession

    # Resolve values-seed model and tools (should be empty list)
    model = resolve_model("values-seed")
    tools = resolve_tools("values-seed")

    # Build the values seed prompt
    prompt = build_agent_prompt("seed", "values")

    # Create agent config with no tools
    config = AgentConfig(
        model=model,
        tools=tools,
    )

    # Record agent run
    agent_label = "Values layer seed agent"
    agent_run_id = store.create_agent_run(
        cascade_id=None,
        agent_type="values-seed",
        agent_label=agent_label,
        model=model,
        target_layer="values",
    )

    # Run the values seed agent
    session = AgentSession(
        config=config,
        emitter=emitter,
        context_id="values-seed",
        agent_label=agent_label,
        data_dir=data_dir,
    )

    try:
        result = await session.run(prompt)

        store.complete_agent_run(
            agent_run_id,
            success=not result.is_error,
            error_message=result.result_text if result.is_error else None,
            cost=result.total_cost_usd,
            output_text=result.full_output,
        )

        if result.is_error:
            return ValuesSeedResponse(
                success=False,
                message=f"Values seed agent failed: {result.result_text}",
            )

    except Exception as exc:
        store.complete_agent_run(
            agent_run_id,
            success=False,
            error_message=str(exc),
        )
        return ValuesSeedResponse(
            success=False,
            message=f"Values seed agent error: {exc}",
        )

    # Parse the agent output to extract individual value documents
    parsed_values = _parse_values_output(result.full_output)

    if not parsed_values:
        # Zero values could be parsed — return error
        return ValuesSeedResponse(
            success=False,
            message=(
                "Failed to parse any values from agent output. "
                "The agent may have produced malformed output."
            ),
        )

    # Clear existing values before writing new ones
    existing_items = list_items(data_dir, "values")
    for item in existing_items:
        try:
            delete_item(data_dir, "values", item.filename)
        except Exception:
            logger.warning("Failed to delete existing value %s", item.filename)

    # Write each parsed value as a markdown file
    values_created = 0
    seen_slugs: set[str] = set()

    for frontmatter, body in parsed_values:
        title = frontmatter.get("title", "")
        slug = _slugify(title)

        # Handle duplicate slugs by appending a counter
        base_slug = slug
        counter = 2
        while slug in seen_slugs:
            slug = f"{base_slug}-{counter}"
            counter += 1
        seen_slugs.add(slug)

        filename = f"{slug}.md"

        try:
            write_item(
                data_dir,
                "values",
                filename,
                frontmatter,
                body,
                modified_by="values-seed-agent",
            )
            values_created += 1
        except Exception as exc:
            logger.warning("Failed to write value %s: %s", filename, exc)

    # Commit changes to git
    try:
        commit_changes(data_dir, f"Seed values layer ({values_created} values)")
    except Exception:
        logger.warning("Git commit failed after values seeding", exc_info=True)

    return ValuesSeedResponse(
        success=True,
        values_created=values_created,
        message=f"Values layer seeded successfully with {values_created} values.",
    )


@router.post("/")
async def trigger_seed(
    _current_user: Annotated[UserPublic, Depends(get_current_user)],
) -> SeedResponse:
    """Trigger initial Situational Awareness seeding.

    Checks whether the SA layer already has content. If it does,
    returns 409. Otherwise, runs the seed agent and triggers a cascade.
    """
    store = get_store()
    emitter = get_event_emitter()
    data_dir = get_data_dir()

    # Check if already seeded
    seeded, count = _is_seeded(data_dir)
    if seeded:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Situational Awareness layer already has {count} items. "
                "Seeding is a one-time operation."
            ),
        )

    # Import agent framework lazily
    from policy_factory.agent.config import AgentConfig, resolve_model
    from policy_factory.agent.prompts import build_agent_prompt
    from policy_factory.agent.session import AgentSession

    # Read values layer content as context
    values_items = list_items(data_dir, "values")
    values_content_parts: list[str] = []
    for item in values_items:
        try:
            from policy_factory.data.layers import read_item
            fm, body = read_item(data_dir, "values", item.filename)
            title = fm.get("title", item.filename)
            values_content_parts.append(f"### {title}\n{body}")
        except Exception:
            logger.warning("Failed to read values item %s", item.filename)

    values_content = (
        "\n\n".join(values_content_parts)
        if values_content_parts
        else "(no values content)"
    )

    # Resolve seed model
    model = resolve_model("seed")

    # Build seed prompt
    current_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    prompt = build_agent_prompt(
        "seed",
        "seed",
        current_date=current_date,
        values_content=values_content,
    )

    # Create agent config
    config = AgentConfig(
        cwd=data_dir,
        model=model,
    )

    # Record agent run
    agent_label = "Situational Awareness seed agent"
    agent_run_id = store.create_agent_run(
        cascade_id=None,
        agent_type="seed",
        agent_label=agent_label,
        model=model,
        target_layer="situational-awareness",
    )

    # Run the seed agent
    session = AgentSession(
        config=config,
        emitter=emitter,
        context_id="seed",
        agent_label=agent_label,
    )

    try:
        result = await session.run(prompt)

        store.complete_agent_run(
            agent_run_id,
            success=not result.is_error,
            error_message=result.result_text if result.is_error else None,
            cost=result.total_cost_usd,
            output_text=result.full_output,
        )

        if result.is_error:
            return SeedResponse(
                success=False,
                message=f"Seed agent failed: {result.result_text}",
            )

    except Exception as exc:
        store.complete_agent_run(
            agent_run_id,
            success=False,
            error_message=str(exc),
        )
        return SeedResponse(
            success=False,
            message=f"Seed agent error: {exc}",
        )

    # Auto-commit the seeded content
    try:
        commit_changes(data_dir, "Seed Situational Awareness layer")
    except Exception:
        logger.warning("Git commit failed after seeding", exc_info=True)

    # Trigger upward cascade from SA layer
    cascade_id: str | None = None
    try:
        cid, is_cascade = await trigger_cascade(
            trigger_source="seed",
            starting_layer="situational-awareness",
            store=store,
            emitter=emitter,
            data_dir=data_dir,
        )
        cascade_id = cid
    except Exception as exc:
        logger.error("Failed to trigger post-seed cascade: %s", exc)

    return SeedResponse(
        success=True,
        cascade_id=cascade_id,
        message="Situational Awareness layer seeded successfully.",
    )


@router.get("/status")
async def get_seed_status(
    _current_user: Annotated[UserPublic, Depends(get_current_user)],
) -> SeedStatusResponse:
    """Check whether seeding has been performed."""
    data_dir = get_data_dir()
    seeded, count = _is_seeded(data_dir)
    return SeedStatusResponse(seeded=seeded, item_count=count)
