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

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    data TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    layer_slug TEXT,
    category TEXT
);

CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
CREATE INDEX IF NOT EXISTS idx_events_event_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_layer_slug ON events(layer_slug);
CREATE INDEX IF NOT EXISTS idx_events_category ON events(category);

CREATE TABLE IF NOT EXISTS cascade_runs (
    id TEXT PRIMARY KEY,
    trigger_source TEXT NOT NULL,
    starting_layer TEXT NOT NULL,
    current_layer TEXT NOT NULL,
    current_step TEXT NOT NULL DEFAULT 'generation',
    status TEXT NOT NULL DEFAULT 'running',
    error_message TEXT,
    error_layer TEXT,
    context TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_cascade_runs_status ON cascade_runs(status);
CREATE INDEX IF NOT EXISTS idx_cascade_runs_created_at ON cascade_runs(created_at);

CREATE TABLE IF NOT EXISTS cascade_queue (
    id TEXT PRIMARY KEY,
    trigger_source TEXT NOT NULL,
    starting_layer TEXT NOT NULL,
    context TEXT,
    queued_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cascade_queue_queued_at ON cascade_queue(queued_at);

CREATE TABLE IF NOT EXISTS agent_runs (
    id TEXT PRIMARY KEY,
    cascade_id TEXT,
    agent_type TEXT NOT NULL,
    agent_label TEXT NOT NULL,
    model TEXT NOT NULL,
    target_layer TEXT,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    success INTEGER,
    error_message TEXT,
    cost_usd REAL,
    output_text TEXT
);

CREATE INDEX IF NOT EXISTS idx_agent_runs_cascade_id ON agent_runs(cascade_id);
CREATE INDEX IF NOT EXISTS idx_agent_runs_agent_type ON agent_runs(agent_type);
CREATE INDEX IF NOT EXISTS idx_agent_runs_target_layer ON agent_runs(target_layer);
CREATE INDEX IF NOT EXISTS idx_agent_runs_started_at ON agent_runs(started_at);
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
