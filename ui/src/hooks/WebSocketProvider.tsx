/**
 * WebSocket provider component.
 *
 * Initialises the global WebSocket connection and exposes connection state
 * via React context. Rendered inside the protected route area so it only
 * activates when the user is authenticated.
 *
 * Components that need connection status (e.g., Navigation) use the
 * useWebSocketStatus() hook to read the context.
 */
import { createContext, useContext, type ReactNode } from "react";
import { useWebSocket, type WebSocketState } from "@/hooks/useWebSocket.ts";

// ── Context ──────────────────────────────────────────────────────────

const WebSocketContext = createContext<WebSocketState | null>(null);

// ── Provider ─────────────────────────────────────────────────────────

interface WebSocketProviderProps {
  children: ReactNode;
}

export function WebSocketProvider({ children }: WebSocketProviderProps) {
  const wsState = useWebSocket();

  return (
    <WebSocketContext.Provider value={wsState}>
      {children}
    </WebSocketContext.Provider>
  );
}

// ── Consumer hook ────────────────────────────────────────────────────

/**
 * Read the WebSocket connection state.
 *
 * Must be called inside a <WebSocketProvider>.
 * Returns null if called outside the provider (e.g., public routes).
 */
export function useWebSocketStatus(): WebSocketState | null {
  return useContext(WebSocketContext);
}
