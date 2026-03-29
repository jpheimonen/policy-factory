"""SQLite-backed persistence for Policy Factory.

This module provides a unified PolicyStore class that combines functionality
from the base store and domain-specific mixins.
"""

from pathlib import Path

from .agent_run import AgentRun, AgentRunStoreMixin
from .auth import AuthStoreMixin, User, UserPublic
from .base import BaseStore
from .cascade import CascadeRun, CascadeStoreMixin, PendingCascadeEntry, QueueEntry
from .conversation import Conversation, ConversationStoreMixin, Message
from .critic_result import CriticResult, CriticResultMixin, SynthesisResult
from .events import EventStoreMixin, StoredEvent
from .feedback_memo import FeedbackMemo, FeedbackMemoMixin
from .heartbeat import HeartbeatMixin, HeartbeatRun, TierEntry
from .idea import Idea, IdeaStoreMixin
from .schema import get_default_db_path, init_db
from .score import IdeaScore, ScoreStoreMixin


class PolicyStore(
    BaseStore,
    AuthStoreMixin,
    EventStoreMixin,
    CascadeStoreMixin,
    AgentRunStoreMixin,
    ConversationStoreMixin,
    CriticResultMixin,
    FeedbackMemoMixin,
    IdeaStoreMixin,
    ScoreStoreMixin,
    HeartbeatMixin,
):
    """SQLite-backed store for Policy Factory.

    This class combines:
    - BaseStore: Database connection initialization
    - AuthStoreMixin: User authentication storage
    - EventStoreMixin: Event persistence and retrieval
    - CascadeStoreMixin: Cascade run tracking, lock, and queue
    - AgentRunStoreMixin: Agent invocation history
    - ConversationStoreMixin: Conversation and message storage
    - CriticResultMixin: Critic and synthesis result storage
    - FeedbackMemoMixin: Bidirectional feedback between layers
    - IdeaStoreMixin: Idea submission and lifecycle management
    - ScoreStoreMixin: 6-axis idea evaluation scores
    - HeartbeatMixin: Heartbeat run tracking and history

    This is the only store class that consumers import and instantiate.
    """

    def __init__(self, db_path: Path) -> None:
        """Initialize the store with the given database path."""
        super().__init__(db_path)


__all__ = [
    "AgentRun",
    "CascadeRun",
    "Conversation",
    "CriticResult",
    "FeedbackMemo",
    "HeartbeatRun",
    "Idea",
    "IdeaScore",
    "Message",
    "PendingCascadeEntry",
    "PolicyStore",
    "QueueEntry",
    "StoredEvent",
    "SynthesisResult",
    "TierEntry",
    "User",
    "UserPublic",
    "get_default_db_path",
    "init_db",
]
