/**
 * Frontend event type definitions matching backend event dataclasses.
 *
 * Maps 1:1 to the Python event types in `src/policy_factory/events.py`.
 * The discriminated union `PolicyEvent` enables type-safe event handling
 * in the central dispatcher.
 *
 * Events arrive over WebSocket with:
 * - `db_id` — database-generated integer (for deduplication and replay cursor)
 * - `id` — UUID string (original event ID)
 * - `event_type` — string literal discriminator
 * - `timestamp` — ISO 8601 string
 * - Type-specific fields
 *
 * The replay endpoint returns events with the integer `id` field (db_id).
 */

// ── Event type literals ────────────────────────────────────────────

export type EventType =
  // Cascade lifecycle (7)
  | "cascade_started"
  | "cascade_completed"
  | "cascade_failed"
  | "cascade_paused"
  | "cascade_resumed"
  | "cascade_cancelled"
  | "cascade_queued"
  // Layer processing (6)
  | "layer_generation_started"
  | "layer_generation_completed"
  | "critic_started"
  | "critic_completed"
  | "synthesis_started"
  | "synthesis_completed"
  // Agent streaming (1)
  | "agent_text_chunk"
  // Heartbeat (3)
  | "heartbeat_started"
  | "heartbeat_tier_completed"
  | "heartbeat_completed"
  // Seed progress (3)
  | "seed_started"
  | "seed_progress"
  | "seed_completed"
  // Ideas (5)
  | "idea_submitted"
  | "idea_evaluation_started"
  | "idea_evaluation_completed"
  | "idea_generation_started"
  | "idea_generation_completed"
  // System (4)
  | "user_login"
  | "user_created"
  | "cascade_lock_acquired"
  | "cascade_lock_released"
  // Conversation (6)
  | "conversation_started"
  | "conversation_text_chunk"
  | "conversation_file_edit"
  | "conversation_turn_complete"
  | "conversation_cascade_pending"
  | "conversation_turn_error";

export type EventCategory = "cascade" | "conversation" | "heartbeat" | "idea" | "seed" | "system";

// ── Base event interface ───────────────────────────────────────────

export interface BaseEvent {
  /** Database-generated integer ID (for deduplication and replay cursor).
   * Present on WS events as `db_id`, on replay events as `id`. */
  db_id: number;
  /** UUID string — the original event ID */
  id: string;
  event_type: EventType;
  timestamp: string; // ISO 8601
}

// ── Cascade lifecycle events ───────────────────────────────────────

export interface CascadeStartedEvent extends BaseEvent {
  event_type: "cascade_started";
  cascade_id: string;
  trigger_source: string;
  starting_layer: string;
}

export interface CascadeCompletedEvent extends BaseEvent {
  event_type: "cascade_completed";
  cascade_id: string;
  success: boolean;
}

export interface CascadeFailedEvent extends BaseEvent {
  event_type: "cascade_failed";
  cascade_id: string;
  error: string;
  failed_layer: string;
  failed_step: string;
}

export interface CascadePausedEvent extends BaseEvent {
  event_type: "cascade_paused";
  cascade_id: string;
  error: string;
  paused_layer: string;
  paused_step: string;
}

export interface CascadeResumedEvent extends BaseEvent {
  event_type: "cascade_resumed";
  cascade_id: string;
}

export interface CascadeCancelledEvent extends BaseEvent {
  event_type: "cascade_cancelled";
  cascade_id: string;
}

export interface CascadeQueuedEvent extends BaseEvent {
  event_type: "cascade_queued";
  cascade_id: string;
  queue_position: number;
}

// ── Layer processing events ────────────────────────────────────────

export interface LayerGenerationStartedEvent extends BaseEvent {
  event_type: "layer_generation_started";
  cascade_id: string;
  layer_slug: string;
}

export interface LayerGenerationCompletedEvent extends BaseEvent {
  event_type: "layer_generation_completed";
  cascade_id: string;
  layer_slug: string;
}

