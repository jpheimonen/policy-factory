"""Dependency injection for FastAPI routes."""

import logging

logger = logging.getLogger(__name__)

# Global instances (set during app startup)
_store: object | None = None
_ws_manager: object | None = None


def init_deps(
    store: object | None = None,
    ws_manager: object | None = None,
) -> None:
    """Initialize global dependencies.

    Called during FastAPI lifespan startup to set up shared resources.
    """
    global _store, _ws_manager
    _store = store
    _ws_manager = ws_manager


def get_store() -> object:
    """Get the store instance.

    Returns:
        The store instance.

    Raises:
        RuntimeError: If the store has not been initialized.
    """
    if _store is None:
        raise RuntimeError("Store not initialized - call init_deps() first")
    return _store


def get_ws_manager() -> object:
    """Get the WebSocket manager instance.

    Returns:
        The WebSocket manager instance.

    Raises:
        RuntimeError: If the WebSocket manager has not been initialized.
    """
    if _ws_manager is None:
        raise RuntimeError("WebSocket manager not initialized - call init_deps() first")
    return _ws_manager
