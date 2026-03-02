/**
 * Global WebSocket hook for Policy Factory.
 *
 * Manages a single WebSocket connection to `/ws?token=<JWT>` with:
 * - Auto-reconnection with exponential backoff (1s initial, 15s max, 8 attempts)
 * - Event deduplication by database-generated ID (rolling window)
 * - REST replay of missed events on reconnection
 * - Dispatching validated events to zustand stores via the central dispatcher
 *
 * Adapted from cc-runner's useWebSocket hook with key differences:
 * - JWT in query parameter (cc-runner uses cookies)
 * - Global connection (cc-runner is per-run)
 * - Store-based dispatch (cc-runner returns events array)
 *
 * The hook is initialised at the app level inside the protected route area
 * so it only activates when the user is authenticated.
 */
import { useEffect, useRef, useState, useCallback } from "react";
import { useAuthStore } from "@/stores/authStore.ts";
import { useEventDispatch } from "@/hooks/useEventDispatch.ts";
import { useCascadeStore } from "@/stores/cascadeStore.ts";
import { useLayerStore } from "@/stores/layerStore.ts";
import { apiRequest } from "@/lib/apiClient.ts";
import type {
  PolicyEvent,
  ReplayResponse,
  ReplayEvent,
  EventType,
} from "@/types/events.ts";

// ── Constants ────────────────────────────────────────────────────────

const INITIAL_BACKOFF_MS = 1000;
const MAX_BACKOFF_MS = 15000;
const MAX_RECONNECT_ATTEMPTS = 8;

/** Max size of the seen-IDs dedup window. */
const DEDUP_WINDOW_SIZE = 1000;

// ── Hook ─────────────────────────────────────────────────────────────

export interface WebSocketState {
  /** Whether the WebSocket is currently open */
  connected: boolean;
  /** Whether a reconnection attempt is in progress */
  reconnecting: boolean;
  /** Whether all reconnection attempts have been exhausted */
  disconnected: boolean;
  /** Manually trigger a reconnection (resets attempt counter) */
  reconnect: () => void;
  /** Send a JSON message to the backend (fire-and-forget) */
  send: (message: Record<string, unknown>) => void;
}

