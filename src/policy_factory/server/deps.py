"""Dependency injection for FastAPI routes."""

import logging
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from policy_factory.auth import decode_access_token
from policy_factory.store import PolicyStore
from policy_factory.store.auth import UserPublic

logger = logging.getLogger(__name__)

# Global instances (set during app startup)
_store: PolicyStore | None = None
_ws_manager: object | None = None

# Security scheme for Bearer token extraction
_bearer_scheme = HTTPBearer(auto_error=False)


def init_deps(
    store: PolicyStore | None = None,
    ws_manager: object | None = None,
) -> None:
    """Initialize global dependencies.

    Called during FastAPI lifespan startup to set up shared resources.
    """
    global _store, _ws_manager
    _store = store
    _ws_manager = ws_manager


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

    Raises:
        HTTPException 401: If no auth header, invalid/expired token, or user not found.
    """
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
