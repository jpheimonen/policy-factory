"""Auth store mixin for user management."""

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class User:
    """User record from the database."""

    id: str
    email: str
    hashed_password: str
    role: str
    created_at: datetime


@dataclass
class UserPublic:
    """User record without sensitive fields (for list responses)."""

    id: str
    email: str
    role: str
    created_at: datetime


class AuthStoreMixin:
    """Mixin providing user authentication storage methods.

    Expects the parent class to provide a `conn` attribute
    with an active sqlite3.Connection.

    Note: This mixin stores pre-hashed passwords. Password hashing
    is the responsibility of the auth service layer (step 005).
    The store never sees plaintext passwords.
    """

    # Type hint for the mixin — provided by BaseStore at runtime
    conn: sqlite3.Connection

    def create_user(self, email: str, hashed_password: str, role: str = "user") -> str:
        """Create a new user.

        Args:
            email: User's email address.
            hashed_password: Pre-hashed password (bcrypt hash from auth service).
            role: User role, either "admin" or "user". Defaults to "user".

        Returns:
            The generated UUID for the new user.

        Raises:
            sqlite3.IntegrityError: If a user with the same email already exists.
        """
        user_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "INSERT INTO users (id, email, hashed_password, role, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, email, hashed_password, role, now),
        )
        self.conn.commit()
        return user_id

    def get_user_by_email(self, email: str) -> User | None:
        """Look up a user by email (case-insensitive).

        Args:
            email: Email address to search for.

        Returns:
            A User dataclass with all fields (including hashed_password)
            if found, or None if not found.
        """
        row = self.conn.execute(
            "SELECT * FROM users WHERE LOWER(email) = LOWER(?)",
            (email,),
        ).fetchone()
        if not row:
            return None
        return self._row_to_user(row)

    def get_user_by_id(self, user_id: str) -> User | None:
        """Look up a user by UUID.

        Args:
            user_id: The user's UUID.

        Returns:
            A User dataclass with all fields if found, or None if not found.
        """
        row = self.conn.execute(
            "SELECT * FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if not row:
            return None
        return self._row_to_user(row)

    def list_users(self) -> list[UserPublic]:
        """List all users ordered by creation date.

        Returns:
            A list of UserPublic dataclasses (hashed passwords excluded).
        """
        rows = self.conn.execute(
            "SELECT id, email, role, created_at FROM users ORDER BY created_at",
        ).fetchall()
        return [self._row_to_user_public(row) for row in rows]

    def delete_user(self, user_id: str) -> None:
        """Delete a user by ID.

        This operation is idempotent — deleting a non-existent user
        does not raise an error.

        Args:
            user_id: The user's UUID to delete.
        """
        self.conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        self.conn.commit()

    def count_users(self) -> int:
        """Count the total number of users.

        Used by registration logic to determine if this is the
        first user (who gets admin role automatically).

        Returns:
            The total number of users in the database.
        """
        row = self.conn.execute("SELECT COUNT(*) as count FROM users").fetchone()
        return row["count"]

    def email_exists(self, email: str) -> bool:
        """Check whether an email is already registered (case-insensitive).

        A lightweight check used to reject duplicate registrations
        before attempting an insert.

        Args:
            email: Email address to check.

        Returns:
            True if the email is already registered, False otherwise.
        """
        row = self.conn.execute(
            "SELECT 1 FROM users WHERE LOWER(email) = LOWER(?) LIMIT 1",
            (email,),
        ).fetchone()
        return row is not None

    def _row_to_user(self, row: sqlite3.Row) -> User:
        """Convert a sqlite3.Row to a User dataclass."""
        return User(
            id=row["id"],
            email=row["email"],
            hashed_password=row["hashed_password"],
            role=row["role"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def _row_to_user_public(self, row: sqlite3.Row) -> UserPublic:
        """Convert a sqlite3.Row to a UserPublic dataclass (no password)."""
        return UserPublic(
            id=row["id"],
            email=row["email"],
            role=row["role"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
