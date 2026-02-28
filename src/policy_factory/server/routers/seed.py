"""Seed router — initial Situational Awareness population.

The seed endpoint triggers a special agent that uses web search to
research Finland's current tech policy landscape and populates the
Situational Awareness layer. After seeding, an upward cascade is
triggered from SA through the remaining layers.

Seeding is a one-time operation for initial system setup.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from policy_factory.cascade.orchestrator import trigger_cascade
from policy_factory.data.git import commit_changes
from policy_factory.data.layers import list_items
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
# Endpoints
# ---------------------------------------------------------------------------


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
