"""Auth router — login, register, and token refresh endpoints."""

from __future__ import annotations

import logging
import sqlite3
from typing import Annotated

import jwt as pyjwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from policy_factory.auth import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from policy_factory.server.deps import _is_local_mode, get_current_user, get_store
from policy_factory.server.validation import validate_email, validate_password
from policy_factory.store import PolicyStore
from policy_factory.store.auth import UserPublic

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Bearer scheme that doesn't auto-error (for optional auth on register)
_optional_bearer = HTTPBearer(auto_error=False)



# --- Request/Response Models ---


class LoginRequest(BaseModel):
    """Login request body."""

    email: str
    password: str


class RegisterRequest(BaseModel):
    """Registration request body."""

    email: str
    password: str


class UserInfo(BaseModel):
    """Public user information returned in auth responses."""

    id: str
    email: str
    role: str
    created_at: str


class TokenResponse(BaseModel):
    """Response containing a JWT token and user info."""

    token: str
    user: UserInfo


class UserCreatedResponse(BaseModel):
    """Response when an admin creates a user (no token returned)."""

    user: UserInfo


def _user_info(user: UserPublic) -> UserInfo:
    """Convert a UserPublic to a UserInfo response model."""
    return UserInfo(
        id=user.id,
        email=user.email,
        role=user.role,
        created_at=user.created_at.isoformat(),
    )




def _try_get_user_from_token(
    credentials: HTTPAuthorizationCredentials | None,
    store: PolicyStore,
) -> UserPublic | None:
    """Attempt to extract a user from a Bearer token, returning None on failure.

    Unlike get_current_user, this does NOT raise — it's used where auth
    is optional (the register endpoint for the first-user flow).
    """
    if credentials is None:
        return None

    try:
        payload = decode_access_token(credentials.credentials)
    except (pyjwt.ExpiredSignatureError, pyjwt.InvalidTokenError):
        return None

    user = store.get_user_by_id(payload.user_id)
    if user is None:
        return None

    return UserPublic(
        id=user.id,
        email=user.email,
        role=user.role,
        created_at=user.created_at,
    )


# --- Response Models for Status ---


class AuthStatusResponse(BaseModel):
    """Response for the auth status check."""

    has_users: bool
    local_mode: bool = False


# --- Endpoints ---


@router.get("/status")
async def auth_status(
    store: Annotated[PolicyStore, Depends(get_store)],
) -> AuthStatusResponse:
    """Check whether any users exist in the system.

    Used by the frontend on initial load to decide whether to show
    the registration page (first-user flow) or the login page.

    Also returns local_mode flag so frontend can auto-authenticate
    when running in local development mode.

    This endpoint is public — no authentication required.
    """
    return AuthStatusResponse(
        has_users=store.count_users() > 0,
        local_mode=_is_local_mode(),
    )


@router.post("/login")
async def login(
    body: LoginRequest,
    store: Annotated[PolicyStore, Depends(get_store)],
) -> TokenResponse:
    """Authenticate with email and password.

    Returns a JWT token and user info on success.
    Returns 401 with a generic message on failure (no email enumeration).
    """
    # Generic message — same for wrong email and wrong password
    bad_credentials = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password",
        headers={"WWW-Authenticate": "Bearer"},
    )

    user = store.get_user_by_email(body.email)
    if user is None:
        raise bad_credentials

    if not verify_password(body.password, user.hashed_password):
        raise bad_credentials

    token = create_access_token(user.id, user.email, user.role)

    user_public = UserPublic(
        id=user.id,
        email=user.email,
        role=user.role,
        created_at=user.created_at,
    )

    return TokenResponse(token=token, user=_user_info(user_public))


@router.post("/register")
async def register(
    body: RegisterRequest,
    store: Annotated[PolicyStore, Depends(get_store)],
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_optional_bearer)
    ] = None,
) -> TokenResponse | UserCreatedResponse:
    """Register a new user.

    First-user flow: When no users exist, anyone can register and
    the first user becomes admin. Returns a JWT.

    Subsequent registrations: Requires admin JWT. Creates a regular
    user. Returns user info (no JWT — admin creates accounts for
    others who then log in separately).
    """
    is_first_user = store.count_users() == 0

    if not is_first_user:
        # After first user, require admin auth
        caller = _try_get_user_from_token(credentials, store)
        if caller is None or caller.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Registration is closed — only admins can create accounts",
            )

    # Validate inputs
    validate_email(body.email)
    if not is_first_user:
        # First-user (admin setup) can choose any password — they own the
        # instance and may be using env-var defaults.  Subsequent users
        # created by admins must meet the minimum-length requirement.
        validate_password(body.password)

    # Check for duplicate email
    if store.email_exists(body.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Hash the password before storing
    hashed = hash_password(body.password)

    # First user gets admin role
    role = "admin" if is_first_user else "user"

    try:
        user_id = store.create_user(body.email, hashed, role)
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

    if is_first_user:
        # First user: return JWT so they're immediately logged in
        token = create_access_token(user.id, user.email, user.role)
        return TokenResponse(token=token, user=_user_info(user_public))
    else:
        # Subsequent users: admin creates account, user logs in separately
        return UserCreatedResponse(user=_user_info(user_public))


@router.post("/refresh")
async def refresh_token(
    current_user: Annotated[UserPublic, Depends(get_current_user)],
) -> TokenResponse:
    """Refresh an existing JWT.

    Requires a valid (not expired) JWT. Returns a new JWT with a
    fresh expiry time.
    """
    token = create_access_token(current_user.id, current_user.email, current_user.role)
    return TokenResponse(token=token, user=_user_info(current_user))
