/**
 * Cascade zustand store.
 *
 * Holds the current cascade status, progress, and streaming text.
 *
 * Updated by two sources:
 * 1. REST (initial load via fetchStatus)
 * 2. WebSocket events dispatched by the central event dispatcher (step 013)
 *
 * The WebSocket event handlers update the store in real-time, keeping the
 * cascade status indicator, live cascade viewer, and cascade page current
 * without polling.
 */
import { create } from "zustand";
import { apiRequest } from "@/lib/apiClient.ts";
import type {
  CascadeStartedEvent,
  CascadeCompletedEvent,
  CascadeFailedEvent,
  CascadePausedEvent,
  CascadeResumedEvent,
  CascadeCancelledEvent,
  CascadeQueuedEvent,
  LayerGenerationStartedEvent,
  LayerGenerationCompletedEvent,
  CriticStartedEvent,
  CriticCompletedEvent,
  SynthesisStartedEvent,
  SynthesisCompletedEvent,
  AgentTextChunkEvent,
} from "@/types/events.ts";

// ── Types ────────────────────────────────────────────────────────────

export type CascadeStatus = "idle" | "running" | "paused" | "failed" | "queued";

export type CascadeStep = "generation" | "critics" | "synthesis";

export interface CascadeStatusResponse {
  status: CascadeStatus;
  current_layer?: string | null;
  current_step?: CascadeStep | null;
  queue_depth: number;
  error?: string | null;
}

// ── Store definition ─────────────────────────────────────────────────

interface CascadeState {
  /** Current cascade status */
  status: CascadeStatus;
  /** Current cascade ID (if running) */
  cascadeId: string | null;
  /** Current layer being processed (if running) */
  currentLayer: string | null;
  /** Current step within the layer (if running) */
  currentStep: CascadeStep | null;
  /** Number of cascades waiting in the queue */
  queueDepth: number;
  /** Error information if paused/failed */
  errorInfo: string | null;
  /** Whether the initial fetch has been attempted */
  initialized: boolean;
  /** Human-readable label of the currently active agent */
  currentAgentLabel: string | null;
  /** Accumulated agent reasoning text being streamed live */
  streamingText: string;

  // REST actions
  /** Fetch cascade status from the REST API */
  fetchStatus: () => Promise<void>;
  /** Re-fetch without any loading state */
  refresh: () => Promise<void>;

  // WebSocket event handlers (called by the dispatcher)
  handleCascadeStarted: (event: CascadeStartedEvent) => void;
  handleCascadeCompleted: (event: CascadeCompletedEvent) => void;
  handleCascadeFailed: (event: CascadeFailedEvent) => void;
  handleCascadePaused: (event: CascadePausedEvent) => void;
  handleCascadeResumed: (event: CascadeResumedEvent) => void;
  handleCascadeCancelled: (event: CascadeCancelledEvent) => void;
  handleCascadeQueued: (event: CascadeQueuedEvent) => void;
  handleLayerGenerationStarted: (event: LayerGenerationStartedEvent) => void;
  handleLayerGenerationCompleted: (event: LayerGenerationCompletedEvent) => void;
  handleCriticStarted: (event: CriticStartedEvent) => void;
  handleCriticCompleted: (event: CriticCompletedEvent) => void;
  handleSynthesisStarted: (event: SynthesisStartedEvent) => void;
  handleSynthesisCompleted: (event: SynthesisCompletedEvent) => void;
  handleAgentTextChunk: (event: AgentTextChunkEvent) => void;
}

export const useCascadeStore = create<CascadeState>((set, get) => ({
  status: "idle",
  cascadeId: null,
  currentLayer: null,
  currentStep: null,
  queueDepth: 0,
  errorInfo: null,
  initialized: false,
  currentAgentLabel: null,
  streamingText: "",

  fetchStatus: async () => {
    if (get().initialized) return;
    set({ initialized: true });

    try {
      const data = await apiRequest<CascadeStatusResponse>(
        "/api/cascade/status",
      );
      set({
        status: data.status,
        currentLayer: data.current_layer ?? null,
        currentStep: data.current_step ?? null,
        queueDepth: data.queue_depth,
        errorInfo: data.error ?? null,
      });
    } catch {
      // The cascade endpoint may not exist yet (built in step 017).
      // Default to idle — no error display needed.
      set({ status: "idle" });
    }
  },

  refresh: async () => {
    try {
      const data = await apiRequest<CascadeStatusResponse>(
        "/api/cascade/status",
      );
      set({
        status: data.status,
        currentLayer: data.current_layer ?? null,
        currentStep: data.current_step ?? null,
        queueDepth: data.queue_depth,
        errorInfo: data.error ?? null,
      });
    } catch {
      // Silently fail — keep existing state
    }
  },

  // ── WebSocket event handlers ─────────────────────────────────────

  handleCascadeStarted: (event) => {
    set({
      status: "running",
      cascadeId: event.cascade_id,
      currentLayer: event.starting_layer,
      currentStep: null,
      errorInfo: null,
      currentAgentLabel: null,
      streamingText: "",
    });
  },

  handleCascadeCompleted: (_event) => {
    set({
      status: "idle",
      cascadeId: null,
      currentLayer: null,
      currentStep: null,
      currentAgentLabel: null,
      streamingText: "",
      errorInfo: null,
    });
  },

  handleCascadeFailed: (event) => {
    set({
      status: "failed",
      errorInfo: event.error,
      currentLayer: event.failed_layer,
      currentStep: event.failed_step as CascadeStep,
    });
  },

  handleCascadePaused: (event) => {
    set({
      status: "paused",
      errorInfo: event.error,
      currentLayer: event.paused_layer,
      currentStep: event.paused_step as CascadeStep,
    });
  },

  handleCascadeResumed: (_event) => {
    set({
      status: "running",
      errorInfo: null,
    });
  },

  handleCascadeCancelled: (_event) => {
    set({
      status: "idle",
      cascadeId: null,
      currentLayer: null,
      currentStep: null,
      currentAgentLabel: null,
      streamingText: "",
      errorInfo: null,
    });
  },

  handleCascadeQueued: (event) => {
    set({
      queueDepth: event.queue_position,
    });
  },

  handleLayerGenerationStarted: (event) => {
    set({
      currentLayer: event.layer_slug,
      currentStep: "generation",
      currentAgentLabel: null,
      streamingText: "",
    });
  },

  handleLayerGenerationCompleted: (_event) => {
    // Step completed — agent label and streaming text cleared
    set({
      currentAgentLabel: null,
      streamingText: "",
    });
  },

  handleCriticStarted: (event) => {
    set({
      currentStep: "critics",
      currentAgentLabel: event.critic_archetype,
      streamingText: "",
    });
  },

  handleCriticCompleted: (_event) => {
    set({
      currentAgentLabel: null,
    });
  },

  handleSynthesisStarted: (_event) => {
    set({
      currentStep: "synthesis",
      currentAgentLabel: null,
      streamingText: "",
    });
  },

  handleSynthesisCompleted: (_event) => {
    set({
      currentAgentLabel: null,
      streamingText: "",
    });
  },

  handleAgentTextChunk: (event) => {
    set((state) => ({
      streamingText: state.streamingText + event.text,
      currentAgentLabel: event.agent_label || state.currentAgentLabel,
    }));
  },
}));
