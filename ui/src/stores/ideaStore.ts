/**
 * Idea zustand store.
 *
 * Full-featured store for the idea inbox page (step 021).
 * Combines REST-based CRUD actions with WebSocket event handlers
 * from step 013. REST provides initial data and explicit fetches;
 * WebSocket provides real-time incremental updates.
 *
 * Follows the layerStore pattern: async fetch with loading/error state,
 * optimistic updates on submission.
 */
import { create } from "zustand";
import { apiRequest } from "@/lib/apiClient.ts";
import type {
  IdeaSubmittedEvent,
  IdeaEvaluationStartedEvent,
  IdeaEvaluationCompletedEvent,
  IdeaGenerationStartedEvent,
  IdeaGenerationCompletedEvent,
} from "@/types/events.ts";

// ── Types ────────────────────────────────────────────────────────────

export type IdeaStatus = "pending" | "evaluating" | "evaluated" | "archived";
export type IdeaSource = "human" | "ai";
export type IdeaSortField = "submission_date" | "score";
export type IdeaSortOrder = "asc" | "desc";
export type IdeaFilterStatus = "all" | IdeaStatus;

/** Idea summary as returned by GET /api/ideas/ */
export interface IdeaSummary {
  id: string;
  text: string;
  source: string;
  target_objective: string | null;
  status: IdeaStatus;
  submitted_at: string;
  submitted_by: string;
  overall_score: number | null;
}

/** Score axes for an evaluated idea */
export interface IdeaScores {
  strategic_fit: number;
  feasibility: number;
  cost: number;
  risk: number;
  public_acceptance: number;
  international_impact: number;
  overall_score: number;
}

/** A single critic assessment */
export interface CriticAssessment {
  archetype: string;
  assessment_text: string;
  structured_assessment: Record<string, unknown> | null;
  created_at: string;
}

/** Synthesis result */
export interface SynthesisResult {
  synthesis_text: string;
  structured_synthesis: Record<string, unknown> | null;
  created_at: string;
}

/** Full idea detail as returned by GET /api/ideas/:id */
export interface IdeaDetail {
  id: string;
  text: string;
  source: string;
  target_objective: string | null;
  status: IdeaStatus;
  submitted_at: string;
  submitted_by: string;
  evaluation_started_at: string | null;
  evaluation_completed_at: string | null;
  scores: IdeaScores | null;
  critic_assessments: CriticAssessment[];
  synthesis: SynthesisResult | null;
}

// ── Constants ────────────────────────────────────────────────────────

const PAGE_SIZE = 20;

// Re-export critic constants from the shared module
export { CRITIC_ORDER, CRITIC_DISPLAY_KEYS } from "@/lib/layerConstants.ts";

// ── Store definition ─────────────────────────────────────────────────

interface IdeaState {
  /** List of ideas (filtered + sorted) */
  ideas: IdeaSummary[];
  /** Currently expanded idea's full detail */
  expandedDetail: IdeaDetail | null;
  /** ID of the currently expanded idea */
  expandedId: string | null;

  /** Current filter state */
  filterStatus: IdeaFilterStatus;
  /** Current sort field */
  sortField: IdeaSortField;
  /** Current sort order */
  sortOrder: IdeaSortOrder;

  /** Loading flags */
  loading: boolean;
  detailLoading: boolean;
  submitting: boolean;
  generating: boolean;
  archiving: string | null;
  reEvaluating: string | null;

  /** Error states */
  error: string | null;
  detailError: string | null;
  submitError: string | null;

  /** Pagination */
  offset: number;
  hasMore: boolean;
  loadingMore: boolean;

  /** Temporary ID counter for optimistic updates */
  _optimisticCounter: number;
  /** Set of optimistic IDs pending server confirmation */
  _optimisticIds: Set<string>;

  // ── REST-based actions ───────────────────────────────────────────

