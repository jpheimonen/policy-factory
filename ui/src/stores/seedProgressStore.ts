/**
 * Seed progress zustand store.
 *
 * Tracks real-time progress of seed operations per-layer.
 * Updated by WebSocket events dispatched through useEventDispatch.
 *
 * State shape: a Record<layer_slug, progress_info | null>.
 * Null means no active seed for that layer.
 */
import { create } from "zustand";
import type {
  SeedStartedEvent,
  SeedProgressEvent,
  SeedCompletedEvent,
} from "@/types/events.ts";

// ── Types ──────────────────────────────────────────────────────────────

export interface SeedLayerProgress {
  /** Current step identifier (agent_running, parsing, writing, committing, cascade) */
  step: string;
  /** Human-readable progress message */
  message: string;
  /** Whether the operation is complete */
  done: boolean;
  /** Success/failure (only meaningful when done=true) */
  success?: boolean;
}

interface SeedProgressState {
  /** Per-layer progress. Key = layer slug. */
  progress: Record<string, SeedLayerProgress | null>;

  // Event handlers
  handleSeedStarted: (event: SeedStartedEvent) => void;
  handleSeedProgress: (event: SeedProgressEvent) => void;
  handleSeedCompleted: (event: SeedCompletedEvent) => void;

  /** Clear progress for a specific layer */
  clearLayer: (layerSlug: string) => void;
}

// ── Store ──────────────────────────────────────────────────────────────

export const useSeedProgressStore = create<SeedProgressState>((set) => ({
  progress: {},

  handleSeedStarted: (event) => {
    set((state) => ({
      progress: {
        ...state.progress,
        [event.layer_slug]: {
          step: "starting",
          message: `Starting ${event.agent_label}…`,
          done: false,
        },
      },
    }));
  },

  handleSeedProgress: (event) => {
    set((state) => ({
      progress: {
        ...state.progress,
        [event.layer_slug]: {
          step: event.step,
          message: event.message,
          done: false,
        },
      },
    }));
  },

  handleSeedCompleted: (event) => {
    set((state) => ({
      progress: {
        ...state.progress,
        [event.layer_slug]: {
          step: "done",
          message: event.message,
          done: true,
          success: event.success,
        },
      },
    }));
  },

  clearLayer: (layerSlug) => {
    set((state) => ({
      progress: {
        ...state.progress,
        [layerSlug]: null,
      },
    }));
  },
}));
