"""Git operations for the data directory.

Provides auto-initialization of the data git repo, committing changes,
and retrieving per-layer commit history. Follows the cc-runner pattern
of subprocess.run with capture and timeout.
"""

from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Default timeout for git commands (seconds)
_GIT_TIMEOUT = 30

# Author identity for automated commits
_DEFAULT_AUTHOR_NAME = "Policy Factory"
_DEFAULT_AUTHOR_EMAIL = "policy-factory@localhost"


# ---------------------------------------------------------------------------
# Low-level git command execution
# ---------------------------------------------------------------------------


def _run_git(
    args: list[str],
    cwd: Path,
    *,
    timeout: int = _GIT_TIMEOUT,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Execute a git command via subprocess.

    Args:
        args: Git sub-command and arguments (e.g. ``["init"]``).
        cwd: Working directory for the command.
        timeout: Timeout in seconds.
        check: Whether to raise on non-zero exit code.

    Returns:
        CompletedProcess with stdout/stderr captured as strings.

    Raises:
        subprocess.CalledProcessError: If check=True and the command fails.
        subprocess.TimeoutExpired: If the command exceeds the timeout.
    """
    cmd = ["git"] + args

    # Set author identity via environment so we don't need git config
    env = os.environ.copy()
    author_name = env.get("POLICY_FACTORY_GIT_AUTHOR", _DEFAULT_AUTHOR_NAME)
    author_email = env.get("POLICY_FACTORY_GIT_EMAIL", _DEFAULT_AUTHOR_EMAIL)
    env["GIT_AUTHOR_NAME"] = author_name
    env["GIT_AUTHOR_EMAIL"] = author_email
    env["GIT_COMMITTER_NAME"] = author_name
    env["GIT_COMMITTER_EMAIL"] = author_email

    return subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=check,
        env=env,
    )


def is_git_repo(data_root: Path) -> bool:
    """Check whether the data directory is an initialized git repository."""
    return (data_root / ".git").is_dir()


# ---------------------------------------------------------------------------
# Committing
# ---------------------------------------------------------------------------


def commit_changes(data_root: Path, message: str) -> bool:
    """Stage all changes and create a git commit.

    Args:
        data_root: Path to the data directory (the git repo root).
        message: Descriptive commit message.

    Returns:
        True if a commit was created, False if there were no changes.
    """
    # Stage everything
    _run_git(["add", "."], cwd=data_root)

    # Check if there's anything to commit
    result = _run_git(["status", "--porcelain"], cwd=data_root)
    if not result.stdout.strip():
        logger.debug("No changes to commit")
        return False

    _run_git(["commit", "-m", message], cwd=data_root)
    logger.info("Committed: %s", message)
    return True


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


@dataclass
class CommitEntry:
    """A single git commit from the log."""

    hash: str
    timestamp: str  # ISO 8601
    message: str
    author: str


def get_layer_history(
    data_root: Path,
    slug: str,
    *,
    limit: int = 20,
) -> list[CommitEntry]:
    """Return recent git commits that affected a specific layer directory.

    Args:
        data_root: Path to the data directory (git repo root).
        slug: Layer slug (used as subdirectory name).
        limit: Maximum number of commits to return.

    Returns:
        List of CommitEntry objects, most recent first.
        Returns an empty list if no commits exist.
    """
    layer_dir = slug  # Relative path within the repo

    # Use a separator unlikely to appear in commit messages
    sep = "---COMMIT_SEP---"
    log_format = f"%H{sep}%aI{sep}%s{sep}%aN"

    try:
        result = _run_git(
            [
                "log",
                f"--max-count={limit}",
                f"--format={log_format}",
                "--",
                layer_dir,
            ],
            cwd=data_root,
            check=False,
        )
    except subprocess.TimeoutExpired:
        logger.warning("git log timed out for layer %s", slug)
        return []

    if result.returncode != 0:
        # No commits yet or other issue
        return []

    entries: list[CommitEntry] = []
    for line in result.stdout.strip().splitlines():
        parts = line.split(sep)
        if len(parts) != 4:
            continue
        entries.append(
            CommitEntry(
                hash=parts[0],
                timestamp=parts[1],
                message=parts[2],
                author=parts[3],
            )
        )

    return entries


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


def init_data_repo(data_root: Path) -> None:
    """Initialize the data directory as a git repository.

    Creates the directory, runs ``git init``, and sets up an initial
    ``.gitignore``. Does NOT create layer directories or seed files —
    that is handled by the higher-level initialization function.

    This is a low-level helper; callers should check ``is_git_repo()``
    first to avoid re-initializing.
    """
    data_root.mkdir(parents=True, exist_ok=True)
    _run_git(["init"], cwd=data_root)

    # Create a minimal .gitignore for the data repo
    gitignore = data_root / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("# Data repo — managed by Policy Factory\n", encoding="utf-8")

    logger.info("Initialized git repository at %s", data_root)
