"""Shared input validation helpers for API routers.

Centralises email and password validation rules used by both the
auth and users routers.
"""

from __future__ import annotations

import re

from fastapi import HTTPException

# Minimum password length
MIN_PASSWORD_LENGTH = 8


def validate_email(email: str) -> None:
    """Validate an email address format.

    Raises:
        HTTPException 422: If the email is empty or malformed.
    """
    if not email or not email.strip():
        raise HTTPException(
            status_code=422,
            detail="Email is required",
        )
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email.strip()):
        raise HTTPException(
            status_code=422,
            detail="Invalid email format",
        )


def validate_password(password: str) -> None:
    """Validate a password meets minimum requirements.

    Raises:
        HTTPException 422: If the password is empty or too short.
    """
    if not password:
        raise HTTPException(
            status_code=422,
            detail="Password is required",
        )
    if len(password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=422,
            detail=f"Password must be at least {MIN_PASSWORD_LENGTH} characters",
        )
