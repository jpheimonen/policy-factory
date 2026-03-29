"""Event system for Policy Factory — typed events and async EventEmitter.

Provides:
- Typed dataclass events for all event categories (cascade, layer, agent,
  heartbeat, ideas, system).
- An EventEmitter with async-safe pub/sub for decoupled event dispatch.

Follows the cc-runner EventEmitter pattern with Policy Factory-specific
event types.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Literal

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Event type literals
# ---------------------------------------------------------------------------

EventCategory = Literal["cascade", "conversation", "heartbeat", "idea", "seed", "system"]

EventType = Literal[
    # Cascade lifecycle (7)
    "cascade_started",
    "cascade_completed",
    "cascade_failed",
    "cascade_paused",
    "cascade_resumed",
    "cascade_cancelled",
    "cascade_queued",
    # Layer processing (6)
    "layer_generation_started",
    "layer_generation_completed",
    "critic_started",
    "critic_completed",
    "synthesis_started",
    "synthesis_completed",
    # Agent streaming (1)
    "agent_text_chunk",
    # Heartbeat (3)
    "heartbeat_started",
    "heartbeat_tier_completed",
    "heartbeat_completed",
    # Seed progress (3)
    "seed_started",
    "seed_progress",
    "seed_completed",
    # Ideas (5)
    "idea_submitted",
    "idea_evaluation_started",
    "idea_evaluation_completed",
    "idea_generation_started",
    "idea_generation_completed",
    # System (4)
    "user_login",
    "user_created",
    "cascade_lock_acquired",
    "cascade_lock_released",
    # Conversation (6)
    "conversation_started",
    "conversation_text_chunk",
    "conversation_file_edit",
    "conversation_turn_complete",
    "conversation_cascade_pending",
    "conversation_turn_error",
]

# Mapping from event_type → category for efficient filtering
_EVENT_CATEGORY_MAP: dict[str, EventCategory] = {
    # Cascade lifecycle
    "cascade_started": "cascade",
    "cascade_completed": "cascade",
    "cascade_failed": "cascade",
    "cascade_paused": "cascade",
    "cascade_resumed": "cascade",
    "cascade_cancelled": "cascade",
    "cascade_queued": "cascade",
    # Layer processing (part of cascade)
    "layer_generation_started": "cascade",
    "layer_generation_completed": "cascade",
    "critic_started": "cascade",
    "critic_completed": "cascade",
    "synthesis_started": "cascade",
    "synthesis_completed": "cascade",
    # Agent streaming (part of cascade)
    "agent_text_chunk": "cascade",
    # Heartbeat
    "heartbeat_started": "heartbeat",
    "heartbeat_tier_completed": "heartbeat",
    "heartbeat_completed": "heartbeat",
    # Seed
    "seed_started": "seed",
    "seed_progress": "seed",
    "seed_completed": "seed",
    # Ideas
    "idea_submitted": "idea",
    "idea_evaluation_started": "idea",
    "idea_evaluation_completed": "idea",
    "idea_generation_started": "idea",
    "idea_generation_completed": "idea",
    # System
    "user_login": "system",
    "user_created": "system",
    "cascade_lock_acquired": "system",
    "cascade_lock_released": "system",
    # Conversation
    "conversation_started": "conversation",
    "conversation_text_chunk": "conversation",
    "conversation_file_edit": "conversation",
    "conversation_turn_complete": "conversation",
    "conversation_cascade_pending": "conversation",
    "conversation_turn_error": "conversation",
}


def get_event_category(event_type: str) -> EventCategory | None:
    """Return the category for a given event type string."""
    return _EVENT_CATEGORY_MAP.get(event_type)


# ---------------------------------------------------------------------------
# Base event
# ---------------------------------------------------------------------------


@dataclass
class BaseEvent:
    """Base class for all Policy Factory events.

    Each event has:
    - A unique ``id`` (UUID, generated on creation) for client deduplication.
    - A ``timestamp`` (UTC datetime, serialised to ISO 8601).
    - An ``event_type`` string set by each subclass (not passed by caller).
    """

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = field(init=False)  # Set by subclass

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dictionary of this event."""
        return {
            "id": self.id,
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
        }


# ---------------------------------------------------------------------------
# Cascade lifecycle events (7)
# ---------------------------------------------------------------------------


@dataclass
class CascadeStarted(BaseEvent):
    """Emitted when a cascade begins."""

    cascade_id: str = ""
    trigger_source: str = ""  # user_input, layer_refresh, heartbeat, seed
    starting_layer: str = ""
    event_type: str = field(default="cascade_started", init=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            **super().to_dict(),
            "cascade_id": self.cascade_id,
            "trigger_source": self.trigger_source,
            "starting_layer": self.starting_layer,
        }


