/**
 * Layer zustand store.
 *
 * Manages layer listing data and per-layer detail data fetched from the backend API.
 * Provides layers in their canonical hierarchical order
 * (Philosophy → Values → Situational Awareness → Strategic Objectives → Tactical Objectives → Policies)
 * regardless of the order returned by the API.
 *
 * The store holds two data slices:
 * 1. Layer listing — all 5 layers with summary metadata (step 009)
 * 2. Layer detail — items, narrative summary, and feedback memos for the
 *    currently viewed layer (step 010)
 *
 * Pattern follows authStore.ts and cc-runner's projectInfoStore.ts:
 * - Async fetch with loading/error state
 * - Refresh action that keeps stale data visible
 * - Initialize guard to prevent duplicate fetches
 */
import { create } from "zustand";
import { apiRequest, extractErrorDetail } from "@/lib/apiClient.ts";

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

/** A single item within a layer as returned by GET /api/layers/:slug/items */
export interface LayerItem {
  filename: string;
  title: string;
  status?: string;
  last_modified: string;
  last_modified_by: string;
}

/** A feedback memo targeting the current layer */
export interface FeedbackMemo {
  id: string;
  source_layer: string;
  target_layer: string;
  content: string;
  referenced_items: string[];
  status: string;
  created_at: string;
}

/** Canonical layer order (bottom to top) */
const LAYER_ORDER: readonly string[] = [
  "philosophy",
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

/** Check if a slug is one of the 5 known layer slugs. */
export function isValidLayerSlug(slug: string): boolean {
  return LAYER_ORDER.includes(slug);
}

// ── Store definition ─────────────────────────────────────────────────

interface LayerState {
  // ── Layer listing (step 009) ──────────────────────────────────────
  /** The list of layers in canonical order */
  layers: LayerSummary[];
  /** True during the initial fetch */
  loading: boolean;
  /** Error message if the API call failed */
  error: string | null;
  /** Whether init() has been called */
  initialized: boolean;

  // ── Layer detail (step 010) ───────────────────────────────────────
  /** The currently viewed layer's slug */
  detailSlug: string | null;
  /** Items in the currently viewed layer */
  detailItems: LayerItem[];
  /** Narrative summary (markdown) for the currently viewed layer */
  detailSummary: string;
  /** Pending feedback memos targeting the currently viewed layer */
  detailMemos: FeedbackMemo[];
  /** True during the initial detail fetch */
  detailLoading: boolean;
  /** Error message if the detail fetch failed */
  detailError: string | null;

  // ── Listing actions ───────────────────────────────────────────────
  /** One-time initialization — triggers the first fetch with loading state */
  init: () => Promise<void>;
  /** Fetch layers with loading indicator (for initial load) */
  fetchLayers: () => Promise<void>;
  /** Re-fetch without loading state (keeps stale data visible) */
  refresh: () => Promise<void>;

  // ── Detail actions ────────────────────────────────────────────────
  /** Fetch items + summary for a specific layer. Shows loading state. */
  fetchLayerDetail: (slug: string) => Promise<void>;
  /** Re-fetch detail without showing loading state (keeps stale data visible). */
  refreshLayerDetail: () => Promise<void>;
  /** Clear detail data (call when navigating away from the detail page). */
  clearLayerDetail: () => void;
}

export const useLayerStore = create<LayerState>((set, get) => ({
  // ── Listing state ─────────────────────────────────────────────────
  layers: [],
  loading: false,
  error: null,
  initialized: false,

  // ── Detail state ──────────────────────────────────────────────────
  detailSlug: null,
  detailItems: [],
  detailSummary: "",
  detailMemos: [],
  detailLoading: false,
  detailError: null,

  // ── Listing actions ───────────────────────────────────────────────

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
      const detail = extractErrorDetail(err, "Failed to fetch layers");
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

  // ── Detail actions ────────────────────────────────────────────────

  fetchLayerDetail: async (slug: string) => {
    set({
      detailSlug: slug,
      detailLoading: true,
      detailError: null,
    });

    try {
      // Fetch items and summary in parallel
      const [items, summaryData] = await Promise.all([
        apiRequest<LayerItem[]>(`/api/layers/${slug}/items`),
        apiRequest<{ summary: string }>(`/api/layers/${slug}/summary`),
      ]);

      // Sort items alphabetically by title
      const sortedItems = [...items].sort((a, b) =>
        (a.title || a.filename).localeCompare(b.title || b.filename),
      );

      // Feedback memos — attempt to fetch, but the endpoint may not exist yet (step 017)
      let memos: FeedbackMemo[] = [];
      try {
        memos = await apiRequest<FeedbackMemo[]>(
          `/api/layers/${slug}/feedback-memos`,
        );
      } catch {
        // Endpoint not available yet — use empty list
      }

      set({
        detailItems: sortedItems,
        detailSummary:
          typeof summaryData === "string"
            ? summaryData
            : summaryData?.summary ?? "",
        detailMemos: memos,
        detailLoading: false,
        detailError: null,
      });
    } catch (err: unknown) {
      const detail = extractErrorDetail(err, "Failed to fetch layer detail");
      set({ detailLoading: false, detailError: detail });
    }
  },

  refreshLayerDetail: async () => {
    const slug = get().detailSlug;
    if (!slug) return;

    try {
      const [items, summaryData] = await Promise.all([
        apiRequest<LayerItem[]>(`/api/layers/${slug}/items`),
        apiRequest<{ summary: string }>(`/api/layers/${slug}/summary`),
      ]);

      const sortedItems = [...items].sort((a, b) =>
        (a.title || a.filename).localeCompare(b.title || b.filename),
      );

      let memos: FeedbackMemo[] = [];
      try {
        memos = await apiRequest<FeedbackMemo[]>(
          `/api/layers/${slug}/feedback-memos`,
        );
      } catch {
        // Endpoint not available yet
      }

      set({
        detailItems: sortedItems,
        detailSummary:
          typeof summaryData === "string"
            ? summaryData
            : summaryData?.summary ?? "",
        detailMemos: memos,
        detailError: null,
      });
    } catch {
      // Silently fail on refresh — stale data is better than error
    }
  },

  clearLayerDetail: () => {
    set({
      detailSlug: null,
      detailItems: [],
      detailSummary: "",
      detailMemos: [],
      detailLoading: false,
      detailError: null,
    });
  },
}));