  /** Fetch the idea list with current filter/sort. Resets offset. */
  fetchIdeas: () => Promise<void>;
  /** Load more ideas (pagination). */
  loadMore: () => Promise<void>;
  /** Fetch full detail for a specific idea. */
  fetchIdeaDetail: (ideaId: string) => Promise<void>;
  /** Submit a new idea (optimistic update). */
  submitIdea: (text: string, targetObjective?: string) => Promise<void>;
  /** Trigger AI idea generation. */
  triggerGeneration: (scope?: string) => Promise<void>;
  /** Archive an idea. */
  archiveIdea: (ideaId: string) => Promise<void>;
  /** Re-evaluate an idea. */
  reEvaluateIdea: (ideaId: string) => Promise<void>;

  /** Update filter status and re-fetch. */
  setFilter: (status: IdeaFilterStatus) => void;
  /** Update sort and re-fetch. */
  setSort: (field: IdeaSortField, order: IdeaSortOrder) => void;

  /** Expand an idea (fetch detail). Collapses the previously expanded one. */
  expandIdea: (ideaId: string) => void;
  /** Collapse the currently expanded idea. */
  collapseIdea: () => void;

  // ── WebSocket event handlers ─────────────────────────────────────

  handleIdeaSubmitted: (event: IdeaSubmittedEvent) => void;
  handleIdeaEvaluationStarted: (event: IdeaEvaluationStartedEvent) => void;
  handleIdeaEvaluationCompleted: (event: IdeaEvaluationCompletedEvent) => void;
  handleIdeaGenerationStarted: (event: IdeaGenerationStartedEvent) => void;
  handleIdeaGenerationCompleted: (event: IdeaGenerationCompletedEvent) => void;
}

/** Build query string from filter/sort/offset. */
function buildQuery(
  filterStatus: IdeaFilterStatus,
  sortField: IdeaSortField,
  sortOrder: IdeaSortOrder,
  offset: number,
  limit: number,
): string {
  const params = new URLSearchParams();
  if (filterStatus !== "all") {
    params.set("status", filterStatus);
  }
  params.set("sort_by", sortField);
  params.set("sort_order", sortOrder);
  params.set("offset", String(offset));
  params.set("limit", String(limit));
  return params.toString();
}

