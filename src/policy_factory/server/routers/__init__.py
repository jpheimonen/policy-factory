"""Policy Factory API routers."""

from policy_factory.server.routers.activity import router as activity_router
from policy_factory.server.routers.auth import router as auth_router
from policy_factory.server.routers.health import router as health_router
from policy_factory.server.routers.history import router as history_router
from policy_factory.server.routers.layers import router as layers_router
from policy_factory.server.routers.users import router as users_router

__all__ = [
    "activity_router",
    "auth_router",
    "health_router",
    "history_router",
    "layers_router",
    "users_router",
]