@dataclass
class CascadeCompleted(BaseEvent):
    """Emitted when a cascade completes successfully."""

    cascade_id: str = ""
    success: bool = True
    event_type: str = field(default="cascade_completed", init=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            **super().to_dict(),
            "cascade_id": self.cascade_id,
            "success": self.success,
        }


@dataclass
class CascadeFailed(BaseEvent):
    """Emitted when a cascade fails."""

    cascade_id: str = ""
    error: str = ""
    failed_layer: str = ""
    failed_step: str = ""  # generation, critics, synthesis
    event_type: str = field(default="cascade_failed", init=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            **super().to_dict(),
            "cascade_id": self.cascade_id,
            "error": self.error,
            "failed_layer": self.failed_layer,
            "failed_step": self.failed_step,
        }


@dataclass
class CascadePaused(BaseEvent):
    """Emitted when a cascade is paused due to error."""

    cascade_id: str = ""
    error: str = ""
    paused_layer: str = ""
    paused_step: str = ""
    event_type: str = field(default="cascade_paused", init=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            **super().to_dict(),
            "cascade_id": self.cascade_id,
            "error": self.error,
            "paused_layer": self.paused_layer,
            "paused_step": self.paused_step,
        }


@dataclass
class CascadeResumed(BaseEvent):
    """Emitted when a paused cascade is resumed."""

    cascade_id: str = ""
    event_type: str = field(default="cascade_resumed", init=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            **super().to_dict(),
            "cascade_id": self.cascade_id,
        }


@dataclass
class CascadeCancelled(BaseEvent):
    """Emitted when a cascade is cancelled."""

    cascade_id: str = ""
    event_type: str = field(default="cascade_cancelled", init=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            **super().to_dict(),
            "cascade_id": self.cascade_id,
        }


@dataclass
class CascadeQueued(BaseEvent):
    """Emitted when a cascade is added to the queue."""

    cascade_id: str = ""
    queue_position: int = 0
    event_type: str = field(default="cascade_queued", init=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            **super().to_dict(),
            "cascade_id": self.cascade_id,
            "queue_position": self.queue_position,
        }


# ---------------------------------------------------------------------------
# Layer processing events (6)
# ---------------------------------------------------------------------------


@dataclass
class LayerGenerationStarted(BaseEvent):
    """Emitted when layer generation begins."""

    cascade_id: str = ""
    layer_slug: str = ""
    event_type: str = field(default="layer_generation_started", init=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            **super().to_dict(),
            "cascade_id": self.cascade_id,
            "layer_slug": self.layer_slug,
        }


@dataclass
class LayerGenerationCompleted(BaseEvent):
    """Emitted when layer generation completes."""

    cascade_id: str = ""
    layer_slug: str = ""
    event_type: str = field(default="layer_generation_completed", init=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            **super().to_dict(),
            "cascade_id": self.cascade_id,
            "layer_slug": self.layer_slug,
        }


@dataclass
class CriticStarted(BaseEvent):
    """Emitted when a critic agent starts."""

    cascade_id: str = ""
    layer_slug: str = ""
    critic_archetype: str = ""  # e.g. "realist", "liberal-institutionalist"
    event_type: str = field(default="critic_started", init=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            **super().to_dict(),
            "cascade_id": self.cascade_id,
            "layer_slug": self.layer_slug,
            "critic_archetype": self.critic_archetype,
        }


@dataclass
class CriticCompleted(BaseEvent):
    """Emitted when a critic agent completes."""

    cascade_id: str = ""
    layer_slug: str = ""
    critic_archetype: str = ""
    event_type: str = field(default="critic_completed", init=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            **super().to_dict(),
            "cascade_id": self.cascade_id,
            "layer_slug": self.layer_slug,
            "critic_archetype": self.critic_archetype,
        }


@dataclass
class SynthesisStarted(BaseEvent):
    """Emitted when synthesis begins."""

    cascade_id: str = ""
    layer_slug: str = ""
    event_type: str = field(default="synthesis_started", init=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            **super().to_dict(),
            "cascade_id": self.cascade_id,
            "layer_slug": self.layer_slug,
        }


@dataclass
class SynthesisCompleted(BaseEvent):
    """Emitted when synthesis completes."""

    cascade_id: str = ""
    layer_slug: str = ""
    event_type: str = field(default="synthesis_completed", init=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            **super().to_dict(),
            "cascade_id": self.cascade_id,
            "layer_slug": self.layer_slug,
        }


# ---------------------------------------------------------------------------
# Agent streaming events (1)
# ---------------------------------------------------------------------------


