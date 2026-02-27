"""FastAPI application with REST API, WebSocket, and static file serving."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from importlib.resources import files
from pathlib import Path
from typing import TYPE_CHECKING, AsyncGenerator

import jwt as pyjwt
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from policy_factory.auth import decode_access_token
from policy_factory.data.init import get_data_dir, initialize_data_directory
from policy_factory.server.deps import init_deps
from policy_factory.server.routers import auth_router, health_router, users_router

if TYPE_CHECKING:
    from policy_factory.store import PolicyStore

logger = logging.getLogger(__name__)


def create_app(
    store: PolicyStore | None = None,
    ws_manager: object | None = None,
    data_dir: Path | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        store: PolicyStore instance (or None for testing).
        ws_manager: WebSocket connection manager (or None).
        data_dir: Override for the data directory path. If None, uses
            the ``POLICY_FACTORY_DATA_DIR`` env var or defaults to ``data/``.
    """
    # Resolve the data directory path (but don't initialize yet — that happens in lifespan)
    resolved_data_dir = data_dir if data_dir is not None else get_data_dir()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        # Startup: initialize data directory (first-run setup)
        try:
            initialize_data_directory(resolved_data_dir)
        except OSError:
            logger.exception("Failed to initialize data directory at %s", resolved_data_dir)
            raise

        # Startup: initialize dependencies
        init_deps(
            store=store,
            ws_manager=ws_manager,
            data_dir=resolved_data_dir,
        )
        yield
        # Shutdown: cleanup if needed

    app = FastAPI(title="Policy Factory", lifespan=lifespan)

    # --- Include API Routers ---
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(users_router)

    # --- WebSocket endpoint with JWT authentication ---
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        """WebSocket endpoint with JWT authentication via query parameter.

        The client passes the JWT as a query parameter: /ws?token=<jwt>
        The server validates the token during the handshake and rejects
        invalid connections.
        """
        token = websocket.query_params.get("token")

        if not token:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        # Validate the token
        try:
            payload = decode_access_token(token)
        except (pyjwt.ExpiredSignatureError, pyjwt.InvalidTokenError):
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        # Verify the user still exists
        if store is None:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
            return

        user = store.get_user_by_id(payload.user_id)
        if user is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        # Accept the connection
        await websocket.accept()

        try:
            while True:
                # Keep the connection alive — receive and discard client messages
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass

    # --- Static File Serving ---

    # SPA fallback: catch-all for non-API routes returns index.html
    # This must be defined AFTER API routes but BEFORE mounting static files
    @app.get("/{path:path}")
    async def spa_fallback(path: str) -> FileResponse:
        """Serve index.html for client-side routing (SPA fallback)."""
        # Don't intercept API or WebSocket routes
        if path.startswith("api/") or path == "ws":
            raise HTTPException(status_code=404)

        try:
            static_path = files("policy_factory") / "static" / "dist"
            # First try to serve the exact file (for assets like favicon)
            file_path = static_path / path
            if hasattr(file_path, "is_file") and file_path.is_file():
                return FileResponse(str(file_path))

            # Fall back to index.html for SPA routing
            index_path = static_path / "index.html"
            if hasattr(index_path, "is_file") and index_path.is_file():
                return FileResponse(str(index_path))
        except (TypeError, FileNotFoundError):
            pass

        raise HTTPException(status_code=404, detail="Frontend not built")

    # Mount static assets directory (if it exists)
    try:
        static_path = files("policy_factory") / "static" / "dist"
        assets_path = static_path / "assets"
        if hasattr(assets_path, "is_dir") and assets_path.is_dir():
            app.mount(
                "/assets",
                StaticFiles(directory=str(assets_path)),
                name="assets",
            )
    except (TypeError, FileNotFoundError):
        pass  # Static files not built yet - dev mode

    return app
