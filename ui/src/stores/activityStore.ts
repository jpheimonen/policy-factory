/**
 * Activity zustand store.
 *
 * Holds a chronological stream of recent events for the activity feed.
 * Populated by two sources:
 * 1. The central event dispatcher pushes every incoming WebSocket event
 *    via addEvent().
 * 2. The activity feed page fetches historical events via fetchHistory()
 *    on mount.
 *
 * The event list is capped at MAX_EVENTS to prevent unbounded memory growth.
 */
import { create } from "zustand";
import { apiRequest } from "@/lib/apiClient.ts";
import type {
  PolicyEvent,
  EventCategory,
  ActivityResponse,
  ReplayEvent,
} from "@/types/events.ts";

// ── Constants ────────────────────────────────────────────────────────

/** Maximum number of events to keep in the store. */
const MAX_EVENTS = 200;

// ── Types ────────────────────────────────────────────────────────────

/** Lightweight event record for the activity feed. */
export interface ActivityEvent {
  /** Database-generated integer ID */
  db_id: number;
  /** Event type string */
  event_type: string;
  /** ISO 8601 timestamp */
  timestamp: string;
  /** Event category (cascade, heartbeat, idea, system) */
  category: EventCategory | null;
  /** Layer slug (if event is layer-specific) */
  layer_slug: string | null;
  /** Full event data */
  data: Record<string, unknown>;
}

// ── Store definition ─────────────────────────────────────────────────

interface ActivityState {
  /** Chronological event list (newest at end), capped at MAX_EVENTS */
  events: ActivityEvent[];
  /** Filter: selected event category (null = all) */
  filterCategory: EventCategory | null;
  /** Filter: selected layer slug (null = all) */
  filterLayer: string | null;
  /** Whether a history fetch is in progress */
  loading: boolean;
  /** Error from history fetch */
  error: string | null;

  // Actions
  /** Add a new event from the WebSocket dispatcher */
  addEvent: (event: PolicyEvent) => void;
  /** Update the filter criteria */
  setFilter: (category: EventCategory | null, layerSlug: string | null) => void;
  /** Fetch historical events from the REST API */
  fetchHistory: (limit?: number, offset?: number) => Promise<void>;
  /** Get filtered events (computed value pattern) */
  getFilteredEvents: () => ActivityEvent[];
}

/** Extract category from a PolicyEvent using the event_type → category mapping. */
function eventToCategory(eventType: string): EventCategory | null {
  const cascadeTypes = new Set([
    "cascade_started", "cascade_completed", "cascade_failed",
    "cascade_paused", "cascade_resumed", "cascade_cancelled",
    "cascade_queued", "layer_generation_started", "layer_generation_completed",
    "critic_started", "critic_completed", "synthesis_started",
    "synthesis_completed", "agent_text_chunk",
  ]);
  const heartbeatTypes = new Set([
    "heartbeat_started", "heartbeat_tier_completed", "heartbeat_completed",
  ]);
  const ideaTypes = new Set([
    "idea_submitted", "idea_evaluation_started", "idea_evaluation_completed",
    "idea_generation_started", "idea_generation_completed",
  ]);
  const systemTypes = new Set([
    "user_login", "user_created", "cascade_lock_acquired", "cascade_lock_released",
  ]);

  if (cascadeTypes.has(eventType)) return "cascade";
  if (heartbeatTypes.has(eventType)) return "heartbeat";
  if (ideaTypes.has(eventType)) return "idea";
  if (systemTypes.has(eventType)) return "system";
  return null;
}

/** Extract layer_slug from a PolicyEvent if present. */
function extractLayerSlug(event: PolicyEvent): string | null {
  if ("layer_slug" in event) return (event as { layer_slug: string }).layer_slug;
  if ("starting_layer" in event) return (event as { starting_layer: string }).starting_layer;
  if ("failed_layer" in event) return (event as { failed_layer: string }).failed_layer;
  if ("paused_layer" in event) return (event as { paused_layer: string }).paused_layer;
  return null;
}

export const useActivityStore = create<ActivityState>((set, get) => ({
  events: [],
  filterCategory: null,
  filterLayer: null,
  loading: false,
  error: null,

  addEvent: (event) => {
    const activityEvent: ActivityEvent = {
      db_id: event.db_id,
      event_type: event.event_type,
      timestamp: event.timestamp,
      category: eventToCategory(event.event_type),
      layer_slug: extractLayerSlug(event),
      data: event as unknown as Record<string, unknown>,
    };

    set((state) => {
      // Append to end (chronological order, newest at end)
      const updated = [...state.events, activityEvent];
      // Trim oldest if exceeding cap
      if (updated.length > MAX_EVENTS) {
        return { events: updated.slice(updated.length - MAX_EVENTS) };
      }
      return { events: updated };
    });
  },

  setFilter: (category, layerSlug) => {
    set({
      filterCategory: category,
      filterLayer: layerSlug,
    });
  },

  fetchHistory: async (limit = 50, offset = 0) => {
    set({ loading: true, error: null });
    try {
      const params = new URLSearchParams();
      params.set("limit", String(limit));
      params.set("offset", String(offset));

      const { filterCategory, filterLayer } = get();
      if (filterCategory) params.set("category", filterCategory);
      if (filterLayer) params.set("layer", filterLayer);

      const data = await apiRequest<ActivityResponse>(
        `/api/activity/?${params.toString()}`,
      );

      // API returns newest-first; reverse for chronological (oldest at start)
      const activityEvents: ActivityEvent[] = data.events
        .reverse()
        .map((e: ReplayEvent) => ({
          db_id: e.id,
          event_type: e.event_type,
          timestamp: e.timestamp,
          category: e.category ?? eventToCategory(e.event_type),
          layer_slug: e.layer_slug,
          data: e.data,
        }));

      set({ events: activityEvents, loading: false });
    } catch {
      set({ error: "Failed to fetch activity history", loading: false });
    }
  },

  getFilteredEvents: () => {
    const { events, filterCategory, filterLayer } = get();
    return events.filter((e) => {
      if (filterCategory && e.category !== filterCategory) return false;
      if (filterLayer && e.layer_slug !== filterLayer) return false;
      return true;
    });
  },
}));
