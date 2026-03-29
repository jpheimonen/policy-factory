"""Conversations router — REST endpoints for conversation management.

Provides endpoints for:
- Creating conversations for items or layers (POST /)
- Listing conversations filtered by layer/item (GET /)
- Getting conversation details with messages (GET /{id})
- Sending messages and triggering AI response (POST /{id}/messages)
- Deleting conversations (DELETE /{id})

All endpoints require JWT authentication. The message-sending endpoint
launches the conversation runner as a background task and streams the
AI response via WebSocket events.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from policy_factory.data.layers import LAYER_SLUGS, read_item
from policy_factory.server.deps import (
    get_current_user,
    get_data_dir,
    get_event_emitter,
    get_store,
)
from policy_factory.store.auth import UserPublic

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class CreateConversationRequest(BaseModel):
    """Request body for creating a conversation."""

    layer_slug: str
    filename: str | None = None


class ConversationResponse(BaseModel):
    """Response model for a conversation."""

    id: str
    layer_slug: str
    filename: str | None
    created_at: str  # ISO8601
    last_active_at: str  # ISO8601


class ConversationListResponse(BaseModel):
    """Response model for listing conversations."""

    conversations: list[ConversationResponse]


class MessageResponse(BaseModel):
    """Response model for a message."""

    id: str
    role: str  # "user" or "assistant"
    content: str
    created_at: str  # ISO8601
    files_edited: list[str] | None


class ConversationDetailResponse(BaseModel):
    """Response model for conversation with messages."""

    conversation: ConversationResponse
    messages: list[MessageResponse]


class SendMessageRequest(BaseModel):
    """Request body for sending a message."""

    content: str


class SendMessageResponse(BaseModel):
    """Response after sending a message.

    Note: The assistant response streams via WebSocket events.
    """

    message_id: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    req: CreateConversationRequest,
    current_user: Annotated[UserPublic, Depends(get_current_user)],
) -> ConversationResponse:
    """Create a new conversation for an item or layer.

    If filename is provided, creates an item-level conversation.
    If filename is omitted, creates a layer-level conversation.

    Returns 400 if the layer_slug is invalid or item doesn't exist.
    """
    store = get_store()
    data_dir = get_data_dir()

    # Validate layer_slug
    if req.layer_slug not in LAYER_SLUGS:
        valid_slugs = ", ".join(sorted(LAYER_SLUGS))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid layer_slug: {req.layer_slug!r}. Valid slugs: {valid_slugs}",
        )

    # If filename is provided, validate that the item exists
    if req.filename:
        try:
            read_item(data_dir, req.layer_slug, req.filename)
        except FileNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Item not found: {req.layer_slug}/{req.filename}",
            )

    # Create the conversation
    conversation_id = store.create_conversation(
        layer_slug=req.layer_slug,
        filename=req.filename,
    )

    # Fetch the created conversation to get timestamps
    conversation = store.get_conversation(conversation_id)
    if conversation is None:
        # Should not happen, but handle gracefully
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create conversation",
        )

    return ConversationResponse(
        id=conversation.id,
        layer_slug=conversation.layer_slug,
        filename=conversation.filename,
        created_at=conversation.created_at.isoformat(),
        last_active_at=conversation.last_active_at.isoformat(),
    )


@router.get("/", response_model=ConversationListResponse)
async def list_conversations(
    layer_slug: str,
    current_user: Annotated[UserPublic, Depends(get_current_user)],
    filename: str | None = None,
) -> ConversationListResponse:
    """List conversations filtered by layer_slug and optional filename.

    If filename is provided, returns item-level conversations.
    If filename is omitted, returns layer-level conversations (where filename is null).
    """
    store = get_store()

    # Validate layer_slug
    if layer_slug not in LAYER_SLUGS:
        valid_slugs = ", ".join(sorted(LAYER_SLUGS))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid layer_slug: {layer_slug!r}. Valid slugs: {valid_slugs}",
        )

    # List conversations based on whether filename is provided
    if filename:
        conversations = store.list_conversations_for_item(layer_slug, filename)
    else:
        conversations = store.list_conversations_for_layer(layer_slug)

    return ConversationListResponse(
        conversations=[
            ConversationResponse(
                id=conv.id,
                layer_slug=conv.layer_slug,
                filename=conv.filename,
                created_at=conv.created_at.isoformat(),
                last_active_at=conv.last_active_at.isoformat(),
            )
            for conv in conversations
        ]
    )


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: str,
    current_user: Annotated[UserPublic, Depends(get_current_user)],
) -> ConversationDetailResponse:
    """Get a conversation with all its messages.

    Returns 404 if the conversation doesn't exist.
    """
    store = get_store()

    conversation = store.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation not found: {conversation_id}",
        )

    messages = store.get_messages(conversation_id)

    return ConversationDetailResponse(
        conversation=ConversationResponse(
            id=conversation.id,
            layer_slug=conversation.layer_slug,
            filename=conversation.filename,
            created_at=conversation.created_at.isoformat(),
            last_active_at=conversation.last_active_at.isoformat(),
        ),
        messages=[
            MessageResponse(
                id=msg.id,
                role=msg.role,
                content=msg.content,
                created_at=msg.created_at.isoformat(),
                files_edited=msg.files_edited,
            )
            for msg in messages
        ],
    )


@router.post(
    "/{conversation_id}/messages",
    response_model=SendMessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def send_message(
    conversation_id: str,
    req: SendMessageRequest,
    current_user: Annotated[UserPublic, Depends(get_current_user)],
) -> SendMessageResponse:
    """Send a user message and trigger the AI response.

    Stores the user message immediately and launches the conversation
    runner as a background task. The AI response streams via WebSocket
    events (ConversationTextChunk, ConversationTurnComplete, etc.).

    Returns 202 Accepted with the user message ID.
    Returns 404 if the conversation doesn't exist.
    """
    store = get_store()
    emitter = get_event_emitter()
    data_dir = get_data_dir()

    # Verify conversation exists
    conversation = store.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation not found: {conversation_id}",
        )

    # Store the user message immediately
    message_id = store.add_message(conversation_id, "user", req.content)

    # Launch the conversation runner as a background task
    async def _background_conversation_turn() -> None:
        try:
            from policy_factory.conversation.runner import run_conversation_turn

            await run_conversation_turn(
                conversation_id=conversation_id,
                user_content=req.content,
                store=store,
                emitter=emitter,
                data_dir=data_dir,
            )
        except Exception:
            logger.exception(
                "Background conversation turn failed for conversation %s",
                conversation_id,
            )

    asyncio.create_task(_background_conversation_turn())

    return SendMessageResponse(message_id=message_id)


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: str,
    current_user: Annotated[UserPublic, Depends(get_current_user)],
) -> None:
    """Delete a conversation and all its messages.

    Returns 204 No Content on success.
    Returns 404 if the conversation doesn't exist.
    """
    store = get_store()

    deleted = store.delete_conversation(conversation_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation not found: {conversation_id}",
        )

    # No return value — 204 No Content
    return None