export function useWebSocket(): WebSocketState {
  const [connected, setConnected] = useState(false);
  const [reconnecting, setReconnecting] = useState(false);
  const [disconnected, setDisconnected] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptRef = useRef(0);
  const intentionalCloseRef = useRef(false);
  const lastEventIdRef = useRef<number>(0);
  const seenIdsRef = useRef<Set<number>>(new Set());
  const mountedRef = useRef(true);
  const connectRef = useRef<() => void>(() => {});

  const dispatch = useEventDispatch();

  const clearReconnectTimer = useCallback(() => {
    if (reconnectTimerRef.current !== null) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
  }, []);

  /** Convert a replay event (from REST) into a PolicyEvent for dispatch. */
  const replayEventToPolicy = useCallback((e: ReplayEvent): PolicyEvent => {
    return {
      db_id: e.id,
      id: (e.data.id as string) ?? "",
      event_type: e.event_type as EventType,
      timestamp: e.timestamp,
      ...e.data,
    } as PolicyEvent;
  }, []);

  /** Track a seen event ID. Trims the set if it exceeds the window size. */
  const trackSeenId = useCallback((dbId: number) => {
    seenIdsRef.current.add(dbId);
    if (dbId > lastEventIdRef.current) {
      lastEventIdRef.current = dbId;
    }
    // Trim: if the set gets too large, keep only the most recent IDs
    if (seenIdsRef.current.size > DEDUP_WINDOW_SIZE) {
      const sorted = Array.from(seenIdsRef.current).sort((a, b) => a - b);
      const trimmed = sorted.slice(sorted.length - Math.floor(DEDUP_WINDOW_SIZE * 0.75));
      seenIdsRef.current = new Set(trimmed);
    }
  }, []);

  /** Process and dispatch an event (shared between live and replay). */
  const processEvent = useCallback(
    (event: PolicyEvent) => {
      if (!event.db_id || seenIdsRef.current.has(event.db_id)) return;
      trackSeenId(event.db_id);
      dispatch(event);
    },
    [dispatch, trackSeenId],
  );

  /** Full store refresh (used when too many events were missed). */
  const fullRefresh = useCallback(() => {
    useCascadeStore.getState().refresh();
    useLayerStore.getState().refresh();
    // Other stores will be refreshed when their pages are visited
  }, []);

  /** Replay missed events from the REST endpoint. */
  const replayMissedEvents = useCallback(
    async (sinceId: number) => {
      try {
        const data = await apiRequest<ReplayResponse>(
          `/api/activity/replay?since_id=${sinceId}`,
        );

        if (data.overflow) {
          // Too many events missed — do a full refresh instead
          fullRefresh();
          // Still process the replayed events for the activity store
          for (const e of data.events) {
            processEvent(replayEventToPolicy(e));
          }
          return;
        }

        // Process replayed events in chronological order
        for (const e of data.events) {
          processEvent(replayEventToPolicy(e));
        }
      } catch {
        // Replay failed — continue with live events only (graceful degradation)
      }
    },
    [processEvent, replayEventToPolicy, fullRefresh],
  );

  const connect = useCallback(() => {
    // Get the current JWT
    const token = useAuthStore.getState().token;
    if (!token) return;

    // Auto-detect protocol
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${protocol}//${window.location.host}/ws?token=${encodeURIComponent(token)}`;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      if (!mountedRef.current) return;

      setConnected(true);
      setReconnecting(false);
      setDisconnected(false);

      const isReconnect = reconnectAttemptRef.current > 0;
      reconnectAttemptRef.current = 0;

      if (isReconnect && lastEventIdRef.current > 0) {
        // Replay missed events from the REST endpoint
        replayMissedEvents(lastEventIdRef.current);
      }
    };

    ws.onclose = () => {
      if (!mountedRef.current) return;

      setConnected(false);
      wsRef.current = null;

      if (intentionalCloseRef.current) return;

      // Unexpected close — attempt reconnection with exponential backoff
      reconnectAttemptRef.current += 1;

      if (reconnectAttemptRef.current > MAX_RECONNECT_ATTEMPTS) {
        setReconnecting(false);
        setDisconnected(true);
        return;
      }

      setReconnecting(true);

      const delay = Math.min(
        INITIAL_BACKOFF_MS * Math.pow(2, reconnectAttemptRef.current - 1),
        MAX_BACKOFF_MS,
      );

      reconnectTimerRef.current = setTimeout(() => {
        reconnectTimerRef.current = null;
        if (!intentionalCloseRef.current && mountedRef.current) {
          connectRef.current();
        }
      }, delay);
    };

    ws.onerror = () => {
      // onerror is always followed by onclose — reconnection handled there
      if (mountedRef.current) {
        setConnected(false);
      }
    };

    ws.onmessage = (msgEvent) => {
      try {
        const data = JSON.parse(msgEvent.data);

        // Basic sanity check: must have event_type
        if (!data || !data.event_type) return;

        // Construct a PolicyEvent from the WebSocket payload.
        // WS events have `db_id` (integer from broadcast handler).
        const event: PolicyEvent = {
          ...data,
          db_id: data.db_id ?? 0,
        } as PolicyEvent;

        if (event.db_id > 0) {
          processEvent(event);
        } else {
          // No db_id — dispatch without dedup (shouldn't normally happen)
          dispatch(event);
        }
      } catch {
        // Malformed JSON — silently ignore
      }
    };
  }, [dispatch, processEvent, replayMissedEvents]);

  // Keep the ref in sync with the latest connect function (in an effect to avoid render-time updates)
  useEffect(() => {
    connectRef.current = connect;
  }, [connect]);

  /** Manual reconnect — resets attempt counter and tries again. */
  const reconnect = useCallback(() => {
    clearReconnectTimer();
    intentionalCloseRef.current = false;
    reconnectAttemptRef.current = 0;
    setDisconnected(false);
    setReconnecting(true);

    // Close existing connection if any
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    connect();
  }, [connect, clearReconnectTimer]);

  /** Send a JSON message to the backend. Fire-and-forget. */
  const send = useCallback((message: Record<string, unknown>) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    }
  }, []);

  // ── Effect: connect on mount, disconnect on unmount ─────────────

  useEffect(() => {
    mountedRef.current = true;
    const token = useAuthStore.getState().token;

    if (token) {
      connect();
    }

    return () => {
      mountedRef.current = false;
      intentionalCloseRef.current = true;
      clearReconnectTimer();
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect, clearReconnectTimer]);

  // ── Effect: react to auth state changes ─────────────────────────

  useEffect(() => {
    // Subscribe to auth store token changes
    const unsubscribe = useAuthStore.subscribe((state, prevState) => {
      const tokenChanged = state.token !== prevState.token;
      if (!tokenChanged) return;

      if (state.token) {
        // Token appeared or changed — (re)connect
        if (wsRef.current) {
          intentionalCloseRef.current = true;
          wsRef.current.close();
          wsRef.current = null;
        }
        intentionalCloseRef.current = false;
        reconnectAttemptRef.current = 0;
        connect();
      } else {
        // Token removed (logout) — disconnect
        intentionalCloseRef.current = true;
        clearReconnectTimer();
        if (wsRef.current) {
          wsRef.current.close();
          wsRef.current = null;
        }
        setConnected(false);
        setReconnecting(false);
        setDisconnected(false);
      }
    });

    return unsubscribe;
  }, [connect, clearReconnectTimer]);

  return { connected, reconnecting, disconnected, reconnect, send };
}
