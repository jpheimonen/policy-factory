"""Tests for the data directory initialization (data/init.py)."""

import os
from pathlib import Path
from unittest.mock import patch

from policy_factory.data.git import _run_git, is_git_repo
from policy_factory.data.init import get_data_dir, initialize_data_directory
from policy_factory.data.layers import LAYERS, list_items, read_narrative
from policy_factory.data.seed_values import SEED_VALUES

# ---------------------------------------------------------------------------
# get_data_dir
# ---------------------------------------------------------------------------


class TestGetDataDir:
    """Tests for data directory path resolution."""

    def test_default_path(self) -> None:
        """Without env var, defaults to cwd/data."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("POLICY_FACTORY_DATA_DIR", None)
            result = get_data_dir()
            assert result == Path.cwd() / "data"

    def test_env_var_override(self, tmp_path: Path) -> None:
        custom = str(tmp_path / "custom-data")
        with patch.dict(os.environ, {"POLICY_FACTORY_DATA_DIR": custom}):
            result = get_data_dir()
            assert result == Path(custom)


# ---------------------------------------------------------------------------
# initialize_data_directory
# ---------------------------------------------------------------------------


class TestInitializeDataDirectory:
    """Tests for first-run data directory initialization."""

    def test_creates_git_repo(self, tmp_path: Path) -> None:
        data_root = tmp_path / "data"
        initialize_data_directory(data_root)
        assert is_git_repo(data_root)

    def test_creates_all_layer_dirs(self, tmp_path: Path) -> None:
        data_root = tmp_path / "data"
        initialize_data_directory(data_root)

        for layer in LAYERS:
            layer_dir = data_root / layer.slug
            assert layer_dir.is_dir(), f"Missing layer directory: {layer.slug}"

    def test_creates_readme_in_each_layer(self, tmp_path: Path) -> None:
        data_root = tmp_path / "data"
        initialize_data_directory(data_root)

        for layer in LAYERS:
            content = read_narrative(data_root, layer.slug)
            assert content, f"README.md missing or empty for {layer.slug}"

    def test_writes_seed_values(self, tmp_path: Path) -> None:
        data_root = tmp_path / "data"
        initialize_data_directory(data_root)

        items = list_items(data_root, "values")
        assert len(items) == len(SEED_VALUES)

        # Verify each seed value exists with proper frontmatter
        filenames = {item.filename for item in items}
        for filename, title, _body in SEED_VALUES:
            assert filename in filenames, f"Missing seed file: {filename}"

    def test_seed_values_have_content(self, tmp_path: Path) -> None:
        """Each seed value should have substantive frontmatter and body."""
        data_root = tmp_path / "data"
        initialize_data_directory(data_root)

        from policy_factory.data.layers import read_item

        for filename, expected_title, _expected_body in SEED_VALUES:
            fm, body = read_item(data_root, "values", filename)
            assert fm.get("title") == expected_title
            assert fm.get("status") == "active"
            assert fm.get("created_by") == "system"
            assert fm.get("last_modified")
            assert fm.get("last_modified_by") == "system"
            assert len(body) > 100, f"Body too short for {filename}"

    def test_initial_commit_exists(self, tmp_path: Path) -> None:
        data_root = tmp_path / "data"
        initialize_data_directory(data_root)

        log = _run_git(["log", "--oneline"], cwd=data_root)
        assert "Initial data directory" in log.stdout

    def test_idempotent(self, tmp_path: Path) -> None:
        """Running initialization twice should not error or modify the repo."""
        data_root = tmp_path / "data"
        initialize_data_directory(data_root)

        # Get commit count after first init
        log_before = _run_git(["rev-list", "--count", "HEAD"], cwd=data_root)
        count_before = int(log_before.stdout.strip())

        # Run again
        initialize_data_directory(data_root)

        # Commit count should be unchanged
        log_after = _run_git(["rev-list", "--count", "HEAD"], cwd=data_root)
        count_after = int(log_after.stdout.strip())
        assert count_after == count_before

    def test_ten_seed_values(self, tmp_path: Path) -> None:
        """The spec requires approximately 10 pre-seeded values."""
        data_root = tmp_path / "data"
        initialize_data_directory(data_root)
        items = list_items(data_root, "values")
        assert len(items) >= 10
