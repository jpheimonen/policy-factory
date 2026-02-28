"""Activity router — event feed and WebSocket reconnection replay.

Provides:
- ``GET /api/activity/``  — recent events for the activity feed page.
- ``GET /api/activity/replay`` — events since a given ID for reconnection.

All endpoints require JWT authentication.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from policy_factory.server.deps import get_current_user, get_store
from policy_factory.store import PolicyStore
from policy_factory.store.auth import UserPublic

router = APIRouter(prefix="/api/activity", tags=["activity"])


def _serialize_event(e: Any) -> dict[str, Any]:
    """Convert a stored event to its API response dict."""
    return {
        "id": e.id,
        "event_type": e.event_type,
        "timestamp": e.timestamp.isoformat(),
        "data": e.data,
        "layer_slug": e.layer_slug,
        "category": e.category,
    }


@router.get("/")
async def get_activity(
    _current_user: Annotated[UserPublic, Depends(get_current_user)],
    store: Annotated[PolicyStore, Depends(get_store)],
    event_type: Annotated[str | None, Query()] = None,
    layer: Annotated[str | None, Query()] = None,
    category: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    """Return recent events for the activity feed.

    Events are returned in reverse chronological order (newest first).
    Supports optional filtering by event_type, layer, and category,
    plus pagination via limit/offset.
    """
    events = store.get_recent_events(
        limit=limit,
        offset=offset,
        event_type=event_type,
        layer_slug=layer,
        category=category,
    )
    return {
        "events": [_serialize_event(e) for e in events],
        "limit": limit,
        "offset": offset,
    }


@router.get("/replay")
async def replay_events(
    _current_user: Annotated[UserPublic, Depends(get_current_user)],
    store: Annotated[PolicyStore, Depends(get_store)],
    since_id: Annotated[int, Query(ge=0)],
    event_type: Annotated[str | None, Query()] = None,
    layer: Annotated[str | None, Query()] = None,
    category: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    """Return events since a given ID for WebSocket reconnection replay.

    Events are returned in chronological order (oldest first) so the
    client can process them in sequence. Limited to 500 events — if
    more were missed, the client should do a full store refresh.
    """
    events = store.get_events(
        since_id=since_id,
        event_type=event_type,
        layer_slug=layer,
        category=category,
        limit=500,
    )
    return {
        "events": [_serialize_event(e) for e in events],
        "since_id": since_id,
        "overflow": len(events) >= 500,
    }
