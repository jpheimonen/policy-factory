"""Seed router — Policy layer population.

The seed endpoints trigger specialized agents to populate the layers
of the policy stack:

- POST /api/seed/philosophy — Uses model's knowledge to synthesize
  epistemological commitments and normative axioms (no tools needed)
- POST /api/seed/values — Uses Claude's knowledge to synthesize axiomatic
  Finnish policy values (no tools needed, uses training data)
- POST /api/seed/ — Uses web search to research Finland's current tech
  policy landscape and populate the Situational Awareness layer
- POST /api/seed/strategic-objectives — Seeds the strategic objectives layer
- POST /api/seed/tactical-objectives — Seeds the tactical objectives layer
- POST /api/seed/policies — Seeds the policies layer

All seeding operations are re-runnable and will clear existing content
before writing new items. The upper-layer seeds (strategic, tactical,
policies) validate that all prerequisite layers below are populated
before proceeding.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from datetime import datetime, timezone
from typing import Annotated

import yaml
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from policy_factory.cascade.content import check_prerequisites, gather_context_below
from policy_factory.cascade.orchestrator import trigger_cascade
from policy_factory.data.git import commit_changes
from policy_factory.data.layers import LAYERS, delete_item, list_items, read_item, write_item
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


class LayerStatusEntry(BaseModel):
    """Status of a single layer in the policy stack.

    Attributes:
        slug: Layer identifier (e.g. ``"values"``, ``"situational-awareness"``).
        display_name: Human-readable layer name (e.g. ``"Situational Awareness"``).
        seeded: Whether the layer has at least one item.
        count: Number of items in the layer.
    """

    slug: str
    display_name: str
    seeded: bool
    count: int = 0


class SeedStatusResponse(BaseModel):
    """Response for the seed status endpoint.

    Reports the seeding status of all 5 layers in the policy stack,
    ordered hierarchically from bottom (values) to top (policies).

    Attributes:
        layers: List of per-layer status entries.
    """

    layers: list[LayerStatusEntry]


class SeedRequest(BaseModel):
    """Request body for SA seed endpoint."""

    context: str | None = None
    """Optional human-provided context to inform the seed agent's research.

    When provided, this context is prepended to the seed prompt so the agent
    incorporates it alongside web research. Useful for providing situational
    context like "Here's how Finland's situation looks right now".
    """


class ValuesSeedResponse(BaseModel):
    """Response for the values seed endpoint."""

    success: bool
    values_created: int = 0
    message: str = ""


class PhilosophySeedResponse(BaseModel):
    """Response for the philosophy seed endpoint."""

    success: bool
    items_created: int = 0
    message: str = ""


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
# Helper: run a seed agent with tracking
# ---------------------------------------------------------------------------


async def _run_seed_agent(
    *,
    prompt: str,
    agent_role: str,
    agent_label: str,
    target_layer: str,
) -> tuple[object | None, str | None]:
    """Execute a seed agent and record the run in the store.

    Handles the full agent lifecycle: resolve model, create config,
    record the agent run, execute, and record completion.  This
    eliminates the duplicated try/except/complete_agent_run boilerplate
    from each seed endpoint.

    Args:
        prompt: The fully-assembled prompt string.
        agent_role: Agent role key (e.g. ``"values-seed"``).
        agent_label: Human-readable label for logging/display.
        target_layer: Layer slug being seeded.

    Returns:
        A tuple of ``(result, error_message)``.  On success,
        ``result`` is the ``AgentResult`` and ``error_message`` is
        ``None``.  On failure, ``result`` is ``None`` and
        ``error_message`` describes the failure.
    """
    from policy_factory.agent.config import AgentConfig, resolve_model
    from policy_factory.agent.session import AgentSession

    store = get_store()
    emitter = get_event_emitter()
    data_dir = get_data_dir()

    model = resolve_model(agent_role)
    config = AgentConfig(model=model, role=agent_role)

    agent_run_id = store.create_agent_run(
        cascade_id=None,
        agent_type=agent_role,
        agent_label=agent_label,
        model=model,
        target_layer=target_layer,
    )

    session = AgentSession(
        config=config,
        emitter=emitter,
        context_id=agent_role,
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
            return None, f"{agent_label} failed: {result.result_text}"

        return result, None

    except Exception as exc:
        store.complete_agent_run(
            agent_run_id,
            success=False,
            error_message=str(exc),
        )
        return None, f"{agent_label} error: {exc}"


# ---------------------------------------------------------------------------
# Helper: seed foundational layer (philosophy, values)
# ---------------------------------------------------------------------------


async def _seed_foundational_layer(
    *,
    layer_slug: str,
    agent_role: str,
    template_name: str,
    agent_label: str,
    modified_by: str,
) -> tuple[bool, int, str]:
    """Shared logic for seeding foundational layers (philosophy, values).

    These layers use model knowledge (no tools) and produce YAML-frontmatter
    output that is parsed, written to files, and committed.

    Args:
        layer_slug: Target layer slug (e.g. ``"philosophy"``, ``"values"``).
        agent_role: Agent role key (e.g. ``"philosophy-seed"``).
        template_name: Prompt template name within the ``seed/`` directory.
        agent_label: Human-readable label for logging/display.
        modified_by: Author name for frontmatter metadata.

    Returns:
        Tuple of (success, items_created, message).
    """
    from policy_factory.agent.prompts import build_agent_prompt
    from policy_factory.events import SeedCompleted, SeedProgress, SeedStarted

    data_dir = get_data_dir()
    emitter = get_event_emitter()

    await emitter.emit(SeedStarted(layer_slug=layer_slug, agent_label=agent_label))

    # Build and run the seed agent
    prompt = build_agent_prompt("seed", template_name)

    await emitter.emit(SeedProgress(
        layer_slug=layer_slug,
        step="agent_running",
        message=f"Running {agent_label}…",
    ))

    result, error_msg = await _run_seed_agent(
        prompt=prompt,
        agent_role=agent_role,
        agent_label=agent_label,
        target_layer=layer_slug,
    )
    if error_msg is not None:
        await emitter.emit(SeedCompleted(
            layer_slug=layer_slug, success=False, message=error_msg,
        ))
        return False, 0, error_msg

    # Parse the agent output to extract individual items
    await emitter.emit(SeedProgress(
        layer_slug=layer_slug,
        step="parsing",
        message="Parsing agent output…",
    ))
    parsed_items = _parse_values_output(result.full_output)

    if not parsed_items:
        msg = (
            f"Failed to parse any {layer_slug} items from agent output. "
            "The agent may have produced malformed output."
        )
        await emitter.emit(SeedCompleted(
            layer_slug=layer_slug, success=False, message=msg,
        ))
        return False, 0, msg

    # Clear existing items before writing new ones
    existing_items = list_items(data_dir, layer_slug)
    for item in existing_items:
        try:
            delete_item(data_dir, layer_slug, item.filename)
        except Exception:
            logger.warning("Failed to delete existing %s item %s", layer_slug, item.filename)

    # Write each parsed item as a markdown file
    await emitter.emit(SeedProgress(
        layer_slug=layer_slug,
        step="writing",
        message=f"Writing {len(parsed_items)} items…",
    ))
    items_created = 0
    seen_slugs: set[str] = set()

    for frontmatter, body in parsed_items:
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
            write_item(data_dir, layer_slug, filename, frontmatter, body, modified_by=modified_by)
            items_created += 1
        except Exception as exc:
            logger.warning("Failed to write %s item %s: %s", layer_slug, filename, exc)

    # Commit changes to git
    await emitter.emit(SeedProgress(
        layer_slug=layer_slug,
        step="committing",
        message="Committing to git…",
    ))
    try:
        commit_changes(data_dir, f"Seed {layer_slug} layer ({items_created} items)")
    except Exception:
        logger.warning("Git commit failed after %s seeding", layer_slug, exc_info=True)

    layer_name = layer_slug.replace('-', ' ').title()
    msg = f"{layer_name} layer seeded successfully with {items_created} items."
    await emitter.emit(SeedCompleted(
        layer_slug=layer_slug, success=True, message=msg, items_created=items_created,
    ))

    return True, items_created, msg


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
    success, values_created, message = await _seed_foundational_layer(
        layer_slug="values",
        agent_role="values-seed",
        template_name="values",
        agent_label="Values layer seed agent",
        modified_by="values-seed-agent",
    )
    return ValuesSeedResponse(success=success, values_created=values_created, message=message)


@router.post("/philosophy")
async def seed_philosophy(
    _current_user: Annotated[UserPublic, Depends(get_current_user)],
) -> PhilosophySeedResponse:
    """Seed the philosophy layer with epistemological commitments and normative axioms.

    Uses an agent with model's training knowledge (no tools) to synthesize
    foundational philosophical reasoning axioms. Clears any existing philosophy
    items before writing new ones.

    This endpoint is re-runnable — calling it multiple times will replace
    the existing philosophy items each time.

    Returns:
        PhilosophySeedResponse with success status and count of items created.
    """
    success, items_created, message = await _seed_foundational_layer(
        layer_slug="philosophy",
        agent_role="philosophy-seed",
        template_name="philosophy",
        agent_label="Philosophy layer seed agent",
        modified_by="philosophy-seed-agent",
    )
    return PhilosophySeedResponse(success=success, items_created=items_created, message=message)


@router.post("/")
async def trigger_seed(
    _current_user: Annotated[UserPublic, Depends(get_current_user)],
    request: SeedRequest | None = None,
) -> SeedResponse:
    """Trigger Situational Awareness seeding.

    Clears any existing SA items, runs the seed agent with web search,
    and triggers a cascade after successful seeding. This endpoint is
    re-runnable — calling it multiple times will replace existing SA
    items each time.

    Args:
        request: Optional request body with context field. When context
            is provided, it is prepended to the seed prompt so the agent
            incorporates it alongside web research.

    Returns:
        SeedResponse with success status, cascade ID, and message.
    """
    from policy_factory.events import SeedCompleted, SeedProgress, SeedStarted

    store = get_store()
    emitter = get_event_emitter()
    data_dir = get_data_dir()

    await emitter.emit(SeedStarted(
        layer_slug="situational-awareness",
        agent_label="Situational Awareness seed agent",
    ))

    # Clear existing SA items before re-seeding
    existing_items = list_items(data_dir, "situational-awareness")
    for item in existing_items:
        try:
            delete_item(data_dir, "situational-awareness", item.filename)
        except Exception:
            logger.warning("Failed to delete existing SA item %s", item.filename)

    from policy_factory.agent.prompts import build_agent_prompt

    # Read values layer content as context
    values_items = list_items(data_dir, "values")
    values_content_parts: list[str] = []
    for item in values_items:
        try:
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

    # Build seed prompt
    current_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    prompt = build_agent_prompt(
        "seed",
        "seed",
        current_date=current_date,
        values_content=values_content,
    )

    # Prepend user-provided context if available
    if request and request.context:
        context_section = (
            "## Human-Provided Context\n\n"
            "The user has provided the following situational context to inform "
            "your research. Consider this information alongside your web research:\n\n"
            f"{request.context}\n\n"
            "---\n\n"
        )
        prompt = context_section + prompt

    await emitter.emit(SeedProgress(
        layer_slug="situational-awareness",
        step="agent_running",
        message="Running SA seed agent (web research)…",
    ))

    result, error_msg = await _run_seed_agent(
        prompt=prompt,
        agent_role="seed",
        agent_label="Situational Awareness seed agent",
        target_layer="situational-awareness",
    )
    if error_msg is not None:
        await emitter.emit(SeedCompleted(
            layer_slug="situational-awareness", success=False, message=error_msg,
        ))
        return SeedResponse(success=False, message=error_msg)

    # Auto-commit the seeded content
    await emitter.emit(SeedProgress(
        layer_slug="situational-awareness",
        step="committing",
        message="Committing to git…",
    ))
    try:
        commit_changes(data_dir, "Seed Situational Awareness layer")
    except Exception:
        logger.warning("Git commit failed after seeding", exc_info=True)

    # Trigger upward cascade from SA layer
    await emitter.emit(SeedProgress(
        layer_slug="situational-awareness",
        step="cascade",
        message="Triggering upward cascade…",
    ))
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

    msg = "Situational Awareness layer seeded successfully."
    await emitter.emit(SeedCompleted(
        layer_slug="situational-awareness", success=True, message=msg,
    ))

    return SeedResponse(
        success=True,
        cascade_id=cascade_id,
        message=msg,
    )


@router.get("/status")
async def get_seed_status(
    _current_user: Annotated[UserPublic, Depends(get_current_user)],
) -> SeedStatusResponse:
    """Check the seeding status of all 5 policy layers.

    Returns a list of layer status entries ordered hierarchically from
    bottom (values) to top (policies). Each entry reports the layer slug,
    display name, whether it has been seeded, and the item count.

    Returns:
        SeedStatusResponse with a list of per-layer status entries.
    """
    data_dir = get_data_dir()

    entries: list[LayerStatusEntry] = []
    for layer in LAYERS:
        items = list_items(data_dir, layer.slug)
        count = len(items)
        entries.append(
            LayerStatusEntry(
                slug=layer.slug,
                display_name=layer.display_name,
                seeded=count > 0,
                count=count,
            )
        )

    return SeedStatusResponse(layers=entries)


# ---------------------------------------------------------------------------
# Upper-layer seed helper and endpoints
# ---------------------------------------------------------------------------


async def _seed_upper_layer(
    *,
    layer_slug: str,
    agent_role: str,
    template_name: str,
    agent_label: str,
) -> SeedResponse:
    """Shared logic for seeding an upper-layer (strategic, tactical, policies).

    Validates prerequisites, clears existing items, gathers context from
    layers below, runs the seed agent, and commits to git.

    Args:
        layer_slug: Target layer slug (e.g. ``"strategic-objectives"``).
        agent_role: Agent role key (e.g. ``"strategic-seed"``).
        template_name: Prompt template name (e.g. ``"strategic"``).
        agent_label: Human-readable label for logging/display.

    Returns:
        SeedResponse with success/failure status and message.
    """
    from policy_factory.events import SeedCompleted, SeedProgress, SeedStarted

    data_dir = get_data_dir()
    emitter = get_event_emitter()

    # 1. Validate prerequisites — all layers below must have items
    empty_layers = check_prerequisites(data_dir, layer_slug)
    if empty_layers:
        names = ", ".join(empty_layers)
        msg = f"Cannot seed {layer_slug}: prerequisite layers are empty: {names}"
        await emitter.emit(SeedCompleted(
            layer_slug=layer_slug, success=False, message=msg,
        ))
        return SeedResponse(success=False, message=msg)

    await emitter.emit(SeedStarted(
        layer_slug=layer_slug,
        agent_label=agent_label,
    ))

    # 2. Clear existing items in the target layer
    existing_items = list_items(data_dir, layer_slug)
    for item in existing_items:
        try:
            delete_item(data_dir, layer_slug, item.filename)
        except Exception:
            logger.warning(
                "Failed to delete existing %s item %s",
                layer_slug,
                item.filename,
            )

    # 3. Gather context from all layers below
    await emitter.emit(SeedProgress(
        layer_slug=layer_slug,
        step="preparing",
        message="Gathering context from layers below…",
    ))
    context_below = gather_context_below(data_dir, layer_slug)

    from policy_factory.agent.prompts import build_agent_prompt

    # 4. Build the prompt
    current_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    prompt = build_agent_prompt(
        "seed",
        template_name,
        current_date=current_date,
        context_below=context_below,
    )

    # 5. Execute the seed agent
    await emitter.emit(SeedProgress(
        layer_slug=layer_slug,
        step="agent_running",
        message=f"Running {agent_label}…",
    ))
    result, error_msg = await _run_seed_agent(
        prompt=prompt,
        agent_role=agent_role,
        agent_label=agent_label,
        target_layer=layer_slug,
    )
    if error_msg is not None:
        await emitter.emit(SeedCompleted(
            layer_slug=layer_slug, success=False, message=error_msg,
        ))
        return SeedResponse(success=False, message=error_msg)

    # 6. Commit to git
    await emitter.emit(SeedProgress(
        layer_slug=layer_slug,
        step="committing",
        message="Committing to git…",
    ))
    try:
        commit_changes(data_dir, f"Seed {layer_slug} layer")
    except Exception:
        logger.warning(
            "Git commit failed after %s seeding", layer_slug, exc_info=True
        )

    # 7. Return success (no cascade_id — upper seeds don't trigger cascades)
    msg = f"{layer_slug} layer seeded successfully."
    await emitter.emit(SeedCompleted(
        layer_slug=layer_slug, success=True, message=msg,
    ))
    return SeedResponse(success=True, message=msg)


@router.post("/strategic-objectives")
async def seed_strategic_objectives(
    _current_user: Annotated[UserPublic, Depends(get_current_user)],
) -> SeedResponse:
    """Seed the strategic objectives layer.

    Validates that the values and situational-awareness layers are
    populated, clears existing strategic-objectives items, gathers
    context from layers below, runs the strategic-seed agent, and
    commits to git.

    Returns:
        SeedResponse with success status and message.
    """
    return await _seed_upper_layer(
        layer_slug="strategic-objectives",
        agent_role="strategic-seed",
        template_name="strategic",
        agent_label="Strategic Objectives seed agent",
    )


@router.post("/tactical-objectives")
async def seed_tactical_objectives(
    _current_user: Annotated[UserPublic, Depends(get_current_user)],
) -> SeedResponse:
    """Seed the tactical objectives layer.

    Validates that the values, situational-awareness, and
    strategic-objectives layers are populated, clears existing
    tactical-objectives items, gathers context from layers below,
    runs the tactical-seed agent, and commits to git.

    Returns:
        SeedResponse with success status and message.
    """
    return await _seed_upper_layer(
        layer_slug="tactical-objectives",
        agent_role="tactical-seed",
        template_name="tactical",
        agent_label="Tactical Objectives seed agent",
    )


@router.post("/policies")
async def seed_policies(
    _current_user: Annotated[UserPublic, Depends(get_current_user)],
) -> SeedResponse:
    """Seed the policies layer.

    Validates that all four layers below (values, situational-awareness,
    strategic-objectives, tactical-objectives) are populated, clears
    existing policies items, gathers context from layers below, runs
    the policies-seed agent, and commits to git.

    Returns:
        SeedResponse with success status and message.
    """
    return await _seed_upper_layer(
        layer_slug="policies",
        agent_role="policies-seed",
        template_name="policies",
        agent_label="Policies seed agent",
    )
