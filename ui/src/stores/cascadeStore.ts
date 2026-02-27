/**
 * Cascade zustand store (initial shell).
 *
 * Holds the current cascade status fetched from GET /api/cascade/status.
 * This is a minimal REST-only store — step 013 (Frontend WebSocket integration)
 * will extend it with WebSocket event handlers that update the store in real-time.
 *
 * For now, the store:
 * - Fetches cascade status on mount of the navigation component
 * - Provides the status to the cascade indicator in the nav bar
 * - Gracefully handles 404 (cascade endpoint not yet implemented)
 */
import { create } from "zustand";
import { apiRequest } from "@/lib/apiClient.ts";

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

  // Actions
  /** Fetch cascade status from the REST API */
  fetchStatus: () => Promise<void>;
  /** Re-fetch without any loading state */
  refresh: () => Promise<void>;
}

export const useCascadeStore = create<CascadeState>((set, get) => ({
  status: "idle",
  currentLayer: null,
  currentStep: null,
  queueDepth: 0,
  errorInfo: null,
  initialized: false,

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
}));
