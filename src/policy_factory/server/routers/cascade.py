"""Cascade router — REST endpoints for triggering and controlling cascades.

Follows the cc-runner runs router pattern: POST endpoints trigger
background operations and return immediately, GET endpoints query status,
and POST control endpoints manage running/paused cascades.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel

from policy_factory.cascade.classifier import classify_input
from policy_factory.cascade.orchestrator import trigger_cascade
from policy_factory.data.layers import LAYER_SLUGS
from policy_factory.server.deps import (
    get_cascade_controller,
    get_current_user,
    get_data_dir,
    get_event_emitter,
    get_store,
)
from policy_factory.store.auth import UserPublic

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cascade", tags=["cascade"])


# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------


class TriggerInputRequest(BaseModel):
    """Request body for triggering a cascade from user input."""

    input_text: str


class RefreshLayerRequest(BaseModel):
    """Request body for triggering a layer refresh cascade."""

    layer_slug: str


class TriggerResponse(BaseModel):
    """Response for cascade trigger endpoints."""

    id: str
    is_cascade: bool  # True = cascade ID, False = queue entry ID
    classification: dict[str, Any] | None = None


class CascadeStatusResponse(BaseModel):
    """Response for the cascade status endpoint."""

    status: str  # running, paused, idle
    cascade_id: str | None = None
    current_layer: str | None = None
    current_step: str | None = None
    trigger_source: str | None = None
    started_at: str | None = None
    error_message: str | None = None
    queue_depth: int = 0
    queue_entries: list[dict[str, Any]] = []
    last_completed_id: str | None = None


class CascadeDetailResponse(BaseModel):
    """Response for the cascade detail endpoint."""

    id: str
    trigger_source: str
    starting_layer: str
    current_layer: str
    current_step: str
    status: str
    error_message: str | None
    error_layer: str | None
    context: str | None
    created_at: str
    completed_at: str | None
    agent_runs: list[dict[str, Any]]


class CascadeHistoryEntry(BaseModel):
    """A single entry in the cascade history list."""

    id: str
    trigger_source: str
    starting_layer: str
    status: str
    created_at: str
    completed_at: str | None


class MemoStatusUpdate(BaseModel):
    """Request body for updating a memo status."""

    status: str  # accepted or dismissed


# ---------------------------------------------------------------------------
# Trigger endpoints
# ---------------------------------------------------------------------------


@router.post("/trigger")
async def trigger_from_input(
    req: TriggerInputRequest,
    current_user: Annotated[UserPublic, Depends(get_current_user)],
) -> TriggerResponse:
    """Trigger a cascade from user input.

    Classifies the input to determine the target layer, then triggers
    a cascade. Classification is synchronous; cascade is asynchronous.
    """
    store = get_store()
    emitter = get_event_emitter()
    data_dir = get_data_dir()

    # Classify the input
    classification = await classify_input(
        user_input=req.input_text,
        store=store,
        emitter=emitter,
        data_dir=data_dir,
    )

    # Trigger the cascade
    result_id, is_cascade = await trigger_cascade(
        trigger_source="user_input",
        starting_layer=classification.target_layer,
        store=store,
        emitter=emitter,
        data_dir=data_dir,
        context=req.input_text,
    )

    return TriggerResponse(
        id=result_id,
        is_cascade=is_cascade,
        classification={
            "target_layer": classification.target_layer,
            "secondary_layers": classification.secondary_layers,
            "confidence": classification.confidence,
            "explanation": classification.explanation,
        },
    )


@router.post("/refresh")
async def trigger_refresh(
    req: RefreshLayerRequest,
    _current_user: Annotated[UserPublic, Depends(get_current_user)],
) -> TriggerResponse:
    """Trigger a cascade from a specific layer refresh.

    No classification needed — the user explicitly chose the layer.
    """
    # Validate layer slug
    if req.layer_slug not in LAYER_SLUGS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown layer: {req.layer_slug}",
        )

    store = get_store()
    emitter = get_event_emitter()
    data_dir = get_data_dir()

    result_id, is_cascade = await trigger_cascade(
        trigger_source="layer_refresh",
        starting_layer=req.layer_slug,
        store=store,
        emitter=emitter,
        data_dir=data_dir,
    )

    return TriggerResponse(id=result_id, is_cascade=is_cascade)


@router.post("/full")
async def trigger_full(
    _current_user: Annotated[UserPublic, Depends(get_current_user)],
) -> TriggerResponse:
    """Trigger a full cascade from the values layer."""
    store = get_store()
    emitter = get_event_emitter()
    data_dir = get_data_dir()

    result_id, is_cascade = await trigger_cascade(
        trigger_source="layer_refresh",
        starting_layer="values",
        store=store,
        emitter=emitter,
        data_dir=data_dir,
    )

    return TriggerResponse(id=result_id, is_cascade=is_cascade)


# ---------------------------------------------------------------------------
# Status and detail endpoints
# ---------------------------------------------------------------------------


@router.get("/status")
async def get_cascade_status(
    _current_user: Annotated[UserPublic, Depends(get_current_user)],
) -> CascadeStatusResponse:
    """Get the current cascade status.

    Returns whether a cascade is running/paused/idle, the queue depth,
    and queue entries.
    """
    store = get_store()

    # Check for active cascade
    active = store.get_active_cascade()
    queue = store.get_queue()

    # Find last completed cascade
    last_completed_id: str | None = None
    recent = store.list_cascades(limit=1, offset=0)
    for cascade in recent:
        if cascade.status in ("completed", "failed", "cancelled"):
            last_completed_id = cascade.id
            break

    if active is None:
        return CascadeStatusResponse(
            status="idle",
            queue_depth=len(queue),
            queue_entries=[
                {
                    "id": e.id,
                    "trigger_source": e.trigger_source,
                    "starting_layer": e.starting_layer,
                    "queued_at": e.queued_at.isoformat(),
                }
                for e in queue
            ],
            last_completed_id=last_completed_id,
        )

    return CascadeStatusResponse(
        status=active.status,
        cascade_id=active.id,
        current_layer=active.current_layer,
        current_step=active.current_step,
        trigger_source=active.trigger_source,
        started_at=active.created_at.isoformat(),
        error_message=active.error_message,
        queue_depth=len(queue),
        queue_entries=[
            {
                "id": e.id,
                "trigger_source": e.trigger_source,
                "starting_layer": e.starting_layer,
                "queued_at": e.queued_at.isoformat(),
            }
            for e in queue
        ],
        last_completed_id=last_completed_id,
    )


@router.get("/history")
async def get_cascade_history(
    _current_user: Annotated[UserPublic, Depends(get_current_user)],
    limit: int = 20,
    offset: int = 0,
    cascade_status: str | None = None,
) -> list[CascadeHistoryEntry]:
    """List recent cascade runs in reverse chronological order."""
    store = get_store()

    # Clamp limits
    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    cascades = store.list_cascades(limit=limit, offset=offset)

    # Filter by status if specified
    if cascade_status:
        cascades = [c for c in cascades if c.status == cascade_status]

    return [
        CascadeHistoryEntry(
            id=c.id,
            trigger_source=c.trigger_source,
            starting_layer=c.starting_layer,
            status=c.status,
            created_at=c.created_at.isoformat(),
            completed_at=c.completed_at.isoformat() if c.completed_at else None,
        )
        for c in cascades
    ]


@router.get("/{cascade_id}")
async def get_cascade_detail(
    cascade_id: str,
    _current_user: Annotated[UserPublic, Depends(get_current_user)],
) -> CascadeDetailResponse:
    """Get detailed cascade run information including agent runs."""
    store = get_store()

    cascade = store.get_cascade(cascade_id)
    if cascade is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cascade not found: {cascade_id}",
        )

    # Get associated agent runs
    agent_runs = store.list_agent_runs(cascade_id=cascade_id, limit=100)

    return CascadeDetailResponse(
        id=cascade.id,
        trigger_source=cascade.trigger_source,
        starting_layer=cascade.starting_layer,
        current_layer=cascade.current_layer,
        current_step=cascade.current_step,
        status=cascade.status,
        error_message=cascade.error_message,
        error_layer=cascade.error_layer,
        context=cascade.context,
        created_at=cascade.created_at.isoformat(),
        completed_at=cascade.completed_at.isoformat() if cascade.completed_at else None,
        agent_runs=[
            {
                "id": r.id,
                "agent_type": r.agent_type,
                "agent_label": r.agent_label,
                "model": r.model,
                "target_layer": r.target_layer,
                "started_at": r.started_at.isoformat(),
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                "success": r.success,
                "error_message": r.error_message,
                "cost_usd": r.cost_usd,
            }
            for r in agent_runs
        ],
    )


# ---------------------------------------------------------------------------
# Control endpoints
# ---------------------------------------------------------------------------


@router.post("/{cascade_id}/pause")
async def pause_cascade(
    cascade_id: str,
    _current_user: Annotated[UserPublic, Depends(get_current_user)],
) -> dict[str, Any]:
    """Pause a running cascade."""
    controller = get_cascade_controller(cascade_id)
    if controller is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Active cascade not found: {cascade_id}",
        )

    # Request pause — the orchestrator will handle the actual pause
    from policy_factory.cascade.controller import CascadeState

    if controller.state != CascadeState.RUNNING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cascade is not running (state: {controller.state.value})",
        )

    controller.request_pause()

    return {
        "cascade_id": cascade_id,
        "status": "pause_requested",
    }


@router.post("/{cascade_id}/resume")
async def resume_cascade(
    cascade_id: str,
    _current_user: Annotated[UserPublic, Depends(get_current_user)],
) -> dict[str, Any]:
    """Resume a paused cascade."""
    controller = get_cascade_controller(cascade_id)
    if controller is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Active cascade not found: {cascade_id}",
        )

    from policy_factory.cascade.controller import CascadeState

    if controller.state != CascadeState.PAUSED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cascade is not paused (state: {controller.state.value})",
        )

    success = await controller.resume()
    if not success:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Failed to resume cascade",
        )

    return {
        "cascade_id": cascade_id,
        "status": "resumed",
    }


@router.post("/{cascade_id}/cancel")
async def cancel_cascade(
    cascade_id: str,
    _current_user: Annotated[UserPublic, Depends(get_current_user)],
) -> dict[str, Any]:
    """Cancel a paused cascade."""
    controller = get_cascade_controller(cascade_id)
    if controller is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Active cascade not found: {cascade_id}",
        )

    from policy_factory.cascade.controller import CascadeState

    if controller.state != CascadeState.PAUSED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cascade is not paused (state: {controller.state.value})",
        )

    success = await controller.cancel()
    if not success:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Failed to cancel cascade",
        )

    return {
        "cascade_id": cascade_id,
        "status": "cancelled",
    }


# ---------------------------------------------------------------------------
# Queue management
# ---------------------------------------------------------------------------


@router.delete("/queue/{queue_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_queued_cascade(
    queue_id: str,
    _current_user: Annotated[UserPublic, Depends(get_current_user)],
) -> Response:
    """Remove a queued cascade entry."""
    store = get_store()

    removed = store.cancel_queued_cascade(queue_id)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Queue entry not found: {queue_id}",
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)