export interface CriticStartedEvent extends BaseEvent {
  event_type: "critic_started";
  cascade_id: string;
  layer_slug: string;
  critic_archetype: string;
}

export interface CriticCompletedEvent extends BaseEvent {
  event_type: "critic_completed";
  cascade_id: string;
  layer_slug: string;
  critic_archetype: string;
}

export interface SynthesisStartedEvent extends BaseEvent {
  event_type: "synthesis_started";
  cascade_id: string;
  layer_slug: string;
}

export interface SynthesisCompletedEvent extends BaseEvent {
  event_type: "synthesis_completed";
  cascade_id: string;
  layer_slug: string;
}

// ── Agent streaming events ─────────────────────────────────────────

export interface AgentTextChunkEvent extends BaseEvent {
  event_type: "agent_text_chunk";
  cascade_id: string;
  agent_label: string;
  text: string;
}

// ── Heartbeat events ───────────────────────────────────────────────

export interface HeartbeatStartedEvent extends BaseEvent {
  event_type: "heartbeat_started";
  heartbeat_run_id: string;
}

export interface HeartbeatTierCompletedEvent extends BaseEvent {
  event_type: "heartbeat_tier_completed";
  heartbeat_run_id: string;
  tier: number;
  outcome: string;
  escalated: boolean;
}

export interface HeartbeatCompletedEvent extends BaseEvent {
  event_type: "heartbeat_completed";
  heartbeat_run_id: string;
  highest_tier: number;
}

// ── Seed progress events ──────────────────────────────────────────

export interface SeedStartedEvent extends BaseEvent {
  event_type: "seed_started";
  layer_slug: string;
  agent_label: string;
}

export interface SeedProgressEvent extends BaseEvent {
  event_type: "seed_progress";
  layer_slug: string;
  step: string;
  message: string;
}

export interface SeedCompletedEvent extends BaseEvent {
  event_type: "seed_completed";
  layer_slug: string;
  success: boolean;
  message: string;
  items_created: number;
}

// ── Idea events ────────────────────────────────────────────────────

export interface IdeaSubmittedEvent extends BaseEvent {
  event_type: "idea_submitted";
  idea_id: string;
  source: string;
}

export interface IdeaEvaluationStartedEvent extends BaseEvent {
  event_type: "idea_evaluation_started";
  idea_id: string;
}

export interface IdeaEvaluationCompletedEvent extends BaseEvent {
  event_type: "idea_evaluation_completed";
  idea_id: string;
}

export interface IdeaGenerationStartedEvent extends BaseEvent {
  event_type: "idea_generation_started";
}

export interface IdeaGenerationCompletedEvent extends BaseEvent {
  event_type: "idea_generation_completed";
  count: number;
}

// ── System events ──────────────────────────────────────────────────

export interface UserLoginEvent extends BaseEvent {
  event_type: "user_login";
  email: string;
}

export interface UserCreatedEvent extends BaseEvent {
  event_type: "user_created";
  email: string;
  role: string;
}

export interface CascadeLockAcquiredEvent extends BaseEvent {
  event_type: "cascade_lock_acquired";
  cascade_id: string;
}

export interface CascadeLockReleasedEvent extends BaseEvent {
  event_type: "cascade_lock_released";
  cascade_id: string;
}

// ── Conversation events ────────────────────────────────────────────

export interface ConversationStartedEvent extends BaseEvent {
  event_type: "conversation_started";
  conversation_id: string;
}

export interface ConversationTextChunkEvent extends BaseEvent {
  event_type: "conversation_text_chunk";
  conversation_id: string;
  text: string;
}

export interface ConversationFileEditEvent extends BaseEvent {
  event_type: "conversation_file_edit";
  conversation_id: string;
  layer_slug: string;
  filename: string;
  action: "write" | "delete";
}

export interface ConversationTurnCompleteEvent extends BaseEvent {
  event_type: "conversation_turn_complete";
  conversation_id: string;
  message_id: string;
  files_edited: string[];
}

