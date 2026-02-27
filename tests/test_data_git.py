"""Tests for the git operations module (data/git.py)."""

from pathlib import Path

import pytest

from policy_factory.data.git import (
    CommitEntry,
    _run_git,
    commit_changes,
    get_layer_history,
    init_data_repo,
    is_git_repo,
)


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a temporary git repository for testing."""
    init_data_repo(tmp_path)
    return tmp_path


# ---------------------------------------------------------------------------
# is_git_repo / init_data_repo
# ---------------------------------------------------------------------------


class TestGitInit:
    """Tests for repository detection and initialization."""

    def test_is_git_repo_false(self, tmp_path: Path) -> None:
        assert is_git_repo(tmp_path) is False

    def test_is_git_repo_true(self, git_repo: Path) -> None:
        assert is_git_repo(git_repo) is True

    def test_init_creates_git_dir(self, tmp_path: Path) -> None:
        repo = tmp_path / "data"
        init_data_repo(repo)
        assert (repo / ".git").is_dir()

    def test_init_creates_gitignore(self, tmp_path: Path) -> None:
        repo = tmp_path / "data"
        init_data_repo(repo)
        assert (repo / ".gitignore").exists()

    def test_init_on_existing_dir(self, tmp_path: Path) -> None:
        """Initializing in an existing non-git directory should work."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "existing.txt").write_text("hello", encoding="utf-8")
        init_data_repo(data_dir)
        assert is_git_repo(data_dir)


# ---------------------------------------------------------------------------
# commit_changes
# ---------------------------------------------------------------------------


class TestCommitChanges:
    """Tests for staging and committing changes."""

    def test_commit_with_changes(self, git_repo: Path) -> None:
        # Create a file to commit
        (git_repo / "test.txt").write_text("hello", encoding="utf-8")

        result = commit_changes(git_repo, "Add test file")
        assert result is True

        # Verify the commit exists
        log = _run_git(["log", "--oneline", "-1"], cwd=git_repo)
        assert "Add test file" in log.stdout

    def test_commit_no_changes(self, git_repo: Path) -> None:
        """Committing when there are no changes should succeed silently."""
        # Make an initial commit so the repo isn't empty
        (git_repo / "init.txt").write_text("init", encoding="utf-8")
        commit_changes(git_repo, "Initial")

        # Now commit again with no changes
        result = commit_changes(git_repo, "Empty commit attempt")
        assert result is False

    def test_commit_message_preserved(self, git_repo: Path) -> None:
        (git_repo / "file.txt").write_text("content", encoding="utf-8")
        commit_changes(git_repo, "Descriptive message about the change")

        log = _run_git(["log", "--format=%s", "-1"], cwd=git_repo)
        assert log.stdout.strip() == "Descriptive message about the change"

    def test_commit_author_identity(self, git_repo: Path) -> None:
        """Commits should use the Policy Factory identity."""
        (git_repo / "file.txt").write_text("content", encoding="utf-8")
        commit_changes(git_repo, "Test author")

        log = _run_git(["log", "--format=%aN", "-1"], cwd=git_repo)
        assert "Policy Factory" in log.stdout.strip()


# ---------------------------------------------------------------------------
# get_layer_history
# ---------------------------------------------------------------------------


class TestLayerHistory:
    """Tests for retrieving per-layer commit history."""

    def test_history_with_commits(self, git_repo: Path) -> None:
        # Create a layer directory with files
        values_dir = git_repo / "values"
        values_dir.mkdir()
        (values_dir / "item1.md").write_text("content 1", encoding="utf-8")
        commit_changes(git_repo, "Add item 1 to values")

        (values_dir / "item2.md").write_text("content 2", encoding="utf-8")
        commit_changes(git_repo, "Add item 2 to values")

        history = get_layer_history(git_repo, "values")
        assert len(history) == 2
        assert all(isinstance(entry, CommitEntry) for entry in history)
        # Most recent first
        assert history[0].message == "Add item 2 to values"
        assert history[1].message == "Add item 1 to values"

    def test_history_limit(self, git_repo: Path) -> None:
        values_dir = git_repo / "values"
        values_dir.mkdir()

        for i in range(5):
            (values_dir / f"item{i}.md").write_text(f"content {i}", encoding="utf-8")
            commit_changes(git_repo, f"Add item {i}")

        history = get_layer_history(git_repo, "values", limit=3)
        assert len(history) == 3

    def test_history_empty_layer(self, git_repo: Path) -> None:
        """A layer with no commits should return an empty list."""
        (git_repo / "policies").mkdir()
        history = get_layer_history(git_repo, "policies")
        assert history == []

    def test_history_only_shows_layer_commits(self, git_repo: Path) -> None:
        """History for a layer should only include commits affecting that layer."""
        values_dir = git_repo / "values"
        values_dir.mkdir()
        policies_dir = git_repo / "policies"
        policies_dir.mkdir()

        (values_dir / "v1.md").write_text("value", encoding="utf-8")
        commit_changes(git_repo, "Values commit")

        (policies_dir / "p1.md").write_text("policy", encoding="utf-8")
        commit_changes(git_repo, "Policies commit")

        values_history = get_layer_history(git_repo, "values")
        assert len(values_history) == 1
        assert values_history[0].message == "Values commit"

        policies_history = get_layer_history(git_repo, "policies")
        assert len(policies_history) == 1
        assert policies_history[0].message == "Policies commit"

    def test_history_entry_fields(self, git_repo: Path) -> None:
        """Each history entry should have all required fields."""
        values_dir = git_repo / "values"
        values_dir.mkdir()
        (values_dir / "item.md").write_text("content", encoding="utf-8")
        commit_changes(git_repo, "Test commit")

        history = get_layer_history(git_repo, "values")
        assert len(history) == 1
        entry = history[0]
        assert len(entry.hash) == 40  # Full SHA
        assert entry.timestamp  # ISO 8601
        assert entry.message == "Test commit"
        assert entry.author  # Should be set
