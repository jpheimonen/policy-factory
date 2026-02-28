"""Feedback memo router — REST endpoints for viewing and managing feedback memos.

Provides endpoints for listing memos per layer and updating memo status
(accept/dismiss).
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from policy_factory.data.layers import LAYER_SLUGS
from policy_factory.server.deps import get_current_user, get_store
from policy_factory.store.auth import UserPublic

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class FeedbackMemoResponse(BaseModel):
    """Response for a single feedback memo."""

    id: str
    source_layer: str
    target_layer: str
    cascade_id: str | None
    content: str
    referenced_items: list[str]
    status: str
    created_at: str
    resolved_at: str | None


class MemoStatusUpdateRequest(BaseModel):
    """Request body for updating a memo's status."""

    status: str  # accepted or dismissed


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/{layer_slug}")
async def list_layer_memos(
    layer_slug: str,
    _current_user: Annotated[UserPublic, Depends(get_current_user)],
    memo_status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[FeedbackMemoResponse]:
    """List feedback memos for a layer.

    Args:
        layer_slug: The target layer slug.
        memo_status: Optional filter by status (pending, accepted, dismissed).
        limit: Maximum number of results (default 50).
        offset: Number of results to skip.
    """
    # Validate layer slug
    if layer_slug not in LAYER_SLUGS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown layer: {layer_slug}",
        )

    store = get_store()

    # Clamp limits
    limit = max(1, min(limit, 200))
    offset = max(0, offset)

    memos = store.list_memos(
        target_layer=layer_slug,
        memo_status=memo_status,
        limit=limit,
        offset=offset,
    )

    return [
        FeedbackMemoResponse(
            id=m.id,
            source_layer=m.source_layer,
            target_layer=m.target_layer,
            cascade_id=m.cascade_id,
            content=m.content,
            referenced_items=m.referenced_items,
            status=m.status,
            created_at=m.created_at.isoformat(),
            resolved_at=m.resolved_at.isoformat() if m.resolved_at else None,
        )
        for m in memos
    ]


@router.put("/{memo_id}")
async def update_memo_status(
    memo_id: str,
    req: MemoStatusUpdateRequest,
    _current_user: Annotated[UserPublic, Depends(get_current_user)],
) -> FeedbackMemoResponse:
    """Update a memo's status (accept or dismiss).

    Args:
        memo_id: The memo ID.
        req: Request body with new status.
    """
    store = get_store()

    # Validate status value
    if req.status not in ("accepted", "dismissed"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status: {req.status}. Must be 'accepted' or 'dismissed'.",
        )

    # Verify memo exists
    memo = store.get_memo(memo_id)
    if memo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memo not found: {memo_id}",
        )

    # Update status
    store.update_memo_status(memo_id, req.status)

    # Read back the updated memo
    updated = store.get_memo(memo_id)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve updated memo",
        )

    return FeedbackMemoResponse(
        id=updated.id,
        source_layer=updated.source_layer,
        target_layer=updated.target_layer,
        cascade_id=updated.cascade_id,
        content=updated.content,
        referenced_items=updated.referenced_items,
        status=updated.status,
        created_at=updated.created_at.isoformat(),
        resolved_at=updated.resolved_at.isoformat() if updated.resolved_at else None,
    )
