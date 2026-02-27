"""SQLite-backed persistence for Policy Factory.

This module provides a unified PolicyStore class that combines functionality
from the base store and domain-specific mixins.
"""

from pathlib import Path

from .auth import AuthStoreMixin, User, UserPublic
from .base import BaseStore
from .schema import get_default_db_path, init_db


class PolicyStore(BaseStore, AuthStoreMixin):
    """SQLite-backed store for Policy Factory.

    This class combines:
    - BaseStore: Database connection initialization
    - AuthStoreMixin: User authentication storage

    Additional mixins will be added in later steps as new
    feature domains are built (ideas, cascade, heartbeat, etc.).

    This is the only store class that consumers import and instantiate.
    """

    def __init__(self, db_path: Path) -> None:
        """Initialize the store with the given database path."""
        super().__init__(db_path)


__all__ = [
    "PolicyStore",
    "User",
    "UserPublic",
    "get_default_db_path",
    "init_db",
]
