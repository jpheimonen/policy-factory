"""Dependency injection for FastAPI routes."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from policy_factory.auth import decode_access_token
from policy_factory.store import PolicyStore
from policy_factory.store.auth import UserPublic

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    from policy_factory.cascade.controller import CascadeController
    from policy_factory.events import EventEmitter
    from policy_factory.server.broadcast import BroadcastHandler
    from policy_factory.server.ws import ConnectionManager

logger = logging.getLogger(__name__)

# Global instances (set during app startup)
_store: PolicyStore | None = None
_ws_manager: ConnectionManager | None = None
_event_emitter: EventEmitter | None = None
_broadcast_handler: BroadcastHandler | None = None
_data_dir: Path | None = None
_scheduler: AsyncIOScheduler | None = None

# Cascade controller registry — maps cascade ID → controller instance
_cascade_controllers: dict[str, CascadeController] = {}

# Security scheme for Bearer token extraction
_bearer_scheme = HTTPBearer(auto_error=False)

# Default heartbeat interval in hours
_DEFAULT_HEARTBEAT_INTERVAL_HOURS = 4.0


def init_deps(
    store: PolicyStore | None = None,
    ws_manager: ConnectionManager | None = None,
    event_emitter: EventEmitter | None = None,
    broadcast_handler: BroadcastHandler | None = None,
    data_dir: Path | None = None,
) -> None:
    """Initialize global dependencies.

    Called during FastAPI lifespan startup to set up shared resources.
    """
    global _store, _ws_manager, _event_emitter, _broadcast_handler, _data_dir
    _store = store
    _ws_manager = ws_manager
    _event_emitter = event_emitter
    _broadcast_handler = broadcast_handler
    _data_dir = data_dir


def get_store() -> PolicyStore:
    """Get the store instance.

    Returns:
        The PolicyStore instance.

    Raises:
        RuntimeError: If the store has not been initialized.
    """
    if _store is None:
        raise RuntimeError("Store not initialized - call init_deps() first")
    return _store


def get_data_dir() -> Path:
    """Get the data directory path.

    Returns:
        The configured data directory path.

    Raises:
        RuntimeError: If the data directory has not been initialized.
    """
    if _data_dir is None:
        raise RuntimeError("Data directory not initialized - call init_deps() first")
    return _data_dir


def get_ws_manager() -> ConnectionManager:
    """Get the WebSocket connection manager instance.

    Returns:
        The ConnectionManager instance.

    Raises:
        RuntimeError: If the WebSocket manager has not been initialized.
    """
    if _ws_manager is None:
        raise RuntimeError("WebSocket manager not initialized - call init_deps() first")
    return _ws_manager


def get_event_emitter() -> EventEmitter:
    """Get the EventEmitter singleton.

    This is the single shared emitter instance used by all code that
    needs to emit events (cascade orchestrator, critic runner, heartbeat,
    etc.).

    Returns:
        The EventEmitter instance.

    Raises:
        RuntimeError: If the event emitter has not been initialized.
    """
    if _event_emitter is None:
        raise RuntimeError("Event emitter not initialized - call init_deps() first")
    return _event_emitter


# ---------------------------------------------------------------------------
# Cascade controller registry
# ---------------------------------------------------------------------------


def register_cascade_controller(
    cascade_id: str, controller: CascadeController
) -> None:
    """Register an active cascade controller.

    Args:
        cascade_id: The cascade run ID.
        controller: The CascadeController instance.
    """
    _cascade_controllers[cascade_id] = controller


def get_cascade_controller(cascade_id: str) -> CascadeController | None:
    """Get the controller for a cascade, or None if not found.

    Args:
        cascade_id: The cascade run ID.

    Returns:
        The CascadeController, or None if not registered.
    """
    return _cascade_controllers.get(cascade_id)


def unregister_cascade_controller(cascade_id: str) -> None:
    """Remove a controller from the registry.

    Args:
        cascade_id: The cascade run ID.
    """
    _cascade_controllers.pop(cascade_id, None)


def get_active_cascade_id() -> str | None:
    """Return the ID of the currently running/paused cascade, or None.

    Returns:
        The cascade ID, or None if no cascade is active.
    """
    for cid, controller in _cascade_controllers.items():
        from policy_factory.cascade.controller import CascadeState

        if controller.state in (CascadeState.RUNNING, CascadeState.PAUSED):
            return cid
    return None


# ---------------------------------------------------------------------------
# Scheduler management
# ---------------------------------------------------------------------------


def _get_heartbeat_interval_hours() -> float:
    """Get the configured heartbeat interval in hours.

    Returns 0 if disabled via environment variable.
    """
    env_val = os.environ.get("POLICY_FACTORY_HEARTBEAT_INTERVAL_HOURS")
    if env_val is not None:
        try:
            return float(env_val)
        except (ValueError, TypeError):
            logger.warning(
                "Invalid POLICY_FACTORY_HEARTBEAT_INTERVAL_HOURS=%r, "
                "using default %.1f",
                env_val,
                _DEFAULT_HEARTBEAT_INTERVAL_HOURS,
            )
    return _DEFAULT_HEARTBEAT_INTERVAL_HOURS


def init_scheduler(
    store: PolicyStore,
    emitter: EventEmitter,
    data_dir: Path,
) -> AsyncIOScheduler | None:
    """Create and configure the APScheduler with the heartbeat job.

    The heartbeat interval is configurable via the
    ``POLICY_FACTORY_HEARTBEAT_INTERVAL_HOURS`` environment variable.
    Setting it to 0 disables the scheduled heartbeat.

    Args:
        store: PolicyStore for persistence.
        emitter: EventEmitter for broadcasting events.
        data_dir: Root data directory.

    Returns:
        The configured AsyncIOScheduler, or None if the heartbeat is disabled.
    """
    global _scheduler

    interval_hours = _get_heartbeat_interval_hours()

    if interval_hours <= 0:
        logger.info("Heartbeat scheduler disabled (interval=0)")
        _scheduler = None
        return None

    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.interval import IntervalTrigger

    scheduler = AsyncIOScheduler()

    # Create the heartbeat job function with bound dependencies
    async def _heartbeat_job() -> None:
        """Scheduled heartbeat job — thin wrapper around the orchestrator."""
        from policy_factory.heartbeat.orchestrator import run_heartbeat

        # Concurrency guard: skip if a heartbeat is already running
        if store.has_running_heartbeat():
            logger.info("Skipping scheduled heartbeat — previous run still active")
            return

        try:
            # Import cascade trigger and idea generator lazily
            cascade_trigger = None
            idea_generator = None

            try:
                from policy_factory.cascade.orchestrator import trigger_cascade
                cascade_trigger = trigger_cascade
            except ImportError:
                logger.warning("Cascade trigger not available")

            try:
                from policy_factory.ideas.generator import generate_ideas
                idea_generator = generate_ideas
            except ImportError:
                logger.warning("Idea generator not available")

            await run_heartbeat(
                trigger="scheduled",
                store=store,
                emitter=emitter,
                data_dir=data_dir,
                cascade_trigger=cascade_trigger,
                idea_generator=idea_generator,
            )
        except Exception:
            logger.exception("Scheduled heartbeat job failed unexpectedly")

    # Add the job with interval trigger and coalescing
    scheduler.add_job(
        _heartbeat_job,
        trigger=IntervalTrigger(hours=interval_hours),
        id="heartbeat",
        name="Heartbeat — tiered news monitoring",
        coalesce=True,
        max_instances=1,
        misfire_grace_time=3600,  # 1 hour grace for missed jobs
    )

    _scheduler = scheduler
    logger.info(
        "Heartbeat scheduler configured: interval=%.1f hours", interval_hours
    )
    return scheduler


def get_scheduler() -> AsyncIOScheduler | None:
    """Get the APScheduler instance, or None if not initialized/disabled.

    Returns:
        The AsyncIOScheduler, or None.
    """
    return _scheduler


def shutdown_scheduler() -> None:
    """Gracefully shut down the scheduler.

    Waits for any running heartbeat to complete (with a reasonable timeout).
    """
    global _scheduler
    if _scheduler is not None:
        try:
            _scheduler.shutdown(wait=True)
            logger.info("Heartbeat scheduler shut down")
        except Exception:
            logger.exception("Error shutting down scheduler")
        _scheduler = None


def _is_local_mode() -> bool:
    """Check if local mode (auth bypass) is enabled."""
    return os.environ.get("POLICY_FACTORY_LOCAL_MODE", "").lower() in ("true", "1", "yes")


# Mock admin user for local mode — singleton to avoid recreating
_LOCAL_ADMIN_USER = UserPublic(
    id="local-admin",
    email="admin@local",
    role="admin",
    created_at=datetime(2000, 1, 1, tzinfo=timezone.utc),
)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    store: Annotated[PolicyStore, Depends(get_store)],
) -> UserPublic:
    """Extract and validate the current user from the JWT.

    This dependency:
    1. Extracts the JWT from the Authorization: Bearer <token> header
    2. Decodes and validates the token
    3. Looks up the user in the database (to ensure they still exist)
    4. Returns the user record (without password hash)

    In local mode (POLICY_FACTORY_LOCAL_MODE=true), bypasses auth entirely
    and returns a mock admin user. NEVER enable in production.

    Raises:
        HTTPException 401: If no auth header, invalid/expired token, or user not found.
    """
    # Local mode bypass — return mock admin without any auth checks
    if _is_local_mode():
        return _LOCAL_ADMIN_USER

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify the user still exists in the database
    user = store.get_user_by_id(payload.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Return UserPublic (no password hash)
    return UserPublic(
        id=user.id,
        email=user.email,
        role=user.role,
        created_at=user.created_at,
    )


async def require_admin(
    current_user: Annotated[UserPublic, Depends(get_current_user)],
) -> UserPublic:
    """Require the current user to be an admin.

    Chains the get_current_user dependency, then checks the role.

    Returns:
        The admin user record.

    Raises:
        HTTPException 403: If the user is not an admin.
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user
