"""Tests for the AuthStoreMixin."""

import sqlite3
from datetime import datetime, timezone

import pytest

from policy_factory.store import PolicyStore
from policy_factory.store.auth import User, UserPublic


class TestCreateUser:
    """Tests for create_user method."""

    def test_creates_user_and_returns_id(self, store: PolicyStore) -> None:
        """Creating a user returns a UUID string."""
        user_id = store.create_user("test@example.com", "hashed_pw_123", "user")
        assert isinstance(user_id, str)
        assert len(user_id) == 36  # UUID format

    def test_stores_user_record(self, store: PolicyStore) -> None:
        """Created user can be retrieved from the database."""
        user_id = store.create_user("test@example.com", "hashed_pw_123", "user")
        user = store.get_user_by_id(user_id)
        assert user is not None
        assert user.email == "test@example.com"
        assert user.hashed_password == "hashed_pw_123"
        assert user.role == "user"

    def test_stores_admin_role(self, store: PolicyStore) -> None:
        """User can be created with admin role."""
        user_id = store.create_user("admin@example.com", "hashed_pw", "admin")
        user = store.get_user_by_id(user_id)
        assert user is not None
        assert user.role == "admin"

    def test_stores_created_at_timestamp(self, store: PolicyStore) -> None:
        """Created user has a valid ISO 8601 created_at timestamp."""
        user_id = store.create_user("test@example.com", "hashed_pw", "user")
        user = store.get_user_by_id(user_id)
        assert user is not None
        assert isinstance(user.created_at, datetime)
        # Should be recent (within last minute)
        now = datetime.now(timezone.utc)
        diff = (now - user.created_at.replace(tzinfo=timezone.utc)).total_seconds()
        assert diff < 60

    def test_duplicate_email_raises_error(self, store: PolicyStore) -> None:
        """Creating a user with a duplicate email raises IntegrityError."""
        store.create_user("test@example.com", "hash1", "user")
        with pytest.raises(sqlite3.IntegrityError):
            store.create_user("test@example.com", "hash2", "user")

    def test_unique_ids_generated(self, store: PolicyStore) -> None:
        """Each user gets a unique ID."""
        id1 = store.create_user("user1@example.com", "hash1", "user")
        id2 = store.create_user("user2@example.com", "hash2", "user")
        assert id1 != id2

    def test_default_role_is_user(self, store: PolicyStore) -> None:
        """Default role when not specified is 'user'."""
        user_id = store.create_user("test@example.com", "hash")
        user = store.get_user_by_id(user_id)
        assert user is not None
        assert user.role == "user"


class TestGetUserByEmail:
    """Tests for get_user_by_email method."""

    def test_returns_user_when_found(self, store: PolicyStore) -> None:
        """Returns a User when the email exists."""
        store.create_user("test@example.com", "hashed_pw", "user")
        user = store.get_user_by_email("test@example.com")
        assert user is not None
        assert isinstance(user, User)
        assert user.email == "test@example.com"

    def test_returns_none_when_not_found(self, store: PolicyStore) -> None:
        """Returns None when no user with that email exists."""
        user = store.get_user_by_email("nonexistent@example.com")
        assert user is None

    def test_case_insensitive_lookup(self, store: PolicyStore) -> None:
        """Email lookup is case-insensitive."""
        store.create_user("Test@Example.com", "hashed_pw", "user")

        user = store.get_user_by_email("test@example.com")
        assert user is not None
        assert user.email == "Test@Example.com"

        user = store.get_user_by_email("TEST@EXAMPLE.COM")
        assert user is not None

    def test_includes_hashed_password(self, store: PolicyStore) -> None:
        """Returned user includes hashed_password (needed for login verification)."""
        store.create_user("test@example.com", "hashed_pw_secret", "user")
        user = store.get_user_by_email("test@example.com")
        assert user is not None
        assert user.hashed_password == "hashed_pw_secret"

    def test_returns_all_fields(self, store: PolicyStore) -> None:
        """Returned user has all fields populated."""
        store.create_user("test@example.com", "hashed_pw", "admin")
        user = store.get_user_by_email("test@example.com")
        assert user is not None
        assert user.id is not None
        assert user.email == "test@example.com"
        assert user.hashed_password == "hashed_pw"
        assert user.role == "admin"
        assert isinstance(user.created_at, datetime)


class TestGetUserById:
    """Tests for get_user_by_id method."""

    def test_returns_user_when_found(self, store: PolicyStore) -> None:
        """Returns a User when the ID exists."""
        user_id = store.create_user("test@example.com", "hashed_pw", "user")
        user = store.get_user_by_id(user_id)
        assert user is not None
        assert isinstance(user, User)
        assert user.id == user_id

    def test_returns_none_when_not_found(self, store: PolicyStore) -> None:
        """Returns None when no user with that ID exists."""
        user = store.get_user_by_id("nonexistent-uuid")
        assert user is None

    def test_returns_all_fields(self, store: PolicyStore) -> None:
        """Returned user has all fields populated."""
        user_id = store.create_user("test@example.com", "hashed_pw", "admin")
        user = store.get_user_by_id(user_id)
        assert user is not None
        assert user.email == "test@example.com"
        assert user.hashed_password == "hashed_pw"
        assert user.role == "admin"
        assert isinstance(user.created_at, datetime)


