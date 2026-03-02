"""Data directory initialization — first-run setup.

Called during FastAPI lifespan startup. Creates the data directory,
initializes the git repo, creates layer subdirectories with README
placeholders, and makes the initial commit.

The values layer starts empty; values are populated via explicit
seeding through the API endpoint, not at startup.

Idempotent: if the data directory and git repo already exist, does nothing.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from .git import commit_changes, init_data_repo, is_git_repo
from .layers import LAYERS, write_narrative

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
    for layer in LAYERS:
        layer_dir = data_root / layer.slug
        layer_dir.mkdir(parents=True, exist_ok=True)
        write_narrative(data_root, layer.slug, f"# {layer.display_name}\n")

    # Create the initial commit
    commit_changes(data_root, "Initial data directory structure")
    logger.info("Data directory initialized at %s", data_root)
