"""Conversation store mixin for managing policy conversations.

Provides CRUD operations for conversations and messages. Each conversation
belongs to either a specific item (layer_slug + filename) or to a layer
as a whole (layer_slug only with filename=None).
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class Conversation:
    """A conversation record from the database."""

    id: str
    layer_slug: str
    filename: str | None
    created_at: datetime
    last_active_at: datetime


@dataclass
class Message:
    """A message record from the database."""

    id: str
    conversation_id: str
    role: str  # "user" or "assistant"
    content: str
    created_at: datetime
    files_edited: list[str] | None


class ConversationStoreMixin:
    """Mixin providing conversation and message CRUD operations.

    Requires ``self.conn`` (a ``sqlite3.Connection``) to be set by the
    base store class.
    """

    conn: sqlite3.Connection  # Provided by BaseStore

    # ------------------------------------------------------------------
    # Conversation CRUD
    # ------------------------------------------------------------------

    def create_conversation(
        self,
        layer_slug: str,
        filename: str | None = None,
    ) -> str:
        """Create a conversation for an item or layer.

        Args:
            layer_slug: Which layer this conversation is about.
            filename: Which item within the layer, or None for layer-level
                conversations.

        Returns:
            The generated conversation ID.
        """
        conversation_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "INSERT INTO conversations "
            "(id, layer_slug, filename, created_at, last_active_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (conversation_id, layer_slug, filename, now, now),
        )
        self.conn.commit()
        return conversation_id

    def get_conversation(self, conversation_id: str) -> Conversation | None:
        """Retrieve a conversation by ID.

        Args:
            conversation_id: The conversation ID.

        Returns:
            A Conversation dataclass, or None if not found.
        """
        row = self.conn.execute(
            "SELECT * FROM conversations WHERE id = ?",
            (conversation_id,),
        ).fetchone()
        if not row:
            return None
        return self._row_to_conversation(row)

    def list_conversations_for_item(
        self,
        layer_slug: str,
        filename: str,
    ) -> list[Conversation]:
        """Return conversations matching layer_slug and filename.

        Args:
            layer_slug: The layer slug to filter by.
            filename: The filename to filter by.

        Returns:
            List of Conversation records ordered by last_active_at descending.
        """
        rows = self.conn.execute(
            "SELECT * FROM conversations "
            "WHERE layer_slug = ? AND filename = ? "
            "ORDER BY last_active_at DESC",
            (layer_slug, filename),
        ).fetchall()
        return [self._row_to_conversation(r) for r in rows]

    def list_conversations_for_layer(
        self,
        layer_slug: str,
    ) -> list[Conversation]:
        """Return conversations for a layer where filename is NULL.

        Args:
            layer_slug: The layer slug to filter by.

        Returns:
            List of Conversation records ordered by last_active_at descending.
        """
        rows = self.conn.execute(
            "SELECT * FROM conversations "
            "WHERE layer_slug = ? AND filename IS NULL "
            "ORDER BY last_active_at DESC",
            (layer_slug,),
        ).fetchall()
        return [self._row_to_conversation(r) for r in rows]

    def delete_conversation(self, conversation_id: str) -> bool:
        """Remove a conversation and all its messages.

        Args:
            conversation_id: The conversation ID to delete.

        Returns:
            True if the conversation was found and deleted, False otherwise.
        """
        # First delete all associated messages
        self.conn.execute(
            "DELETE FROM messages WHERE conversation_id = ?",
            (conversation_id,),
        )
        # Then delete the conversation
        cursor = self.conn.execute(
            "DELETE FROM conversations WHERE id = ?",
            (conversation_id,),
        )
        self.conn.commit()
        return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # Message CRUD
    # ------------------------------------------------------------------

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        files_edited: list[str] | None = None,
    ) -> str:
        """Create a message in a conversation and update last_active_at.

        Args:
            conversation_id: The conversation this message belongs to.
            role: Either "user" or "assistant".
            content: The message text.
            files_edited: Optional list of file paths edited (for assistant
                messages).

        Returns:
            The generated message ID.
        """
        message_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        # Serialize files_edited to JSON if provided
        files_edited_json = json.dumps(files_edited) if files_edited else None

        self.conn.execute(
            "INSERT INTO messages "
            "(id, conversation_id, role, content, created_at, files_edited) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (message_id, conversation_id, role, content, now, files_edited_json),
        )

        # Update conversation's last_active_at
        self.conn.execute(
            "UPDATE conversations SET last_active_at = ? WHERE id = ?",
            (now, conversation_id),
        )

        self.conn.commit()
        return message_id

    def get_messages(self, conversation_id: str) -> list[Message]:
        """Retrieve all messages for a conversation in chronological order.

        Args:
            conversation_id: The conversation ID.

        Returns:
            List of Message records ordered by created_at ascending.
        """
        rows = self.conn.execute(
            "SELECT * FROM messages "
            "WHERE conversation_id = ? "
            "ORDER BY created_at ASC",
            (conversation_id,),
        ).fetchall()
        return [self._row_to_message(r) for r in rows]

    # ------------------------------------------------------------------
    # Row conversion helpers
    # ------------------------------------------------------------------

    def _row_to_conversation(self, row: sqlite3.Row) -> Conversation:
        """Convert a database row to a Conversation dataclass."""
        return Conversation(
            id=row["id"],
            layer_slug=row["layer_slug"],
            filename=row["filename"],
            created_at=datetime.fromisoformat(row["created_at"]),
            last_active_at=datetime.fromisoformat(row["last_active_at"]),
        )

    def _row_to_message(self, row: sqlite3.Row) -> Message:
        """Convert a database row to a Message dataclass."""
        files_edited = None
        if row["files_edited"]:
            files_edited = json.loads(row["files_edited"])

        return Message(
            id=row["id"],
            conversation_id=row["conversation_id"],
            role=row["role"],
            content=row["content"],
            created_at=datetime.fromisoformat(row["created_at"]),
            files_edited=files_edited,
        )