@dataclass
class AgentTextChunk(BaseEvent):
    """High-frequency event carrying streamed agent reasoning text."""

    cascade_id: str = ""  # Or other context ID
    agent_label: str = ""  # Human-readable, e.g. "Realist critic"
    text: str = ""
    event_type: str = field(default="agent_text_chunk", init=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            **super().to_dict(),
            "cascade_id": self.cascade_id,
            "agent_label": self.agent_label,
            "text": self.text,
        }


# ---------------------------------------------------------------------------
# Heartbeat events (3)
# ---------------------------------------------------------------------------


@dataclass
class HeartbeatStarted(BaseEvent):
    """Emitted when a heartbeat run begins."""

    heartbeat_run_id: str = ""
    event_type: str = field(default="heartbeat_started", init=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            **super().to_dict(),
            "heartbeat_run_id": self.heartbeat_run_id,
        }


@dataclass
class HeartbeatTierCompleted(BaseEvent):
    """Emitted when a heartbeat tier completes."""

    heartbeat_run_id: str = ""
    tier: int = 0
    outcome: str = ""
    escalated: bool = False
    event_type: str = field(default="heartbeat_tier_completed", init=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            **super().to_dict(),
            "heartbeat_run_id": self.heartbeat_run_id,
            "tier": self.tier,
            "outcome": self.outcome,
            "escalated": self.escalated,
        }


@dataclass
class HeartbeatCompleted(BaseEvent):
    """Emitted when a heartbeat run completes."""

    heartbeat_run_id: str = ""
    highest_tier: int = 0
    event_type: str = field(default="heartbeat_completed", init=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            **super().to_dict(),
            "heartbeat_run_id": self.heartbeat_run_id,
            "highest_tier": self.highest_tier,
        }


# ---------------------------------------------------------------------------
# Seed progress events (3)
# ---------------------------------------------------------------------------


@dataclass
class SeedStarted(BaseEvent):
    """Emitted when a seed operation begins for a layer."""

    layer_slug: str = ""
    agent_label: str = ""
    event_type: str = field(default="seed_started", init=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            **super().to_dict(),
            "layer_slug": self.layer_slug,
            "agent_label": self.agent_label,
        }


@dataclass
class SeedProgress(BaseEvent):
    """Emitted at key milestones during a seed operation."""

    layer_slug: str = ""
    step: str = ""  # agent_running, parsing, writing, committing, cascade
    message: str = ""
    event_type: str = field(default="seed_progress", init=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            **super().to_dict(),
            "layer_slug": self.layer_slug,
            "step": self.step,
            "message": self.message,
        }


@dataclass
class SeedCompleted(BaseEvent):
    """Emitted when a seed operation finishes (success or failure)."""

    layer_slug: str = ""
    success: bool = True
    message: str = ""
    items_created: int = 0
    event_type: str = field(default="seed_completed", init=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            **super().to_dict(),
            "layer_slug": self.layer_slug,
            "success": self.success,
            "message": self.message,
            "items_created": self.items_created,
        }


# ---------------------------------------------------------------------------
# Idea events (5)
# ---------------------------------------------------------------------------


@dataclass
class IdeaSubmitted(BaseEvent):
    """Emitted when an idea is submitted."""

    idea_id: str = ""
    source: str = ""  # "human" or "AI"
    event_type: str = field(default="idea_submitted", init=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            **super().to_dict(),
            "idea_id": self.idea_id,
            "source": self.source,
        }


@dataclass
class IdeaEvaluationStarted(BaseEvent):
    """Emitted when idea evaluation begins."""

    idea_id: str = ""
    event_type: str = field(default="idea_evaluation_started", init=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            **super().to_dict(),
            "idea_id": self.idea_id,
        }


@dataclass
class IdeaEvaluationCompleted(BaseEvent):
    """Emitted when idea evaluation completes."""

    idea_id: str = ""
    event_type: str = field(default="idea_evaluation_completed", init=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            **super().to_dict(),
            "idea_id": self.idea_id,
        }


@dataclass
class IdeaGenerationStarted(BaseEvent):
    """Emitted when batch idea generation begins."""

    event_type: str = field(default="idea_generation_started", init=False)

    def to_dict(self) -> dict[str, Any]:
        return {**super().to_dict()}


@dataclass
class IdeaGenerationCompleted(BaseEvent):
    """Emitted when batch idea generation completes."""

    count: int = 0
    event_type: str = field(default="idea_generation_completed", init=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            **super().to_dict(),
            "count": self.count,
        }


# ---------------------------------------------------------------------------
# System events (4)
# ---------------------------------------------------------------------------


