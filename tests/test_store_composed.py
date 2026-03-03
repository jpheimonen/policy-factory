"""Tests for the composed PolicyStore and dependency integration."""

from pathlib import Path

import pytest

from policy_factory.store import PolicyStore
from policy_factory.store.auth import User, UserPublic
from policy_factory.store.base import BaseStore


class TestPolicyStoreComposition:
    """Tests for the composed PolicyStore class."""

    def test_instantiation(self, tmp_db_path: Path) -> None:
        """PolicyStore can be instantiated with a database path."""
        store = PolicyStore(tmp_db_path)
        assert store is not None
        assert hasattr(store, "conn")

    def test_inherits_from_base_store(self, store: PolicyStore) -> None:
        """PolicyStore inherits from BaseStore."""
        assert isinstance(store, BaseStore)

    def test_has_auth_methods(self, store: PolicyStore) -> None:
        """PolicyStore has all auth mixin methods."""
        assert hasattr(store, "create_user")
        assert hasattr(store, "get_user_by_email")
        assert hasattr(store, "get_user_by_id")
        assert hasattr(store, "list_users")
        assert hasattr(store, "delete_user")
        assert hasattr(store, "count_users")
        assert hasattr(store, "email_exists")

    def test_auth_methods_work(self, store: PolicyStore) -> None:
        """Auth mixin methods work through the composed store."""
        # Create
        user_id = store.create_user("test@example.com", "hash", "admin")
        assert user_id is not None

        # Get by email
        user = store.get_user_by_email("test@example.com")
        assert user is not None
        assert isinstance(user, User)

        # Get by ID
        user = store.get_user_by_id(user_id)
        assert user is not None

        # List
        users = store.list_users()
        assert len(users) == 1
        assert isinstance(users[0], UserPublic)

        # Count
        assert store.count_users() == 1

        # Email exists
        assert store.email_exists("test@example.com") is True

        # Delete
        store.delete_user(user_id)
        assert store.count_users() == 0


class TestDependencyIntegration:
    """Tests for the store dependency injection integration."""

    def test_get_store_before_init_raises(self) -> None:
        """get_store raises RuntimeError before initialization."""
        from policy_factory.server import deps

        # Reset state
        deps._store = None
        with pytest.raises(RuntimeError, match="Store not initialized"):
            deps.get_store()

    def test_init_deps_and_get_store(self, store: PolicyStore) -> None:
        """After init_deps, get_store returns the store."""
        from policy_factory.server import deps

        deps.init_deps(store=store)
        retrieved = deps.get_store()
        assert retrieved is store

        # Cleanup
        deps._store = None

    def test_get_store_returns_policy_store_type(self, store: PolicyStore) -> None:
        """get_store returns a PolicyStore instance."""
        from policy_factory.server import deps

        deps.init_deps(store=store)
        retrieved = deps.get_store()
        assert isinstance(retrieved, PolicyStore)

        # Cleanup
        deps._store = None


class TestModuleExports:
    """Tests for module-level exports."""

    def test_policy_store_exported(self) -> None:
        """PolicyStore is importable from policy_factory.store."""
        from policy_factory.store import PolicyStore

        assert PolicyStore is not None

    def test_user_exported(self) -> None:
        """User is importable from policy_factory.store."""
        from policy_factory.store import User

        assert User is not None

    def test_user_public_exported(self) -> None:
        """UserPublic is importable from policy_factory.store."""
        from policy_factory.store import UserPublic

        assert UserPublic is not None

    def test_init_db_exported(self) -> None:
        """init_db is importable from policy_factory.store."""
        from policy_factory.store import init_db

        assert init_db is not None

    def test_get_default_db_path_exported(self) -> None:
        """get_default_db_path is importable from policy_factory.store."""
        from policy_factory.store import get_default_db_path

        assert get_default_db_path is not None
