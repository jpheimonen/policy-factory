/**
 * Auth zustand store.
 *
 * Manages JWT authentication state:
 * - Login, register, logout, refresh actions
 * - JWT persistence to localStorage
 * - Token restoration on app load
 * - Computed: isAuthenticated, isAdmin
 *
 * Pattern follows themeStore.ts and cc-runner's projectInfoStore.ts.
 */
import { create } from "zustand";
import {
  apiRequest,
  getStoredToken,
  setStoredToken,
  removeStoredToken,
  setClientToken,
  setOnAuthFailure,
} from "@/lib/apiClient.ts";

// ── Types ────────────────────────────────────────────────────────────

export interface UserInfo {
  id: string;
  email: string;
  role: string;
  created_at: string;
}

interface TokenResponse {
  token: string;
  user: UserInfo;
}

interface AuthStatusResponse {
  has_users: boolean;
  local_mode: boolean;
}

// ── JWT decoding (without verification) ──────────────────────────────

/**
 * Decode JWT payload without signature verification.
 * Used only for extracting user info from a stored token on app load.
 * The server will reject expired/invalid tokens on first API call.
 */
function decodeJwtPayload(token: string): {
  sub: string;
  email: string;
  role: string;
  exp: number;
} | null {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;
    const payload = JSON.parse(atob(parts[1]));
    return payload;
  } catch {
    return null;
  }
}

// ── Store definition ─────────────────────────────────────────────────

interface AuthState {
  /** The JWT access token (or null if not logged in) */
  token: string | null;
  /** Current user info (or null if not logged in) */
  user: UserInfo | null;
  /** Whether an async auth operation is in progress */
  loading: boolean;
  /** Auth error message for display in the UI */
  error: string | null;
  /** Whether the initial auth check has completed */
  initialized: boolean;
  /** Whether the system has existing users (for first-user detection) */
  hasUsers: boolean | null;

  // Computed
  /** True if a JWT is present */
  isAuthenticated: boolean;
  /** True if the current user has the admin role */
  isAdmin: boolean;

  // Actions
  login: (email: string, password: string) => Promise<boolean>;
  register: (email: string, password: string) => Promise<boolean>;
  logout: () => void;
  refresh: () => Promise<void>;
  initialize: () => Promise<void>;
  clearError: () => void;
  checkHasUsers: () => Promise<boolean>;
}

export const useAuthStore = create<AuthState>((set, get) => {
  // Register auth failure callback so the API client can trigger logout
  setOnAuthFailure(() => {
    get().logout();
  });

  return {
    token: null,
    user: null,
    loading: false,
    error: null,
    initialized: false,
    hasUsers: null,
    isAuthenticated: false,
    isAdmin: false,

    login: async (email: string, password: string): Promise<boolean> => {
      set({ loading: true, error: null });
      try {
        const data = await apiRequest<TokenResponse>("/api/auth/login", {
          method: "POST",
          body: { email, password },
          skipAuth: true,
        });

        setStoredToken(data.token);
        setClientToken(data.token);

        set({
          token: data.token,
          user: data.user,
          loading: false,
          error: null,
          isAuthenticated: true,
          isAdmin: data.user.role === "admin",
        });
        return true;
      } catch (err: unknown) {
        const detail =
          err && typeof err === "object" && "detail" in err
            ? String((err as { detail: string }).detail)
            : "Login failed";
        set({ loading: false, error: detail });
        return false;
      }
    },

    register: async (email: string, password: string): Promise<boolean> => {
      set({ loading: true, error: null });
      try {
        const data = await apiRequest<TokenResponse>("/api/auth/register", {
          method: "POST",
          body: { email, password },
          skipAuth: true,
        });

        setStoredToken(data.token);
        setClientToken(data.token);

        set({
          token: data.token,
          user: data.user,
          loading: false,
          error: null,
          hasUsers: true,
          isAuthenticated: true,
          isAdmin: data.user.role === "admin",
        });
        return true;
      } catch (err: unknown) {
        const detail =
          err && typeof err === "object" && "detail" in err
            ? String((err as { detail: string }).detail)
            : "Registration failed";
        set({ loading: false, error: detail });
        return false;
      }
    },

    logout: () => {
      removeStoredToken();
      setClientToken(null);
      set({
        token: null,
        user: null,
        error: null,
        loading: false,
        isAuthenticated: false,
        isAdmin: false,
      });
    },

    refresh: async () => {
      const { token } = get();
      if (!token) return;

      try {
        const data = await apiRequest<TokenResponse>("/api/auth/refresh", {
          method: "POST",
        });

        setStoredToken(data.token);
        setClientToken(data.token);

        set({
          token: data.token,
          user: data.user,
          isAuthenticated: true,
          isAdmin: data.user.role === "admin",
        });
      } catch {
        // Refresh failed — logout
        get().logout();
      }
    },

    initialize: async () => {
      // First, check auth status to see if we're in local mode
      try {
        const statusData = await apiRequest<AuthStatusResponse>(
          "/api/auth/status",
          { skipAuth: true }
        );

        // Local mode bypass — auto-authenticate as admin
        if (statusData.local_mode) {
          set({
            token: "local-mode-bypass",
            user: {
              id: "local-admin",
              email: "admin@local",
              role: "admin",
              created_at: "",
            },
            isAuthenticated: true,
            isAdmin: true,
            initialized: true,
            hasUsers: true,
          });
          return;
        }

        // Not local mode — proceed with normal auth flow
        const storedToken = getStoredToken();

        if (storedToken) {
          // Decode token to extract user info (without server validation)
          const payload = decodeJwtPayload(storedToken);
          if (payload) {
            // Check if token is expired
            const now = Date.now() / 1000;
            if (payload.exp > now) {
              setClientToken(storedToken);
              set({
                token: storedToken,
                user: {
                  id: payload.sub,
                  email: payload.email,
                  role: payload.role,
                  created_at: "",
                },
                isAuthenticated: true,
                isAdmin: payload.role === "admin",
                initialized: true,
                hasUsers: statusData.has_users,
              });
              return;
            }
          }

          // Token was invalid or expired — clean up
          removeStoredToken();
          setClientToken(null);
        }

        // No valid stored token
        set({ initialized: true, hasUsers: statusData.has_users });
      } catch {
        // Network error — fall back to stored token check
        const storedToken = getStoredToken();
        if (storedToken) {
          const payload = decodeJwtPayload(storedToken);
          if (payload && payload.exp > Date.now() / 1000) {
            setClientToken(storedToken);
            set({
              token: storedToken,
              user: {
                id: payload.sub,
                email: payload.email,
                role: payload.role,
                created_at: "",
              },
              isAuthenticated: true,
              isAdmin: payload.role === "admin",
              initialized: true,
              hasUsers: true,
            });
            return;
          }
          removeStoredToken();
          setClientToken(null);
        }
        set({ initialized: true, hasUsers: null });
      }
    },

    clearError: () => {
      set({ error: null });
    },

    checkHasUsers: async (): Promise<boolean> => {
      try {
        const data = await apiRequest<AuthStatusResponse>("/api/auth/status", {
          skipAuth: true,
        });
        const hasUsers = data.has_users;
        set({ hasUsers });
        return hasUsers;
      } catch {
        // On error, default to assuming users exist (show login)
        return true;
      }
    },
  };
});
