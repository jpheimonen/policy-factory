/**
 * Idea zustand store (shell).
 *
 * Minimal store for WebSocket event handling. Step 021 (Frontend idea inbox)
 * will add REST-based CRUD actions, filtering, sorting, and submission.
 *
 * For now, only WebSocket event handlers are implemented so that real-time
 * updates flow through when idea events arrive.
 */
import { create } from "zustand";
import type {
  IdeaSubmittedEvent,
  IdeaEvaluationStartedEvent,
  IdeaEvaluationCompletedEvent,
  IdeaGenerationStartedEvent,
  IdeaGenerationCompletedEvent,
} from "@/types/events.ts";

// ── Types ────────────────────────────────────────────────────────────

export type IdeaStatus = "pending" | "evaluating" | "evaluated" | "archived";

export interface Idea {
  id: string;
  text?: string;
  source: string; // "human" or "AI"
  status: IdeaStatus;
  submitted_at?: string;
}

// ── Store definition ─────────────────────────────────────────────────

interface IdeaState {
  /** List of ideas */
  ideas: Idea[];
  /** Whether a fetch is in progress */
  loading: boolean;
  /** Error message if fetch failed */
  error: string | null;
  /** Whether AI idea generation is in progress */
  generating: boolean;
  /** Flag indicating ideas list needs refresh */
  needsRefresh: boolean;

  // WebSocket event handlers (called by the dispatcher)
  handleIdeaSubmitted: (event: IdeaSubmittedEvent) => void;
  handleIdeaEvaluationStarted: (event: IdeaEvaluationStartedEvent) => void;
  handleIdeaEvaluationCompleted: (event: IdeaEvaluationCompletedEvent) => void;
  handleIdeaGenerationStarted: (event: IdeaGenerationStartedEvent) => void;
  handleIdeaGenerationCompleted: (event: IdeaGenerationCompletedEvent) => void;
}

export const useIdeaStore = create<IdeaState>((set) => ({
  ideas: [],
  loading: false,
  error: null,
  generating: false,
  needsRefresh: false,

  // ── WebSocket event handlers ─────────────────────────────────────

  handleIdeaSubmitted: (event) => {
    set((state) => ({
      ideas: [
        ...state.ideas,
        {
          id: event.idea_id,
          source: event.source,
          status: "pending" as IdeaStatus,
          submitted_at: event.timestamp,
        },
      ],
      needsRefresh: true,
    }));
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
    set((state) => ({
      ideas: state.ideas.map((idea) =>
        idea.id === event.idea_id
          ? { ...idea, status: "evaluated" as IdeaStatus }
          : idea,
      ),
      needsRefresh: true,
    }));
  },

  handleIdeaGenerationStarted: (_event) => {
    set({ generating: true });
  },

  handleIdeaGenerationCompleted: (_event) => {
    set({
      generating: false,
      needsRefresh: true,
    });
  },
}));
