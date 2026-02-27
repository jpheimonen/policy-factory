"""FastAPI application with REST API, WebSocket, and static file serving."""

import logging
from contextlib import asynccontextmanager
from importlib.resources import files
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from policy_factory.server.deps import init_deps
from policy_factory.server.routers import health_router

logger = logging.getLogger(__name__)


def create_app(
    store: object | None = None,
    ws_manager: object | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        # Startup: initialize dependencies
        init_deps(
            store=store,
            ws_manager=ws_manager,
        )
        yield
        # Shutdown: cleanup if needed

    app = FastAPI(title="Policy Factory", lifespan=lifespan)

    # --- Include API Routers ---
    app.include_router(health_router)

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