export interface ConversationCascadePendingEvent extends BaseEvent {
  event_type: "conversation_cascade_pending";
  conversation_id: string;
  starting_layer: string;
}

export interface ConversationTurnErrorEvent extends BaseEvent {
  event_type: "conversation_turn_error";
  conversation_id: string;
  error_message: string;
}

// ── Discriminated union ────────────────────────────────────────────

export type PolicyEvent =
  // Cascade lifecycle
  | CascadeStartedEvent
  | CascadeCompletedEvent
  | CascadeFailedEvent
  | CascadePausedEvent
  | CascadeResumedEvent
  | CascadeCancelledEvent
  | CascadeQueuedEvent
  // Layer processing
  | LayerGenerationStartedEvent
  | LayerGenerationCompletedEvent
  | CriticStartedEvent
  | CriticCompletedEvent
  | SynthesisStartedEvent
  | SynthesisCompletedEvent
  // Agent streaming
  | AgentTextChunkEvent
  // Heartbeat
  | HeartbeatStartedEvent
  | HeartbeatTierCompletedEvent
  | HeartbeatCompletedEvent
  // Seed progress
  | SeedStartedEvent
  | SeedProgressEvent
  | SeedCompletedEvent
  // Ideas
  | IdeaSubmittedEvent
  | IdeaEvaluationStartedEvent
  | IdeaEvaluationCompletedEvent
  | IdeaGenerationStartedEvent
  | IdeaGenerationCompletedEvent
  // System
  | UserLoginEvent
  | UserCreatedEvent
  | CascadeLockAcquiredEvent
  | CascadeLockReleasedEvent
  // Conversation
  | ConversationStartedEvent
  | ConversationTextChunkEvent
  | ConversationFileEditEvent
  | ConversationTurnCompleteEvent
  | ConversationCascadePendingEvent
  | ConversationTurnErrorEvent;

// ── Replay API response ────────────────────────────────────────────

export interface ReplayEvent {
  id: number; // Database integer ID
  event_type: EventType;
  timestamp: string;
  data: Record<string, unknown>;
  layer_slug: string | null;
  category: EventCategory | null;
}

export interface ReplayResponse {
  events: ReplayEvent[];
  since_id: number;
  overflow: boolean;
}

export interface ActivityResponse {
  events: ReplayEvent[];
  limit: number;
  offset: number;
}

// ── Category mapping ───────────────────────────────────────────────

const EVENT_CATEGORY_MAP: Record<EventType, EventCategory> = {
  cascade_started: "cascade",
  cascade_completed: "cascade",
  cascade_failed: "cascade",
  cascade_paused: "cascade",
  cascade_resumed: "cascade",
  cascade_cancelled: "cascade",
  cascade_queued: "cascade",
  layer_generation_started: "cascade",
  layer_generation_completed: "cascade",
  critic_started: "cascade",
  critic_completed: "cascade",
  synthesis_started: "cascade",
  synthesis_completed: "cascade",
  agent_text_chunk: "cascade",
  heartbeat_started: "heartbeat",
  heartbeat_tier_completed: "heartbeat",
  heartbeat_completed: "heartbeat",
  seed_started: "seed",
  seed_progress: "seed",
  seed_completed: "seed",
  idea_submitted: "idea",
  idea_evaluation_started: "idea",
  idea_evaluation_completed: "idea",
  idea_generation_started: "idea",
  idea_generation_completed: "idea",
  user_login: "system",
  user_created: "system",
  cascade_lock_acquired: "system",
  cascade_lock_released: "system",
  // Conversation
  conversation_started: "conversation",
  conversation_text_chunk: "conversation",
  conversation_file_edit: "conversation",
  conversation_turn_complete: "conversation",
  conversation_cascade_pending: "conversation",
  conversation_turn_error: "conversation",
};

export function getEventCategory(eventType: EventType): EventCategory {
  return EVENT_CATEGORY_MAP[eventType];
}
