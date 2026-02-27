"""SQLite-backed persistence for Policy Factory.

This module provides a unified PolicyStore class that combines functionality
from the base store and domain-specific mixins.
"""

from pathlib import Path

from .agent_run import AgentRun, AgentRunStoreMixin
from .auth import AuthStoreMixin, User, UserPublic
from .base import BaseStore
from .cascade import CascadeRun, CascadeStoreMixin, QueueEntry
from .events import EventStoreMixin, StoredEvent
from .schema import get_default_db_path, init_db


class PolicyStore(
    BaseStore,
    AuthStoreMixin,
    EventStoreMixin,
    CascadeStoreMixin,
    AgentRunStoreMixin,
):
    """SQLite-backed store for Policy Factory.

    This class combines:
    - BaseStore: Database connection initialization
    - AuthStoreMixin: User authentication storage
    - EventStoreMixin: Event persistence and retrieval
    - CascadeStoreMixin: Cascade run tracking, lock, and queue
    - AgentRunStoreMixin: Agent invocation history

    Additional mixins will be added in later steps as new
    feature domains are built (ideas, heartbeat, feedback memos, etc.).

    This is the only store class that consumers import and instantiate.
    """

    def __init__(self, db_path: Path) -> None:
        """Initialize the store with the given database path."""
        super().__init__(db_path)


__all__ = [
    "AgentRun",
    "CascadeRun",
    "PolicyStore",
    "QueueEntry",
    "StoredEvent",
    "User",
    "UserPublic",
    "get_default_db_path",
    "init_db",
]
