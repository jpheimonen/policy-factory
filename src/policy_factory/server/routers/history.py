"""History router — git commit history per layer."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from policy_factory.data.git import get_layer_history
from policy_factory.data.layers import get_layer
from policy_factory.server.deps import get_current_user, get_data_dir
from policy_factory.store.auth import UserPublic

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/history", tags=["history"])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class CommitResponse(BaseModel):
    """A single git commit entry."""

    hash: str
    timestamp: str
    message: str
    author: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/{slug}")
async def get_history(
    slug: str,
    data_dir: Annotated[Path, Depends(get_data_dir)],
    _current_user: Annotated[UserPublic, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[CommitResponse]:
    """Get recent git history for a layer.

    Returns a list of commit entries, each with: commit hash (short),
    timestamp (ISO 8601), commit message, and author name.

    Returns an empty list if no commits exist for that layer.
    """
    layer = get_layer(slug)
    if layer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown layer: {slug}",
        )

    entries = get_layer_history(data_dir, slug, limit=limit)

    return [
        CommitResponse(
            hash=entry.hash[:7],  # Short hash
            timestamp=entry.timestamp,
            message=entry.message,
            author=entry.author,
        )
        for entry in entries
    ]
