/**
 * Central event dispatcher.
 *
 * Routes incoming WebSocket events to the appropriate zustand stores
 * based on event_type. This is the single point where all event routing
 * logic lives — the useWebSocket hook calls dispatchEvent() for every
 * validated, deduplicated event.
 *
 * Follows the cc-runner globalHITLStore dispatch pattern — a switch on
 * event_type that updates specific stores.
 *
 * Dispatch rules:
 * - Cascade events → cascade store
 * - Layer processing events → cascade store
 * - Agent text chunk events → cascade store (streaming text buffer)
 * - Seed events → seed progress store
 * - Idea events → idea store
 * - All events → activity store (complete chronological stream)
 *
 * Side effects:
 * - cascade_completed → triggers layer store refresh
 * - seed_completed → triggers layer store refresh
 */
import { useCallback } from "react";
import { useCascadeStore } from "@/stores/cascadeStore.ts";
import { useIdeaStore } from "@/stores/ideaStore.ts";
import { useActivityStore } from "@/stores/activityStore.ts";
import { useLayerStore } from "@/stores/layerStore.ts";
import { useSeedProgressStore } from "@/stores/seedProgressStore.ts";
import type { PolicyEvent } from "@/types/events.ts";

/**
 * Returns a stable dispatch function that routes events to stores.
 *
 * Uses zustand's getState() for store access (avoids re-renders from
 * subscribing to every store field in this hook).
 */
export function useEventDispatch() {
  const dispatch = useCallback((event: PolicyEvent) => {
    const cascadeStore = useCascadeStore.getState();
    const ideaStore = useIdeaStore.getState();
    const activityStore = useActivityStore.getState();

    // ── Route to domain-specific stores ──────────────────────────

    switch (event.event_type) {
      // Cascade lifecycle events → cascade store
      case "cascade_started":
        cascadeStore.handleCascadeStarted(event);
        break;
      case "cascade_completed":
        cascadeStore.handleCascadeCompleted(event);
        // Side effect: refresh layer data (cascade changed content)
        useLayerStore.getState().refresh();
        break;
      case "cascade_failed":
        cascadeStore.handleCascadeFailed(event);
        break;
      case "cascade_paused":
        cascadeStore.handleCascadePaused(event);
        break;
      case "cascade_resumed":
        cascadeStore.handleCascadeResumed(event);
        break;
      case "cascade_cancelled":
        cascadeStore.handleCascadeCancelled(event);
        break;
      case "cascade_queued":
        cascadeStore.handleCascadeQueued(event);
        break;

      // Layer processing events → cascade store
      case "layer_generation_started":
        cascadeStore.handleLayerGenerationStarted(event);
        break;
      case "layer_generation_completed":
        cascadeStore.handleLayerGenerationCompleted(event);
        break;
      case "critic_started":
        cascadeStore.handleCriticStarted(event);
        break;
      case "critic_completed":
        cascadeStore.handleCriticCompleted(event);
        break;
      case "synthesis_started":
        cascadeStore.handleSynthesisStarted(event);
        break;
      case "synthesis_completed":
        cascadeStore.handleSynthesisCompleted(event);
        break;

      // Agent streaming → cascade store
      case "agent_text_chunk":
        cascadeStore.handleAgentTextChunk(event);
        break;

      // Idea events → idea store
      case "idea_submitted":
        ideaStore.handleIdeaSubmitted(event);
        break;
      case "idea_evaluation_started":
        ideaStore.handleIdeaEvaluationStarted(event);
        break;
      case "idea_evaluation_completed":
        ideaStore.handleIdeaEvaluationCompleted(event);
        break;
      case "idea_generation_started":
        ideaStore.handleIdeaGenerationStarted(event);
        break;
      case "idea_generation_completed":
        ideaStore.handleIdeaGenerationCompleted(event);
        break;

      // Seed progress events → seed progress store
      case "seed_started":
        useSeedProgressStore.getState().handleSeedStarted(event);
        break;
      case "seed_progress":
        useSeedProgressStore.getState().handleSeedProgress(event);
        break;
      case "seed_completed":
        useSeedProgressStore.getState().handleSeedCompleted(event);
        // Side effect: refresh layer data (seed created content)
        useLayerStore.getState().refresh();
        break;

      // Heartbeat and system events — no dedicated store action needed.
      // They still go to the activity store (below).
      case "heartbeat_started":
      case "heartbeat_tier_completed":
      case "heartbeat_completed":
      case "user_login":
      case "user_created":
      case "cascade_lock_acquired":
      case "cascade_lock_released":
        break;
    }

    // ── All events → activity store ──────────────────────────────
    // Skip high-frequency agent_text_chunk from the activity feed
    // to avoid flooding it with streaming text.
    if (event.event_type !== "agent_text_chunk") {
      activityStore.addEvent(event);
    }
  }, []);

  return dispatch;
}