@dataclass
class UserLogin(BaseEvent):
    """Emitted when a user logs in."""

    email: str = ""
    event_type: str = field(default="user_login", init=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            **super().to_dict(),
            "email": self.email,
        }


@dataclass
class UserCreated(BaseEvent):
    """Emitted when a user account is created."""

    email: str = ""
    role: str = ""
    event_type: str = field(default="user_created", init=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            **super().to_dict(),
            "email": self.email,
            "role": self.role,
        }


@dataclass
class CascadeLockAcquired(BaseEvent):
    """Emitted when the cascade lock is acquired."""

    cascade_id: str = ""
    event_type: str = field(default="cascade_lock_acquired", init=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            **super().to_dict(),
            "cascade_id": self.cascade_id,
        }


@dataclass
class CascadeLockReleased(BaseEvent):
    """Emitted when the cascade lock is released."""

    cascade_id: str = ""
    event_type: str = field(default="cascade_lock_released", init=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            **super().to_dict(),
            "cascade_id": self.cascade_id,
        }


# ---------------------------------------------------------------------------
# Conversation events (6)
# ---------------------------------------------------------------------------


@dataclass
class ConversationStarted(BaseEvent):
    """Emitted when a conversation turn begins processing."""

    conversation_id: str = ""
    event_type: str = field(default="conversation_started", init=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            **super().to_dict(),
            "conversation_id": self.conversation_id,
        }


@dataclass
class ConversationTextChunk(BaseEvent):
    """Emitted during streaming response generation."""

    conversation_id: str = ""
    text: str = ""
    event_type: str = field(default="conversation_text_chunk", init=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            **super().to_dict(),
            "conversation_id": self.conversation_id,
            "text": self.text,
        }


@dataclass
class ConversationFileEdit(BaseEvent):
    """Emitted when the agent writes or deletes a file."""

    conversation_id: str = ""
    layer_slug: str = ""
    filename: str = ""
    action: str = ""  # "write" or "delete"
    event_type: str = field(default="conversation_file_edit", init=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            **super().to_dict(),
            "conversation_id": self.conversation_id,
            "layer_slug": self.layer_slug,
            "filename": self.filename,
            "action": self.action,
        }


@dataclass
class ConversationTurnComplete(BaseEvent):
    """Emitted when the agent finishes its turn."""

    conversation_id: str = ""
    message_id: str = ""
    files_edited: list[str] = field(default_factory=list)  # layer_slug/filename paths
    event_type: str = field(default="conversation_turn_complete", init=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            **super().to_dict(),
            "conversation_id": self.conversation_id,
            "message_id": self.message_id,
            "files_edited": self.files_edited,
        }


@dataclass
class ConversationCascadePending(BaseEvent):
    """Emitted when conversation edits to foundational layers queue a cascade."""

    conversation_id: str = ""
    starting_layer: str = ""
    event_type: str = field(default="conversation_cascade_pending", init=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            **super().to_dict(),
            "conversation_id": self.conversation_id,
            "starting_layer": self.starting_layer,
        }


@dataclass
class ConversationTurnError(BaseEvent):
    """Emitted when the agent turn fails."""

    conversation_id: str = ""
    error_message: str = ""
    event_type: str = field(default="conversation_turn_error", init=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            **super().to_dict(),
            "conversation_id": self.conversation_id,
            "error_message": self.error_message,
        }


# ---------------------------------------------------------------------------
# EventEmitter
# ---------------------------------------------------------------------------

# Type alias for event handlers (sync or async)
EventHandler = Callable[[BaseEvent], None] | Callable[[BaseEvent], Awaitable[None]]


class EventEmitter:
    """Async-safe pub/sub for event dispatch.

    Follows the cc-runner pattern: handlers can be sync or async callables.
    A failing handler is logged but does not prevent other handlers from
    receiving the event.
    """

    def __init__(self) -> None:
        self._handlers: list[EventHandler] = []

    def subscribe(self, handler: EventHandler) -> None:
        """Subscribe a handler to receive events."""
        self._handlers.append(handler)

    def unsubscribe(self, handler: EventHandler) -> None:
        """Unsubscribe a handler from receiving events."""
        try:
            self._handlers.remove(handler)
        except ValueError:
            pass  # Handler not found — no-op

    async def emit(self, event: BaseEvent) -> None:
        """Emit an event to all subscribed handlers.

        Awaits async handlers. If a handler raises an exception, it is
        logged but does not propagate — other handlers still receive
        the event.
        """
        for handler in list(self._handlers):
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                logger.exception(
                    "Event handler %r failed for event %s",
                    handler,
                    event.event_type,
                )
