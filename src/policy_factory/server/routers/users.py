"""Users router — admin-only user management endpoints."""

from __future__ import annotations

import logging
import re
import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel

from policy_factory.auth import hash_password
from policy_factory.server.deps import get_store, require_admin
from policy_factory.store import PolicyStore
from policy_factory.store.auth import UserPublic

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/users", tags=["users"])

# Minimum password length (same as auth router)
MIN_PASSWORD_LENGTH = 8


# --- Request/Response Models ---


class CreateUserRequest(BaseModel):
    """Request body for creating a new user."""

    email: str
    password: str


class UserInfoResponse(BaseModel):
    """Public user information in responses."""

    id: str
    email: str
    role: str
    created_at: str


class UserListResponse(BaseModel):
    """Response containing a list of users."""

    users: list[UserInfoResponse]


def _to_user_info(user: UserPublic) -> UserInfoResponse:
    """Convert a UserPublic to a response model."""
    return UserInfoResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        created_at=user.created_at.isoformat(),
    )


# --- Endpoints ---


@router.get("/")
async def list_users(
    admin: Annotated[UserPublic, Depends(require_admin)],
    store: Annotated[PolicyStore, Depends(get_store)],
) -> UserListResponse:
    """List all users. Admin-only.

    Returns all users with public info (no password hashes).
    """
    users = store.list_users()
    return UserListResponse(users=[_to_user_info(u) for u in users])


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_user(
    body: CreateUserRequest,
    admin: Annotated[UserPublic, Depends(require_admin)],
    store: Annotated[PolicyStore, Depends(get_store)],
) -> UserInfoResponse:
    """Create a new user. Admin-only.

    Creates a user with the "user" role. Admin-created accounts
    are always regular users — no way to create additional admins
    via this endpoint.
    """
    # Validate email
    if not body.email or not body.email.strip():
        raise HTTPException(
            status_code=422,
            detail="Email is required",
        )
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", body.email.strip()):
        raise HTTPException(
            status_code=422,
            detail="Invalid email format",
        )

    # Validate password
    if not body.password:
        raise HTTPException(
            status_code=422,
            detail="Password is required",
        )
    if len(body.password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=422,
            detail=f"Password must be at least {MIN_PASSWORD_LENGTH} characters",
        )

    # Check for duplicate email
    if store.email_exists(body.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Hash password and create user
    hashed = hash_password(body.password)

    try:
        user_id = store.create_user(body.email, hashed, "user")
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = store.get_user_by_id(user_id)
    assert user is not None  # Just created it

    user_public = UserPublic(
        id=user.id,
        email=user.email,
        role=user.role,
        created_at=user.created_at,
    )

    return _to_user_info(user_public)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    admin: Annotated[UserPublic, Depends(require_admin)],
    store: Annotated[PolicyStore, Depends(get_store)],
) -> Response:
    """Delete a user by ID. Admin-only.

    An admin cannot delete themselves — returns 400.
    Returns 404 if the user ID doesn't exist.
    Returns 204 on successful deletion.
    """
    # Prevent self-deletion
    if user_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account",
        )

    # Check user exists
    user = store.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    store.delete_user(user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
