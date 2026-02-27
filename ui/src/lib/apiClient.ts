/**
 * Authenticated HTTP client for Policy Factory API.
 *
 * All API requests from the frontend use this client instead of raw `fetch`.
 * Features:
 * - Automatic `Authorization: Bearer <token>` header injection
 * - 401 interception with token refresh + retry
 * - JSON serialization/deserialization
 * - Consistent error format for UI consumption
 */

const TOKEN_KEY = "policy-factory-jwt";

// ── Error type ───────────────────────────────────────────────────────

export interface ApiError {
  status: number;
  detail: string;
}

export function isApiError(err: unknown): err is ApiError {
  return (
    typeof err === "object" &&
    err !== null &&
    "status" in err &&
    "detail" in err
  );
}

// ── Token management ─────────────────────────────────────────────────

/** Read the stored JWT from localStorage. */
export function getStoredToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

/** Store the JWT in localStorage. */
export function setStoredToken(token: string): void {
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch {
    // localStorage not available
  }
}

/** Remove the JWT from localStorage. */
export function removeStoredToken(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    // localStorage not available
  }
}

// ── Internal state ───────────────────────────────────────────────────

/** In-memory token (synced with the auth store). */
let currentToken: string | null = getStoredToken();

/** Callback to trigger logout — set by the auth store during init. */
let onAuthFailure: (() => void) | null = null;

/** Update the in-memory token (called by the auth store). */
export function setClientToken(token: string | null): void {
  currentToken = token;
}

/** Register the auth failure callback (called by the auth store). */
export function setOnAuthFailure(callback: () => void): void {
  onAuthFailure = callback;
}

// ── Token refresh logic ──────────────────────────────────────────────

let refreshPromise: Promise<string | null> | null = null;

/**
 * Attempt to refresh the JWT. Deduplicates concurrent calls.
 */
async function attemptRefresh(): Promise<string | null> {
  if (refreshPromise) return refreshPromise;

  refreshPromise = (async () => {
    try {
      const res = await fetch("/api/auth/refresh", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(currentToken ? { Authorization: `Bearer ${currentToken}` } : {}),
        },
      });

      if (!res.ok) return null;

      const data = await res.json();
      return data.token as string;
    } catch {
      return null;
    } finally {
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

// ── Core request function ────────────────────────────────────────────

interface RequestOptions {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
  /** Skip the auto-auth header (for login/register). */
  skipAuth?: boolean;
}

/**
 * Make an authenticated API request.
 *
 * Automatically includes the JWT in the Authorization header.
 * On 401, attempts token refresh and retries once.
 * On refresh failure, triggers logout.
 */
export async function apiRequest<T = unknown>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { method = "GET", body, headers = {}, skipAuth = false } = options;

  const buildHeaders = (): Record<string, string> => {
    const h: Record<string, string> = {
      "Content-Type": "application/json",
      ...headers,
    };
    if (!skipAuth && currentToken) {
      h["Authorization"] = `Bearer ${currentToken}`;
    }
    return h;
  };

  const doFetch = async (hdrs: Record<string, string>): Promise<Response> => {
    return fetch(path, {
      method,
      headers: hdrs,
      ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
    });
  };

  let res = await doFetch(buildHeaders());

  // On 401, attempt token refresh and retry once
  if (res.status === 401 && !skipAuth && currentToken) {
    const newToken = await attemptRefresh();

    if (newToken) {
      // Update token everywhere
      currentToken = newToken;
      setStoredToken(newToken);

      // Retry the original request with the new token
      const retryHeaders = buildHeaders();
      retryHeaders["Authorization"] = `Bearer ${newToken}`;
      res = await doFetch(retryHeaders);
    } else {
      // Refresh failed — trigger logout
      if (onAuthFailure) onAuthFailure();
      throw { status: 401, detail: "Session expired" } as ApiError;
    }
  }

  // Parse response
  if (!res.ok) {
    let detail = "An unexpected error occurred";
    try {
      const errBody = await res.json();
      detail = errBody.detail || detail;
    } catch {
      // Response body wasn't JSON
    }
    throw { status: res.status, detail } as ApiError;
  }

  // Handle 204 No Content
  if (res.status === 204) {
    return undefined as T;
  }

  return res.json() as Promise<T>;
}
