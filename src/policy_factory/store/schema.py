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
    model TEXT,
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

CREATE TABLE IF NOT EXISTS critic_results (
    id TEXT PRIMARY KEY,
    cascade_id TEXT,
    layer_slug TEXT,
    idea_id TEXT,
    archetype TEXT NOT NULL,
    assessment_text TEXT NOT NULL DEFAULT '',
    structured_assessment TEXT,
    agent_run_id TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_critic_results_cascade_layer
    ON critic_results(cascade_id, layer_slug);
CREATE INDEX IF NOT EXISTS idx_critic_results_idea_id
    ON critic_results(idea_id);
CREATE INDEX IF NOT EXISTS idx_critic_results_created_at
    ON critic_results(created_at);

CREATE TABLE IF NOT EXISTS synthesis_results (
    id TEXT PRIMARY KEY,
    cascade_id TEXT,
    layer_slug TEXT,
    idea_id TEXT,
    synthesis_text TEXT NOT NULL DEFAULT '',
    structured_synthesis TEXT,
    agent_run_id TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_synthesis_results_cascade_layer
    ON synthesis_results(cascade_id, layer_slug);
CREATE INDEX IF NOT EXISTS idx_synthesis_results_idea_id
    ON synthesis_results(idea_id);
CREATE INDEX IF NOT EXISTS idx_synthesis_results_created_at
    ON synthesis_results(created_at);

CREATE TABLE IF NOT EXISTS feedback_memos (
    id TEXT PRIMARY KEY,
    source_layer TEXT NOT NULL,
    target_layer TEXT NOT NULL,
    cascade_id TEXT,
    content TEXT NOT NULL,
    referenced_items TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    resolved_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_feedback_memos_target_status
    ON feedback_memos(target_layer, status);
CREATE INDEX IF NOT EXISTS idx_feedback_memos_cascade_id
    ON feedback_memos(cascade_id);
CREATE INDEX IF NOT EXISTS idx_feedback_memos_created_at
    ON feedback_memos(created_at);

CREATE TABLE IF NOT EXISTS ideas (
    id TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    source TEXT NOT NULL,
    target_objective TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    submitted_by TEXT NOT NULL,
    submitted_at TEXT NOT NULL,
    evaluation_started_at TEXT,
    evaluation_completed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_ideas_status ON ideas(status);
CREATE INDEX IF NOT EXISTS idx_ideas_submitted_at ON ideas(submitted_at);

CREATE TABLE IF NOT EXISTS idea_scores (
    id TEXT PRIMARY KEY,
    idea_id TEXT NOT NULL,
    strategic_fit REAL NOT NULL,
    feasibility REAL NOT NULL,
    cost REAL NOT NULL,
    risk REAL NOT NULL,
    public_acceptance REAL NOT NULL,
    international_impact REAL NOT NULL,
    overall_score REAL NOT NULL,
    agent_run_id TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_idea_scores_idea_id ON idea_scores(idea_id);
CREATE INDEX IF NOT EXISTS idx_idea_scores_overall ON idea_scores(overall_score);

CREATE TABLE IF NOT EXISTS heartbeat_runs (
    id TEXT PRIMARY KEY,
    trigger TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    highest_tier INTEGER NOT NULL DEFAULT 0,
    structured_log TEXT NOT NULL DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_heartbeat_runs_started_at ON heartbeat_runs(started_at);

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    layer_slug TEXT NOT NULL,
    filename TEXT,
    created_at TEXT NOT NULL,
    last_active_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_conversations_layer_item ON conversations(layer_slug, filename);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    files_edited TEXT
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id);

CREATE TABLE IF NOT EXISTS pending_conversation_cascade (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    starting_layer TEXT NOT NULL,
    affected_layers TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
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
    # Use autocommit mode (isolation_level=None) so the connection does not
    # hold implicit transactions between explicit commit() calls.  This avoids
    # long-lived RESERVED locks that block external writers (e.g. E2E test
    # setup scripts that need to clear the database).
    conn.isolation_level = None
    conn.executescript(SCHEMA)
    conn.execute("PRAGMA journal_mode=WAL")

    # --- Migrations ---

    # Migration: allow NULL in agent_runs.model column.
    # SQLite cannot ALTER COLUMN to remove NOT NULL, so we check the schema
    # and recreate the table if needed.
    schema_row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='agent_runs'"
    ).fetchone()
    if schema_row and "model TEXT NOT NULL" in schema_row["sql"]:
        conn.executescript("""
            ALTER TABLE agent_runs RENAME TO _agent_runs_old;
            CREATE TABLE agent_runs (
                id TEXT PRIMARY KEY,
                cascade_id TEXT,
                agent_type TEXT NOT NULL,
                agent_label TEXT NOT NULL,
                model TEXT,
                target_layer TEXT,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                success INTEGER,
                error_message TEXT,
                cost_usd REAL,
                output_text TEXT
            );
            INSERT INTO agent_runs SELECT * FROM _agent_runs_old;
            DROP TABLE _agent_runs_old;
        """)

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
