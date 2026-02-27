"""Data directory initialization — first-run setup.

Called during FastAPI lifespan startup. Creates the data directory,
initializes the git repo, creates layer subdirectories, writes
pre-seeded values, and makes the initial commit.

Idempotent: if the data directory and git repo already exist, does nothing.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from .git import commit_changes, init_data_repo, is_git_repo
from .layers import LAYERS, write_narrative
from .markdown import write_markdown
from .seed_values import SEED_VALUES

logger = logging.getLogger(__name__)

# Default data directory (relative to cwd)
_DEFAULT_DATA_DIR = "data"


def get_data_dir() -> Path:
    """Return the configured data directory path.

    Uses the ``POLICY_FACTORY_DATA_DIR`` environment variable if set,
    otherwise defaults to ``data/`` relative to the current working directory.
    """
    env_path = os.environ.get("POLICY_FACTORY_DATA_DIR")
    if env_path:
        return Path(env_path)
    return Path.cwd() / _DEFAULT_DATA_DIR


def initialize_data_directory(data_root: Path | None = None) -> None:
    """Initialize the data directory with git repo, layer dirs, and seed files.

    This function is idempotent: if the data directory already contains a
    git repository, it does nothing.

    Args:
        data_root: Path to the data directory. If None, uses ``get_data_dir()``.

    Raises:
        OSError: If the data directory cannot be created (e.g. permissions).
    """
    if data_root is None:
        data_root = get_data_dir()

    if is_git_repo(data_root):
        logger.info("Data directory already initialized at %s — skipping", data_root)
        return

    logger.info("Initializing data directory at %s", data_root)

    # Create the data directory and initialize git
    init_data_repo(data_root)

    # Create all five layer subdirectories with placeholder README.md
    now = datetime.now(timezone.utc).isoformat()
    for layer in LAYERS:
        layer_dir = data_root / layer.slug
        layer_dir.mkdir(parents=True, exist_ok=True)
        write_narrative(data_root, layer.slug, f"# {layer.display_name}\n")

    # Write pre-seeded values
    _write_seed_values(data_root, now)

    # Create the initial commit
    commit_changes(data_root, "Initial data directory with pre-seeded Finnish values")
    logger.info("Data directory initialized with %d seed values", len(SEED_VALUES))


def _write_seed_values(data_root: Path, timestamp: str) -> None:
    """Write the pre-seeded Finnish values files."""
    values_dir = data_root / "values"
    values_dir.mkdir(parents=True, exist_ok=True)

    for filename, title, body in SEED_VALUES:
        frontmatter = {
            "title": title,
            "status": "active",
            "created": timestamp,
            "created_by": "system",
            "last_modified": timestamp,
            "last_modified_by": "system",
        }
        write_markdown(values_dir / filename, frontmatter, body)

    logger.info("Wrote %d seed value files to %s", len(SEED_VALUES), values_dir)