export const useIdeaStore = create<IdeaState>((set, get) => ({
  ideas: [],
  expandedDetail: null,
  expandedId: null,

  filterStatus: "all",
  sortField: "submission_date",
  sortOrder: "desc",

  loading: false,
  detailLoading: false,
  submitting: false,
  generating: false,
  archiving: null,
  reEvaluating: null,

  error: null,
  detailError: null,
  submitError: null,

  offset: 0,
  hasMore: false,
  loadingMore: false,

  _optimisticCounter: 0,
  _optimisticIds: new Set(),

  // ── REST-based actions ───────────────────────────────────────────

  fetchIdeas: async () => {
    const { filterStatus, sortField, sortOrder } = get();
    set({ loading: true, error: null, offset: 0 });

    try {
      const query = buildQuery(filterStatus, sortField, sortOrder, 0, PAGE_SIZE);
      const data = await apiRequest<IdeaSummary[]>(`/api/ideas/?${query}`);
      set({
        ideas: data,
        loading: false,
        error: null,
        offset: data.length,
        hasMore: data.length >= PAGE_SIZE,
      });
    } catch (err: unknown) {
      const detail =
        err && typeof err === "object" && "detail" in err
          ? String((err as { detail: string }).detail)
          : "Failed to fetch ideas";
      set({ loading: false, error: detail });
    }
  },

  loadMore: async () => {
    const { filterStatus, sortField, sortOrder, offset, ideas, loadingMore } =
      get();
    if (loadingMore) return;
    set({ loadingMore: true });

    try {
      const query = buildQuery(
        filterStatus,
        sortField,
        sortOrder,
        offset,
        PAGE_SIZE,
      );
      const data = await apiRequest<IdeaSummary[]>(`/api/ideas/?${query}`);
      set({
        ideas: [...ideas, ...data],
        loadingMore: false,
        offset: offset + data.length,
        hasMore: data.length >= PAGE_SIZE,
      });
    } catch {
      set({ loadingMore: false });
    }
  },

  fetchIdeaDetail: async (ideaId: string) => {
    set({ detailLoading: true, detailError: null });

    try {
      const data = await apiRequest<IdeaDetail>(`/api/ideas/${ideaId}`);
      set({
        expandedDetail: data,
        expandedId: ideaId,
        detailLoading: false,
        detailError: null,
      });
    } catch (err: unknown) {
      const detail =
        err && typeof err === "object" && "detail" in err
          ? String((err as { detail: string }).detail)
          : "Failed to fetch idea detail";
      set({ detailLoading: false, detailError: detail });
    }
  },

  submitIdea: async (text: string, targetObjective?: string) => {
    const counter = get()._optimisticCounter + 1;
    const optimisticId = `__optimistic_${counter}`;

    // Optimistic update — immediately add to list
    const optimisticIdea: IdeaSummary = {
      id: optimisticId,
      text: text.length > 200 ? text.substring(0, 200) + "..." : text,
      source: "human",
      target_objective: targetObjective || null,
      status: "pending",
      submitted_at: new Date().toISOString(),
      submitted_by: "You",
      overall_score: null,
    };

    const newOptimisticIds = new Set(get()._optimisticIds);
    newOptimisticIds.add(optimisticId);

    set((state) => ({
      ideas: [optimisticIdea, ...state.ideas],
      submitting: true,
      submitError: null,
      _optimisticCounter: counter,
      _optimisticIds: newOptimisticIds,
    }));

    try {
      const body: Record<string, string> = { text };
      if (targetObjective) body.target_objective = targetObjective;

      const result = await apiRequest<{ id: string; status: string }>(
        "/api/ideas/",
        { method: "POST", body },
      );

      // Replace optimistic entry with real data
      const updatedOptimisticIds = new Set(get()._optimisticIds);
      updatedOptimisticIds.delete(optimisticId);

      set((state) => ({
        ideas: state.ideas.map((idea) =>
          idea.id === optimisticId
            ? { ...idea, id: result.id, status: result.status as IdeaStatus }
            : idea,
        ),
        submitting: false,
        submitError: null,
        _optimisticIds: updatedOptimisticIds,
      }));
    } catch (err: unknown) {
      // Remove optimistic entry on failure
      const updatedOptimisticIds = new Set(get()._optimisticIds);
      updatedOptimisticIds.delete(optimisticId);

      const detail =
        err && typeof err === "object" && "detail" in err
          ? String((err as { detail: string }).detail)
          : "Failed to submit idea";

      set((state) => ({
        ideas: state.ideas.filter((idea) => idea.id !== optimisticId),
        submitting: false,
        submitError: detail,
        _optimisticIds: updatedOptimisticIds,
      }));
    }
  },

  triggerGeneration: async (scope?: string) => {
    set({ generating: true });

    try {
      const body = scope ? { scope } : {};
      await apiRequest<{ message: string }>("/api/ideas/generate", {
        method: "POST",
        body,
      });
      // generating flag stays true until IdeaGenerationCompleted event
    } catch (err: unknown) {
      const detail =
        err && typeof err === "object" && "detail" in err
          ? String((err as { detail: string }).detail)
          : "Failed to start idea generation";
      set({ generating: false, error: detail });
    }
  },

  archiveIdea: async (ideaId: string) => {
    set({ archiving: ideaId });

    try {
      await apiRequest<{ id: string; status: string }>(
        `/api/ideas/${ideaId}/archive`,
        { method: "PUT" },
      );

      // Remove from list (unless viewing archived)
      const { filterStatus } = get();
      if (filterStatus !== "archived") {
        set((state) => ({
          ideas: state.ideas.filter((idea) => idea.id !== ideaId),
          archiving: null,
          expandedId:
            state.expandedId === ideaId ? null : state.expandedId,
          expandedDetail:
            state.expandedId === ideaId ? null : state.expandedDetail,
        }));
      } else {
        set((state) => ({
          ideas: state.ideas.map((idea) =>
            idea.id === ideaId
              ? { ...idea, status: "archived" as IdeaStatus }
              : idea,
          ),
          archiving: null,
        }));
      }
    } catch {
      set({ archiving: null });
    }
  },

  reEvaluateIdea: async (ideaId: string) => {
    set({ reEvaluating: ideaId });

    try {
      await apiRequest<{ idea_id: string; status: string }>(
        `/api/ideas/${ideaId}/evaluate`,
        { method: "POST" },
      );

      // Status will transition via WebSocket events
      set({ reEvaluating: null });
    } catch {
      set({ reEvaluating: null });
    }
  },

  setFilter: (status: IdeaFilterStatus) => {
    set({ filterStatus: status });
    get().fetchIdeas();
  },

  setSort: (field: IdeaSortField, order: IdeaSortOrder) => {
    set({ sortField: field, sortOrder: order });
    get().fetchIdeas();
  },

  expandIdea: (ideaId: string) => {
    const { expandedId } = get();
    if (expandedId === ideaId) {
      // Already expanded — collapse
      set({ expandedId: null, expandedDetail: null, detailError: null });
      return;
    }
    set({
      expandedId: ideaId,
      expandedDetail: null,
      detailError: null,
    });
    get().fetchIdeaDetail(ideaId);
  },

  collapseIdea: () => {
    set({ expandedId: null, expandedDetail: null, detailError: null });
  },

  // ── WebSocket event handlers ─────────────────────────────────────

  handleIdeaSubmitted: (event) => {
    set((state) => {
      // Check if idea already exists (from optimistic update or duplicate event)
      const exists = state.ideas.some((idea) => idea.id === event.idea_id);
      if (exists) return state;

      // Check if any optimistic entries match (human ideas from this user)
      const optimisticMatch = Array.from(state._optimisticIds).find((optId) =>
        state.ideas.some(
          (idea) => idea.id === optId && idea.source === event.source,
        ),
      );

      if (optimisticMatch) {
        const updatedOptimisticIds = new Set(state._optimisticIds);
        updatedOptimisticIds.delete(optimisticMatch);
        return {
          ideas: state.ideas.map((idea) =>
            idea.id === optimisticMatch
              ? { ...idea, id: event.idea_id }
              : idea,
          ),
          _optimisticIds: updatedOptimisticIds,
        };
      }

      // New idea (e.g., AI-generated) — add to the front of the list
      return {
        ideas: [
          {
            id: event.idea_id,
            text: "",
            source: event.source,
            target_objective: null,
            status: "pending" as IdeaStatus,
            submitted_at: event.timestamp,
            submitted_by: event.source === "human" ? "" : "System",
            overall_score: null,
          },
          ...state.ideas,
        ],
      };
    });
  },

  handleIdeaEvaluationStarted: (event) => {
    set((state) => ({
      ideas: state.ideas.map((idea) =>
        idea.id === event.idea_id
          ? { ...idea, status: "evaluating" as IdeaStatus }
          : idea,
      ),
    }));
  },

  handleIdeaEvaluationCompleted: (event) => {
    set((state) => {
      const newState: Partial<IdeaState> = {
        ideas: state.ideas.map((idea) =>
          idea.id === event.idea_id
            ? { ...idea, status: "evaluated" as IdeaStatus }
            : idea,
        ),
      };

      // If this idea is currently expanded, refresh its detail
      if (state.expandedId === event.idea_id) {
        setTimeout(() => get().fetchIdeaDetail(event.idea_id), 100);
      }

      return newState;
    });
  },

  handleIdeaGenerationStarted: (_event) => {
    set({ generating: true });
  },

  handleIdeaGenerationCompleted: (_event) => {
    set({ generating: false });
    // Refresh the list to pick up all generated ideas
    get().fetchIdeas();
  },
}));