class TestListUsers:
    """Tests for list_users method."""

    def test_empty_database(self, store: PolicyStore) -> None:
        """Returns empty list when no users exist."""
        users = store.list_users()
        assert users == []

    def test_returns_all_users(self, store: PolicyStore) -> None:
        """Returns all users in the database."""
        store.create_user("user1@example.com", "hash1", "admin")
        store.create_user("user2@example.com", "hash2", "user")
        store.create_user("user3@example.com", "hash3", "user")

        users = store.list_users()
        assert len(users) == 3

    def test_ordered_by_created_at(self, store: PolicyStore) -> None:
        """Users are ordered by creation date."""
        store.create_user("first@example.com", "hash1", "user")
        store.create_user("second@example.com", "hash2", "user")
        store.create_user("third@example.com", "hash3", "user")

        users = store.list_users()
        emails = [u.email for u in users]
        assert emails == ["first@example.com", "second@example.com", "third@example.com"]

    def test_excludes_hashed_password(self, store: PolicyStore) -> None:
        """List results use UserPublic which excludes hashed_password."""
        store.create_user("test@example.com", "secret_hash", "user")
        users = store.list_users()
        assert len(users) == 1
        assert isinstance(users[0], UserPublic)
        assert not hasattr(users[0], "hashed_password")

    def test_includes_public_fields(self, store: PolicyStore) -> None:
        """List results include id, email, role, and created_at."""
        store.create_user("test@example.com", "hash", "admin")
        users = store.list_users()
        user = users[0]
        assert user.id is not None
        assert user.email == "test@example.com"
        assert user.role == "admin"
        assert isinstance(user.created_at, datetime)


class TestDeleteUser:
    """Tests for delete_user method."""

    def test_deletes_existing_user(self, store: PolicyStore) -> None:
        """Deleting an existing user removes them from the database."""
        user_id = store.create_user("test@example.com", "hash", "user")
        store.delete_user(user_id)
        user = store.get_user_by_id(user_id)
        assert user is None

    def test_idempotent_delete(self, store: PolicyStore) -> None:
        """Deleting a non-existent user does not raise an error."""
        # Should not raise any exceptions
        store.delete_user("nonexistent-uuid")

    def test_deleting_user_removes_from_list(self, store: PolicyStore) -> None:
        """Deleted user no longer appears in list_users."""
        id1 = store.create_user("user1@example.com", "hash1", "user")
        store.create_user("user2@example.com", "hash2", "user")

        store.delete_user(id1)
        users = store.list_users()
        assert len(users) == 1
        assert users[0].email == "user2@example.com"

    def test_deleting_user_frees_email(self, store: PolicyStore) -> None:
        """After deleting a user, their email can be reused."""
        user_id = store.create_user("test@example.com", "hash1", "user")
        store.delete_user(user_id)

        # Should not raise IntegrityError
        new_id = store.create_user("test@example.com", "hash2", "user")
        assert new_id != user_id


class TestCountUsers:
    """Tests for count_users method."""

    def test_zero_on_fresh_database(self, store: PolicyStore) -> None:
        """Returns 0 when no users exist."""
        assert store.count_users() == 0

    def test_counts_correctly(self, store: PolicyStore) -> None:
        """Returns the correct count after adding users."""
        store.create_user("user1@example.com", "hash1", "user")
        assert store.count_users() == 1

        store.create_user("user2@example.com", "hash2", "user")
        assert store.count_users() == 2

    def test_decrements_after_delete(self, store: PolicyStore) -> None:
        """Count decreases after deleting a user."""
        id1 = store.create_user("user1@example.com", "hash1", "user")
        store.create_user("user2@example.com", "hash2", "user")
        assert store.count_users() == 2

        store.delete_user(id1)
        assert store.count_users() == 1


class TestEmailExists:
    """Tests for email_exists method."""

    def test_returns_false_when_not_exists(self, store: PolicyStore) -> None:
        """Returns False when email is not registered."""
        assert store.email_exists("nonexistent@example.com") is False

    def test_returns_true_when_exists(self, store: PolicyStore) -> None:
        """Returns True when email is registered."""
        store.create_user("test@example.com", "hash", "user")
        assert store.email_exists("test@example.com") is True

    def test_case_insensitive(self, store: PolicyStore) -> None:
        """Check is case-insensitive."""
        store.create_user("Test@Example.com", "hash", "user")
        assert store.email_exists("test@example.com") is True
        assert store.email_exists("TEST@EXAMPLE.COM") is True

    def test_returns_false_after_delete(self, store: PolicyStore) -> None:
        """Returns False after user is deleted."""
        user_id = store.create_user("test@example.com", "hash", "user")
        store.delete_user(user_id)
        assert store.email_exists("test@example.com") is False


class TestTimestampHandling:
    """Tests for ISO 8601 timestamp handling."""

    def test_timestamps_stored_as_iso8601(self, store: PolicyStore) -> None:
        """Timestamps are stored in ISO 8601 format."""
        user_id = store.create_user("test@example.com", "hash", "user")

        # Read raw from database
        row = store.conn.execute(
            "SELECT created_at FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        raw_timestamp = row["created_at"]

        # Should be parseable as ISO 8601
        parsed = datetime.fromisoformat(raw_timestamp)
        assert isinstance(parsed, datetime)

    def test_timestamps_parsed_correctly_on_read(self, store: PolicyStore) -> None:
        """Timestamps are parsed to datetime objects when reading."""
        user_id = store.create_user("test@example.com", "hash", "user")
        user = store.get_user_by_id(user_id)
        assert user is not None
        assert isinstance(user.created_at, datetime)
