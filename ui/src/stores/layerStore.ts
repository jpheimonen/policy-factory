/**
 * Layer zustand store.
 *
 * Manages layer listing data fetched from the backend API.
 * Provides layers in their canonical hierarchical order
 * (Values → Situational Awareness → Strategic Objectives → Tactical Objectives → Policies)
 * regardless of the order returned by the API.
 *
 * Pattern follows authStore.ts and cc-runner's projectInfoStore.ts:
 * - Async fetch with loading/error state
 * - Refresh action that keeps stale data visible
 * - Initialize guard to prevent duplicate fetches
 */
import { create } from "zustand";
import { apiRequest } from "@/lib/apiClient.ts";

// ── Types ────────────────────────────────────────────────────────────

/** A single layer as returned by GET /api/layers/ */
export interface LayerSummary {
  slug: string;
  display_name: string;
  position: number;
  item_count: number;
  last_updated: string;
  narrative_preview: string;
  pending_feedback_count: number;
}

/** Canonical layer order (bottom to top) */
const LAYER_ORDER: readonly string[] = [
  "values",
  "situational-awareness",
  "strategic-objectives",
  "tactical-objectives",
  "policies",
];

/** Sort layers into canonical hierarchical order by position. */
function sortLayers(layers: LayerSummary[]): LayerSummary[] {
  return [...layers].sort((a, b) => {
    const aIdx = LAYER_ORDER.indexOf(a.slug);
    const bIdx = LAYER_ORDER.indexOf(b.slug);
    return aIdx - bIdx;
  });
}

// ── Store definition ─────────────────────────────────────────────────

interface LayerState {
  /** The list of layers in canonical order */
  layers: LayerSummary[];
  /** True during the initial fetch */
  loading: boolean;
  /** Error message if the API call failed */
  error: string | null;
  /** Whether init() has been called */
  initialized: boolean;

  // Actions
  /** One-time initialization — triggers the first fetch with loading state */
  init: () => Promise<void>;
  /** Fetch layers with loading indicator (for initial load) */
  fetchLayers: () => Promise<void>;
  /** Re-fetch without loading state (keeps stale data visible) */
  refresh: () => Promise<void>;
}

export const useLayerStore = create<LayerState>((set, get) => ({
  layers: [],
  loading: false,
  error: null,
  initialized: false,

  init: async () => {
    if (get().initialized) return;
    set({ initialized: true });
    await get().fetchLayers();
  },

  fetchLayers: async () => {
    set({ loading: true, error: null });
    try {
      const data = await apiRequest<LayerSummary[]>("/api/layers/");
      set({ layers: sortLayers(data), loading: false, error: null });
    } catch (err: unknown) {
      const detail =
        err && typeof err === "object" && "detail" in err
          ? String((err as { detail: string }).detail)
          : "Failed to fetch layers";
      set({ loading: false, error: detail });
    }
  },

  refresh: async () => {
    // Re-fetch without showing loading state — keep stale data visible
    try {
      const data = await apiRequest<LayerSummary[]>("/api/layers/");
      set({ layers: sortLayers(data), error: null });
    } catch {
      // Silently fail on refresh — stale data is better than error
    }
  },
}));
