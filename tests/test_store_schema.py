"""Tests for SQLite store schema and initialization."""

import os
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from policy_factory.store.schema import get_default_db_path, init_db


class TestInitDb:
    """Tests for init_db function."""

    def test_creates_database_file(self, tmp_path: Path) -> None:
        """Database file is created on init."""
        db_path = tmp_path / "test.db"
        assert not db_path.exists()
        init_db(db_path)
        assert db_path.exists()

    def test_returns_connection(self, tmp_path: Path) -> None:
        """init_db returns a sqlite3 Connection."""
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)
        assert isinstance(conn, sqlite3.Connection)

    def test_row_factory_set(self, tmp_path: Path) -> None:
        """Connection has row_factory set to sqlite3.Row."""
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)
        assert conn.row_factory == sqlite3.Row

    def test_wal_mode_enabled(self, tmp_path: Path) -> None:
        """Database uses WAL journal mode."""
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)
        result = conn.execute("PRAGMA journal_mode").fetchone()
        assert result[0] == "wal"

    def test_users_table_created(self, tmp_path: Path) -> None:
        """Users table is created with the correct columns."""
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        # Verify table exists by querying it
        cursor = conn.execute("PRAGMA table_info(users)")
        columns = {row["name"]: row["type"] for row in cursor.fetchall()}

        assert "id" in columns
        assert "email" in columns
        assert "hashed_password" in columns
        assert "role" in columns
        assert "created_at" in columns

    def test_users_table_id_is_primary_key(self, tmp_path: Path) -> None:
        """The id column is the primary key."""
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        cursor = conn.execute("PRAGMA table_info(users)")
        for row in cursor.fetchall():
            if row["name"] == "id":
                assert row["pk"] == 1
                break
        else:
            pytest.fail("id column not found in users table")

    def test_email_unique_constraint(self, tmp_path: Path) -> None:
        """Email column has a unique constraint."""
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        # Insert first user
        conn.execute(
            "INSERT INTO users (id, email, hashed_password, role, created_at) "
            "VALUES ('id1', 'test@example.com', 'hash', 'user', '2024-01-01T00:00:00+00:00')"
        )
        conn.commit()

        # Attempt duplicate email should fail
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO users (id, email, hashed_password, role, created_at) "
                "VALUES ('id2', 'test@example.com', 'hash', 'user', '2024-01-01T00:00:00+00:00')"
            )

    def test_role_default_value(self, tmp_path: Path) -> None:
        """Role column defaults to 'user'."""
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        conn.execute(
            "INSERT INTO users (id, email, hashed_password, created_at) "
            "VALUES ('id1', 'test@example.com', 'hash', '2024-01-01T00:00:00+00:00')"
        )
        conn.commit()

        row = conn.execute("SELECT role FROM users WHERE id = 'id1'").fetchone()
        assert row["role"] == "user"

    def test_idempotent_schema_initialization(self, tmp_path: Path) -> None:
        """Running init_db twice does not error or duplicate tables."""
        db_path = tmp_path / "test.db"

        # Initialize twice
        conn1 = init_db(db_path)
        conn1.close()
        conn2 = init_db(db_path)

        # Verify table still works
        cursor = conn2.execute("PRAGMA table_info(users)")
        columns = [row["name"] for row in cursor.fetchall()]
        assert "id" in columns
        assert "email" in columns

    def test_idempotent_with_existing_data(self, tmp_path: Path) -> None:
        """Running init_db on a database with existing data preserves the data."""
        db_path = tmp_path / "test.db"

        # First init and insert data
        conn1 = init_db(db_path)
        conn1.execute(
            "INSERT INTO users (id, email, hashed_password, role, created_at) "
            "VALUES ('id1', 'test@example.com', 'hash', 'admin', '2024-01-01T00:00:00+00:00')"
        )
        conn1.commit()
        conn1.close()

        # Second init should preserve data
        conn2 = init_db(db_path)
        row = conn2.execute("SELECT * FROM users WHERE id = 'id1'").fetchone()
        assert row is not None
        assert row["email"] == "test@example.com"
        assert row["role"] == "admin"

    def test_email_index_exists(self, tmp_path: Path) -> None:
        """A unique index exists on the email column."""
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        indexes = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='users'"
        ).fetchall()
        index_names = [row["name"] for row in indexes]
        assert "idx_users_email" in index_names


class TestGetDefaultDbPath:
    """Tests for get_default_db_path function."""

    def test_default_path(self, tmp_path: Path) -> None:
        """Default path is ~/.policy-factory/store.db."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove POLICY_FACTORY_DB_PATH if set
            os.environ.pop("POLICY_FACTORY_DB_PATH", None)
            with patch("pathlib.Path.home", return_value=tmp_path):
                path = get_default_db_path()
                assert path == tmp_path / ".policy-factory" / "store.db"

    def test_creates_parent_directory(self, tmp_path: Path) -> None:
        """Creates ~/.policy-factory/ if it doesn't exist."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("POLICY_FACTORY_DB_PATH", None)
            with patch("pathlib.Path.home", return_value=tmp_path):
                path = get_default_db_path()
                assert path.parent.exists()

    def test_env_var_override(self, tmp_path: Path) -> None:
        """POLICY_FACTORY_DB_PATH environment variable overrides default."""
        custom_path = tmp_path / "custom" / "my.db"
        with patch.dict(os.environ, {"POLICY_FACTORY_DB_PATH": str(custom_path)}):
            path = get_default_db_path()
            assert path == custom_path

    def test_env_var_creates_parent_directory(self, tmp_path: Path) -> None:
        """Environment variable path creates parent directory."""
        custom_path = tmp_path / "nested" / "dir" / "my.db"
        with patch.dict(os.environ, {"POLICY_FACTORY_DB_PATH": str(custom_path)}):
            path = get_default_db_path()
            assert path.parent.exists()
