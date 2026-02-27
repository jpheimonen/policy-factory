"""Layers router — CRUD for layer items, narrative summaries, and cross-layer references."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel

from policy_factory.data.git import commit_changes
from policy_factory.data.layers import (
    LAYERS,
    delete_item,
    get_layer,
    list_items,
    read_item,
    read_narrative,
    resolve_references,
    write_item,
)
from policy_factory.server.deps import get_current_user, get_data_dir
from policy_factory.store.auth import UserPublic

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/layers", tags=["layers"])


# ---------------------------------------------------------------------------
# Input validation helpers
# ---------------------------------------------------------------------------


def _validate_slug(slug: str) -> None:
    """Validate a layer slug against the known list.

    Raises:
        HTTPException 404: If the slug is not a valid layer.
    """
    layer = get_layer(slug)
    if layer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown layer: {slug}",
        )


def _validate_filename(filename: str) -> None:
    """Validate a filename for path traversal and format.

    Raises:
        HTTPException 400: If the filename is invalid.
    """
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename: path traversal not allowed",
        )
    if not filename.endswith(".md"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename must end in .md",
        )
    if filename.lower() == "readme.md":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot use README.md as an item filename",
        )


def _try_git_commit(data_dir: Path, message: str, user_email: str) -> None:
    """Attempt a git commit, logging warnings on failure.

    A failed git commit does NOT cause the API request to fail — the
    file change has already been persisted.
    """
    try:
        # Temporarily set author identity for this commit
        old_author = os.environ.get("POLICY_FACTORY_GIT_AUTHOR")
        old_email = os.environ.get("POLICY_FACTORY_GIT_EMAIL")
        os.environ["POLICY_FACTORY_GIT_AUTHOR"] = f"User ({user_email})"
        os.environ["POLICY_FACTORY_GIT_EMAIL"] = user_email
        try:
            commit_changes(data_dir, message)
        finally:
            # Restore original env vars
            if old_author is not None:
                os.environ["POLICY_FACTORY_GIT_AUTHOR"] = old_author
            elif "POLICY_FACTORY_GIT_AUTHOR" in os.environ:
                del os.environ["POLICY_FACTORY_GIT_AUTHOR"]
            if old_email is not None:
                os.environ["POLICY_FACTORY_GIT_EMAIL"] = old_email
            elif "POLICY_FACTORY_GIT_EMAIL" in os.environ:
                del os.environ["POLICY_FACTORY_GIT_EMAIL"]
    except Exception:
        logger.warning("Git commit failed for: %s", message, exc_info=True)


# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------


class ItemCreateRequest(BaseModel):
    """Request body for creating a new item."""

    filename: str
    frontmatter: dict[str, Any] = {}
    body: str = ""


class ItemUpdateRequest(BaseModel):
    """Request body for updating an existing item."""

    frontmatter: dict[str, Any] = {}
    body: str = ""


class ItemResponse(BaseModel):
    """Response for a single item (frontmatter + body)."""

    filename: str
    frontmatter: dict[str, Any]
    body: str


class ItemSummaryResponse(BaseModel):
    """Response for an item in a listing."""

    filename: str
    title: str
    status: str
    last_modified: str
    last_modified_by: str


class LayerSummaryResponse(BaseModel):
    """Response for a layer in the list-all-layers endpoint."""

    slug: str
    display_name: str
    position: int
    item_count: int
    last_updated: str
    narrative_preview: str
    pending_feedback_count: int


class ReferenceResponse(BaseModel):
    """A single cross-layer reference."""

    layer_slug: str
    filename: str
    title: str


class ReferencesResponse(BaseModel):
    """Response for the cross-layer references endpoint."""

    forward: list[ReferenceResponse]
    backward: list[ReferenceResponse]


class SummaryResponse(BaseModel):
    """Response for the narrative summary endpoint."""

    content: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/")
async def list_layers(
    data_dir: Annotated[Path, Depends(get_data_dir)],
    _current_user: Annotated[UserPublic, Depends(get_current_user)],
) -> list[LayerSummaryResponse]:
    """List all 5 layers with metadata.

    Returns layers in hierarchical order (values at position 0, policies at position 4).
    """
    result: list[LayerSummaryResponse] = []

    for layer in LAYERS:
        items = list_items(data_dir, layer.slug)

        # Determine last updated from most recently modified item
        last_updated = ""
        if items:
            # Find the most recent last_modified among items
            dates = [i.last_modified for i in items if i.last_modified]
            if dates:
                last_updated = max(dates)

        # Get narrative summary preview (first ~200 chars)
        narrative = read_narrative(data_dir, layer.slug)
        narrative_preview = narrative[:200] if narrative else ""

        result.append(
            LayerSummaryResponse(
                slug=layer.slug,
                display_name=layer.display_name,
                position=layer.position,
                item_count=len(items),
                last_updated=last_updated,
                narrative_preview=narrative_preview,
                pending_feedback_count=0,  # Hardcoded until step 017
            )
        )

    return result


@router.get("/{slug}/items")
async def list_layer_items(
    slug: str,
    data_dir: Annotated[Path, Depends(get_data_dir)],
    _current_user: Annotated[UserPublic, Depends(get_current_user)],
) -> list[ItemSummaryResponse]:
    """List all items in a layer with summary metadata from frontmatter."""
    _validate_slug(slug)
    items = list_items(data_dir, slug)
    return [
        ItemSummaryResponse(
            filename=item.filename,
            title=item.title,
            status=item.status,
            last_modified=item.last_modified,
            last_modified_by=item.last_modified_by,
        )
        for item in items
    ]


@router.get("/{slug}/items/{filename}")
async def get_item(
    slug: str,
    filename: str,
    data_dir: Annotated[Path, Depends(get_data_dir)],
    _current_user: Annotated[UserPublic, Depends(get_current_user)],
) -> ItemResponse:
    """Get a single item (frontmatter + body)."""
    _validate_slug(slug)
    _validate_filename(filename)

    try:
        frontmatter, body = read_item(data_dir, slug, filename)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item not found: {filename}",
        )

    return ItemResponse(filename=filename, frontmatter=frontmatter, body=body)


@router.put("/{slug}/items/{filename}")
async def update_item(
    slug: str,
    filename: str,
    req: ItemUpdateRequest,
    data_dir: Annotated[Path, Depends(get_data_dir)],
    current_user: Annotated[UserPublic, Depends(get_current_user)],
) -> ItemResponse:
    """Update an existing item."""
    _validate_slug(slug)
    _validate_filename(filename)

    # Verify the file exists
    try:
        read_item(data_dir, slug, filename)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item not found: {filename}",
        )

    # Write the updated content (auto-stamps last_modified and last_modified_by)
    write_item(
        data_dir,
        slug,
        filename,
        req.frontmatter,
        req.body,
        modified_by=current_user.email,
    )

    # Git commit (non-blocking on failure)
    layer = get_layer(slug)
    display_name = layer.display_name if layer else slug
    _try_git_commit(
        data_dir,
        f"Update {filename} in {display_name}",
        current_user.email,
    )

    # Read back the written content (includes auto-stamped fields)
    frontmatter, body = read_item(data_dir, slug, filename)
    return ItemResponse(filename=filename, frontmatter=frontmatter, body=body)


@router.post("/{slug}/items", status_code=status.HTTP_201_CREATED)
async def create_item(
    slug: str,
    req: ItemCreateRequest,
    data_dir: Annotated[Path, Depends(get_data_dir)],
    current_user: Annotated[UserPublic, Depends(get_current_user)],
) -> ItemResponse:
    """Create a new item in a layer."""
    _validate_slug(slug)
    _validate_filename(req.filename)

    # Check if file already exists
    layer_dir = data_dir / slug
    target = layer_dir / req.filename
    if target.exists():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Item already exists: {req.filename}",
        )

    # Set created_at in frontmatter
    fm = dict(req.frontmatter)
    fm["created_at"] = datetime.now(timezone.utc).isoformat()

    # Write the item (auto-stamps last_modified and last_modified_by)
    write_item(
        data_dir,
        slug,
        req.filename,
        fm,
        req.body,
        modified_by=current_user.email,
    )

    # Git commit (non-blocking on failure)
    layer = get_layer(slug)
    display_name = layer.display_name if layer else slug
    _try_git_commit(
        data_dir,
        f"Create {req.filename} in {display_name}",
        current_user.email,
    )

    # Read back the written content
    frontmatter, body = read_item(data_dir, slug, req.filename)
    return ItemResponse(filename=req.filename, frontmatter=frontmatter, body=body)


@router.delete("/{slug}/items/{filename}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_layer_item(
    slug: str,
    filename: str,
    data_dir: Annotated[Path, Depends(get_data_dir)],
    current_user: Annotated[UserPublic, Depends(get_current_user)],
) -> Response:
    """Delete an item from a layer."""
    _validate_slug(slug)
    _validate_filename(filename)

    # Verify the file exists
    layer_dir = data_dir / slug
    target = layer_dir / filename
    if not target.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item not found: {filename}",
        )

    delete_item(data_dir, slug, filename)

    # Git commit (non-blocking on failure)
    layer = get_layer(slug)
    display_name = layer.display_name if layer else slug
    _try_git_commit(
        data_dir,
        f"Delete {filename} from {display_name}",
        current_user.email,
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{slug}/summary")
async def get_summary(
    slug: str,
    data_dir: Annotated[Path, Depends(get_data_dir)],
    _current_user: Annotated[UserPublic, Depends(get_current_user)],
) -> SummaryResponse:
    """Get the narrative summary (README.md) for a layer.

    Returns an empty string if README.md doesn't exist (not a 404).
    """
    _validate_slug(slug)
    content = read_narrative(data_dir, slug)
    return SummaryResponse(content=content)


@router.get("/{slug}/items/{filename}/references")
async def get_references(
    slug: str,
    filename: str,
    data_dir: Annotated[Path, Depends(get_data_dir)],
    _current_user: Annotated[UserPublic, Depends(get_current_user)],
) -> ReferencesResponse:
    """Get cross-layer references for an item."""
    _validate_slug(slug)
    _validate_filename(filename)

    # Verify the item exists
    try:
        read_item(data_dir, slug, filename)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item not found: {filename}",
        )

    forward, backward = resolve_references(data_dir, slug, filename)

    return ReferencesResponse(
        forward=[
            ReferenceResponse(
                layer_slug=ref.layer_slug,
                filename=ref.filename,
                title=ref.title,
            )
            for ref in forward
        ],
        backward=[
            ReferenceResponse(
                layer_slug=ref.layer_slug,
                filename=ref.filename,
                title=ref.title,
            )
            for ref in backward
        ],
    )
