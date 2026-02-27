"""SQLite database schema and initialization for Policy Factory."""

import os
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    hashed_password TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',
    created_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email);
"""


def init_db(db_path: Path) -> sqlite3.Connection:
    """Initialize database with schema.

    Opens a SQLite connection, sets row_factory for dict-like access,
    executes the schema, enables WAL mode, and runs any migrations.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        An initialized sqlite3.Connection.
    """
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.execute("PRAGMA journal_mode=WAL")

    # Future migrations go here, following the cc-runner pattern:
    # try:
    #     conn.execute("SELECT new_column FROM table LIMIT 1")
    # except sqlite3.OperationalError:
    #     conn.execute("ALTER TABLE table ADD COLUMN new_column TEXT")
    #     conn.commit()

    return conn


def get_default_db_path() -> Path:
    """Get the default database path.

    The path is determined by:
    1. The POLICY_FACTORY_DB_PATH environment variable (if set)
    2. ~/.policy-factory/store.db (default)

    Creates the parent directory if it doesn't exist.

    Returns:
        Path to the SQLite database file.
    """
    env_path = os.environ.get("POLICY_FACTORY_DB_PATH")
    if env_path:
        db_path = Path(env_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return db_path

    data_dir = Path.home() / ".policy-factory"
    data_dir.mkdir(exist_ok=True)
    return data_dir / "store.db"
