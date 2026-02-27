/**
 * Theme preference store.
 *
 * Manages dark/light theme selection with three modes:
 * - "system": follows OS-level prefers-color-scheme (default)
 * - "dark": always dark
 * - "light": always light
 *
 * Persists to localStorage and listens for OS theme changes.
 */
import { create } from "zustand";
import { darkTheme, lightTheme } from "@/styles/theme.ts";
import type { Theme } from "@/styles/theme.ts";

const STORAGE_KEY = "policy-factory-theme-preference";

export type ThemePreference = "system" | "dark" | "light";

interface ThemeState {
  /** The user's chosen preference: system, dark, or light */
  preference: ThemePreference;
  /** Whether the system (OS) currently prefers dark mode */
  systemPrefersDark: boolean;
  /** The resolved theme object based on preference + system setting */
  resolvedTheme: Theme;
  /** Update the theme preference */
  setPreference: (preference: ThemePreference) => void;
}

/** Read persisted preference from localStorage */
function getStoredPreference(): ThemePreference {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "dark" || stored === "light" || stored === "system") {
      return stored;
    }
  } catch {
    // localStorage not available (SSR, incognito, etc.)
  }
  return "system";
}

/** Detect system dark mode preference */
function getSystemPrefersDark(): boolean {
  if (typeof window === "undefined") return true;
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

/** Resolve which theme to use based on preference + system setting */
function resolveTheme(preference: ThemePreference, systemPrefersDark: boolean): Theme {
  if (preference === "dark") return darkTheme;
  if (preference === "light") return lightTheme;
  // preference === "system"
  return systemPrefersDark ? darkTheme : lightTheme;
}

const initialPreference = getStoredPreference();
const initialSystemPrefersDark = getSystemPrefersDark();

export const useThemeStore = create<ThemeState>((set) => {
  // Listen for OS theme changes
  if (typeof window !== "undefined") {
    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    mediaQuery.addEventListener("change", (e) => {
      set((state) => ({
        systemPrefersDark: e.matches,
        resolvedTheme: resolveTheme(state.preference, e.matches),
      }));
    });
  }

  return {
    preference: initialPreference,
    systemPrefersDark: initialSystemPrefersDark,
    resolvedTheme: resolveTheme(initialPreference, initialSystemPrefersDark),

    setPreference: (preference) => {
      try {
        localStorage.setItem(STORAGE_KEY, preference);
      } catch {
        // localStorage not available
      }
      set((state) => ({
        preference,
        resolvedTheme: resolveTheme(preference, state.systemPrefersDark),
      }));
    },
  };
});
