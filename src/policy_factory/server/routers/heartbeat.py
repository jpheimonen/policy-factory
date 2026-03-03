"""Heartbeat API router — manual trigger, history, and status endpoints.

Prefix: ``/api/heartbeat``
Tag: ``heartbeat``

All endpoints require JWT authentication.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from policy_factory.server.deps import (
    _get_heartbeat_interval_hours,
    get_data_dir,
    get_event_emitter,
    get_scheduler,
    get_store,
)
from policy_factory.store import PolicyStore
from policy_factory.store.auth import UserPublic

from ..deps import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/heartbeat", tags=["heartbeat"])


# ---------------------------------------------------------------------------
# POST /api/heartbeat/trigger — manually trigger a heartbeat run
# ---------------------------------------------------------------------------


@router.post("/trigger")
async def trigger_heartbeat(
    _current_user: Annotated[UserPublic, Depends(get_current_user)],
    store: Annotated[PolicyStore, Depends(get_store)],
) -> dict[str, Any]:
    """Manually trigger a heartbeat run.

    Launches the heartbeat orchestrator as a background asyncio task.
    Returns immediately with the heartbeat run ID.

    Returns 409 if a heartbeat is already running.
    """
    # Check concurrency guard
    if store.has_running_heartbeat():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A heartbeat is already running",
        )

    # Get dependencies
    emitter = get_event_emitter()
    data_dir = get_data_dir()

    # Import cascade trigger and idea generator
    cascade_trigger = None
    idea_generator = None

    try:
        from policy_factory.cascade.orchestrator import trigger_cascade
        cascade_trigger = trigger_cascade
    except ImportError:
        pass

    try:
        from policy_factory.ideas.generator import generate_ideas
        idea_generator = generate_ideas
    except ImportError:
        pass

    # Import and launch orchestrator as background task
    from policy_factory.heartbeat.orchestrator import run_heartbeat

    async def _run() -> None:
        try:
            await run_heartbeat(
                trigger="manual",
                store=store,
                emitter=emitter,
                data_dir=data_dir,
                cascade_trigger=cascade_trigger,
                idea_generator=idea_generator,
            )
        except Exception:
            logger.exception("Manual heartbeat run failed")

    asyncio.create_task(_run(), name="heartbeat-manual")

    return {
        "status": "started",
        "message": "Heartbeat run started in background",
    }


# ---------------------------------------------------------------------------
# GET /api/heartbeat/history — recent heartbeat runs
# ---------------------------------------------------------------------------


@router.get("/history")
async def get_heartbeat_history(
    _current_user: Annotated[UserPublic, Depends(get_current_user)],
    store: Annotated[PolicyStore, Depends(get_store)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[dict[str, Any]]:
    """Get recent heartbeat run history.

    Returns heartbeat runs in reverse chronological order with
    all fields including the full structured log.
    """
    runs = store.list_heartbeat_runs(limit=limit)
    return [_heartbeat_run_to_dict(run) for run in runs]


# ---------------------------------------------------------------------------
# GET /api/heartbeat/latest — most recent heartbeat run
# ---------------------------------------------------------------------------


@router.get("/latest")
async def get_latest_heartbeat(
    _current_user: Annotated[UserPublic, Depends(get_current_user)],
    store: Annotated[PolicyStore, Depends(get_store)],
) -> dict[str, Any] | None:
    """Get the most recent heartbeat run.

    Returns null if no heartbeat has ever run.
    """
    run = store.get_latest_heartbeat_run()
    if run is None:
        return None
    return _heartbeat_run_to_dict(run)


# ---------------------------------------------------------------------------
# GET /api/heartbeat/status — heartbeat system status
# ---------------------------------------------------------------------------


@router.get("/status")
async def get_heartbeat_status(
    _current_user: Annotated[UserPublic, Depends(get_current_user)],
    store: Annotated[PolicyStore, Depends(get_store)],
) -> dict[str, Any]:
    """Get heartbeat system status.

    Returns scheduler status, configured interval, next run time,
    whether a heartbeat is currently executing, and the most recent
    heartbeat run summary.
    """
    scheduler = get_scheduler()
    scheduler_active = scheduler is not None and scheduler.running if scheduler else False

    # Get next run time from the scheduler
    next_run_time = None
    if scheduler is not None and scheduler.running:
        job = scheduler.get_job("heartbeat")
        if job is not None and job.next_run_time is not None:
            next_run_time = job.next_run_time.isoformat()

    # Get configured interval
    interval_hours = _get_heartbeat_interval_hours()

    # Check if a heartbeat is currently running
    is_running = store.has_running_heartbeat()

    # Get latest run summary
    latest = store.get_latest_heartbeat_run()
    latest_summary = None
    if latest is not None:
        latest_summary = {
            "id": latest.id,
            "trigger": latest.trigger,
            "started_at": latest.started_at.isoformat(),
            "completed_at": latest.completed_at.isoformat() if latest.completed_at else None,
            "highest_tier": latest.highest_tier,
        }

    return {
        "scheduler_active": scheduler_active,
        "interval_hours": interval_hours,
        "next_run_time": next_run_time,
        "heartbeat_running": is_running,
        "latest_run": latest_summary,
    }


# ---------------------------------------------------------------------------
# GET /api/heartbeat/agent-run/{agent_run_id} — fetch a single agent run
# ---------------------------------------------------------------------------


@router.get("/agent-run/{agent_run_id}")
async def get_agent_run(
    agent_run_id: str,
    _current_user: Annotated[UserPublic, Depends(get_current_user)],
    store: Annotated[PolicyStore, Depends(get_store)],
) -> dict[str, Any]:
    """Fetch the full agent run record including output text.

    Enables the heartbeat log viewer UI to load agent transcripts
    on demand when a user expands a tier entry.
    """
    agent_run = store.get_agent_run(agent_run_id)
    if agent_run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent run not found: {agent_run_id}",
        )

    return {
        "id": agent_run.id,
        "cascade_id": agent_run.cascade_id,
        "agent_type": agent_run.agent_type,
        "agent_label": agent_run.agent_label,
        "model": agent_run.model,
        "target_layer": agent_run.target_layer,
        "started_at": agent_run.started_at.isoformat(),
        "completed_at": (
            agent_run.completed_at.isoformat() if agent_run.completed_at else None
        ),
        "success": agent_run.success,
        "error_message": agent_run.error_message,
        "cost_usd": agent_run.cost_usd,
        "output_text": agent_run.output_text,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _heartbeat_run_to_dict(run: Any) -> dict[str, Any]:
    """Convert a HeartbeatRun to a JSON-serialisable dict."""
    return {
        "id": run.id,
        "trigger": run.trigger,
        "started_at": run.started_at.isoformat(),
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "highest_tier": run.highest_tier,
        "structured_log": [
            {
                "tier": entry.tier,
                "escalated": entry.escalated,
                "outcome": entry.outcome,
                "agent_run_id": entry.agent_run_id,
                "started_at": entry.started_at,
                "ended_at": entry.ended_at,
            }
            for entry in run.structured_log
        ],
    }
