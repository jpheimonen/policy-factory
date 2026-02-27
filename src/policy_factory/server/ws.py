"""WebSocket connection manager with JWT authentication.

Adapted from cc-runner's ConnectionManager, extended with JWT token
validation on connect. All authenticated connections receive all events
— no per-user or per-cascade filtering at the WebSocket level.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import jwt as pyjwt
from fastapi import WebSocket

from policy_factory.auth import decode_access_token

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections with JWT authentication.

    Tracks active connections and provides broadcast/send_to methods.
    Invalid JWTs are rejected during the connect handshake.
    """

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket, token: str | None) -> bool:
        """Validate JWT and accept the WebSocket connection.

        Args:
            websocket: The incoming WebSocket connection.
            token: JWT token from the query parameter. ``None`` if missing.

        Returns:
            True if the connection was accepted, False if rejected.
        """
        if not token:
            await websocket.close(code=4001, reason="Missing authentication token")
            return False

        try:
            decode_access_token(token)
        except (pyjwt.ExpiredSignatureError, pyjwt.InvalidTokenError) as exc:
            logger.debug("WebSocket auth rejected: %s", exc)
            await websocket.close(code=4001, reason="Invalid or expired token")
            return False

        await websocket.accept()
        self.active_connections.append(websocket)
        return True

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection from tracking."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, event: dict[str, Any]) -> None:
        """Broadcast event to all connected clients.

        If sending to a client fails (disconnected), the client is
        cleaned up automatically. Broadcasting to zero clients is a no-op.
        """
        if not self.active_connections:
            return

        message = json.dumps(event)
        disconnected: list[WebSocket] = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                disconnected.append(connection)

        for conn in disconnected:
            self.disconnect(conn)

    async def send_to(self, websocket: WebSocket, event: dict[str, Any]) -> None:
        """Send event to a specific connected client."""
        await websocket.send_text(json.dumps(event))
