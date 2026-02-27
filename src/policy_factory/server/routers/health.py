"""Health check routes."""

import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("/check")
async def health_check() -> dict:
    """Basic health check endpoint.

    Returns application name and status.
    """
    return {
        "application": "policy-factory",
        "status": "ok",
    }
