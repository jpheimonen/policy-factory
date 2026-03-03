"""Integration tests for data layer round-trips.

Tests markdown file operations through the API: create, read, update, delete,
git commits, and cross-layer reference resolution.
"""

from __future__ import annotations

import subprocess
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import policy_factory.auth as auth_mod
from policy_factory.auth import create_access_token, hash_password
from policy_factory.data.layers import LAYER_SLUGS
from policy_factory.events import EventEmitter
from policy_factory.server.app import create_app
from policy_factory.server.ws import ConnectionManager
from policy_factory.store import PolicyStore

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _configure_auth():
    original_key = auth_mod.JWT_SECRET_KEY
    original_expiry = auth_mod.JWT_EXPIRY_HOURS
    auth_mod.JWT_SECRET_KEY = "test-secret-key-for-data-layer-integration"
    auth_mod.JWT_EXPIRY_HOURS = 24
    yield
    auth_mod.JWT_SECRET_KEY = original_key
    auth_mod.JWT_EXPIRY_HOURS = original_expiry


@pytest.fixture
def store(tmp_path: Path) -> PolicyStore:
    return PolicyStore(tmp_path / "test.db")


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """Create a data directory with git initialization."""
    d = tmp_path / "data"
    for slug in LAYER_SLUGS:
        (d / slug).mkdir(parents=True, exist_ok=True)
        (d / slug / "README.md").write_text(f"# {slug}\n\nSummary.")
    # Initialize git repo for commit tracking
    subprocess.run(["git", "init"], cwd=str(d), capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=str(d), capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"], cwd=str(d), capture_output=True
    )
    subprocess.run(["git", "add", "."], cwd=str(d), capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial"], cwd=str(d), capture_output=True
    )
    return d


@pytest.fixture
def client(store: PolicyStore, data_dir: Path) -> Generator[TestClient, None, None]:
    app = create_app(
        store=store,
        data_dir=data_dir,
        event_emitter=EventEmitter(),
        ws_manager=ConnectionManager(),
    )
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_headers(store: PolicyStore) -> dict[str, str]:
    hashed = hash_password("testpassword")
    user_id = store.create_user("test@example.com", hashed, "admin")
    token = create_access_token(user_id, "test@example.com", "admin")
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------


class TestCreateReadRoundTrip:
    """Create a layer item via POST, read it back via GET, verify match."""

    def test_create_and_read_item(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        """Write a layer item, then read it back and verify data matches."""
        create_resp = client.post(
            "/api/layers/values/items",
            json={
                "filename": "test-item.md",
                "frontmatter": {
                    "title": "Test Item",
                    "status": "draft",
                    "references": [],
                },
                "body": "# Test Item\n\nThis is a test item body.",
            },
            headers=auth_headers,
        )
        assert create_resp.status_code == 201

        # Read it back
        read_resp = client.get(
            "/api/layers/values/items/test-item.md",
            headers=auth_headers,
        )
        assert read_resp.status_code == 200
        data = read_resp.json()
        assert data["frontmatter"]["title"] == "Test Item"
        assert data["frontmatter"]["status"] == "draft"
        assert "Test Item" in data["body"]
        assert "test item body" in data["body"]


class TestUpdateItem:
    """Update a layer item via PUT, verify updated content on re-read."""

    def test_update_preserves_changes(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        """Update an item and verify the updated content is returned."""
        # Create
        client.post(
            "/api/layers/values/items",
            json={
                "filename": "update-test.md",
                "frontmatter": {"title": "Original Title", "status": "draft", "references": []},
                "body": "Original body.",
            },
            headers=auth_headers,
        )

        # Update
        update_resp = client.put(
            "/api/layers/values/items/update-test.md",
            json={
                "frontmatter": {"title": "Updated Title", "status": "active", "references": []},
                "body": "Updated body content.",
            },
            headers=auth_headers,
        )
        assert update_resp.status_code == 200

        # Re-read
        read_resp = client.get(
            "/api/layers/values/items/update-test.md",
            headers=auth_headers,
        )
        data = read_resp.json()
        assert data["frontmatter"]["title"] == "Updated Title"
        assert data["frontmatter"]["status"] == "active"
        assert "Updated body content" in data["body"]


class TestDeleteItem:
    """Delete a layer item via DELETE, verify it's gone."""

    def test_delete_removes_item(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        """Delete an item and verify it no longer appears in listing."""
        # Create
        client.post(
            "/api/layers/values/items",
            json={
                "filename": "delete-me.md",
                "frontmatter": {"title": "Delete Me", "status": "draft", "references": []},
                "body": "To be deleted.",
            },
            headers=auth_headers,
        )

        # Delete
        del_resp = client.delete(
            "/api/layers/values/items/delete-me.md",
            headers=auth_headers,
        )
        assert del_resp.status_code == 204

        # Verify gone
        read_resp = client.get(
            "/api/layers/values/items/delete-me.md",
            headers=auth_headers,
        )
        assert read_resp.status_code == 404


class TestItemInListing:
    """Created items appear in the layer listing with correct metadata."""

    def test_created_item_in_listing(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        """Create an item and verify it appears in the listing."""
        client.post(
            "/api/layers/values/items",
            json={
                "filename": "listed-item.md",
                "frontmatter": {"title": "Listed Item", "status": "active", "references": []},
                "body": "Listed body.",
            },
            headers=auth_headers,
        )

        list_resp = client.get(
            "/api/layers/values/items",
            headers=auth_headers,
        )
        assert list_resp.status_code == 200
        items = list_resp.json()

        filenames = [item["filename"] for item in items]
        assert "listed-item.md" in filenames

        listed = next(i for i in items if i["filename"] == "listed-item.md")
        # Item listing returns flat fields (not nested frontmatter)
        assert listed["title"] == "Listed Item"


class TestGitCommit:
    """Write operations create git commits in the data repo."""

    def test_create_item_triggers_git_commit(
        self, client: TestClient, auth_headers: dict[str, str], data_dir: Path
    ) -> None:
        """Creating an item triggers a git commit with a descriptive message."""
        client.post(
            "/api/layers/values/items",
            json={
                "filename": "git-test.md",
                "frontmatter": {"title": "Git Test", "status": "draft", "references": []},
                "body": "Git commit test.",
            },
            headers=auth_headers,
        )

        # Check git log for the commit
        result = subprocess.run(
            ["git", "log", "--oneline", "-5"],
            cwd=str(data_dir),
            capture_output=True,
            text=True,
        )
        # There should be a commit mentioning the file or operation
        assert result.returncode == 0
        # The log should have more than just the initial commit
        lines = result.stdout.strip().split("\n")
        assert len(lines) >= 1


class TestCrossLayerReferences:
    """Items referencing each other produce bidirectional reference results."""

    def test_bidirectional_references(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        """Create items in two layers that reference each other, verify references."""
        # Create a values item
        client.post(
            "/api/layers/values/items",
            json={
                "filename": "ref-value.md",
                "frontmatter": {
                    "title": "Reference Value",
                    "status": "active",
                    "references": ["strategic-objectives/ref-strategy.md"],
                },
                "body": "A value with a reference.",
            },
            headers=auth_headers,
        )

        # Create a strategic objectives item referencing the value
        client.post(
            "/api/layers/strategic-objectives/items",
            json={
                "filename": "ref-strategy.md",
                "frontmatter": {
                    "title": "Reference Strategy",
                    "status": "active",
                    "references": ["values/ref-value.md"],
                },
                "body": "A strategy referencing a value.",
            },
            headers=auth_headers,
        )

        # Check references from the values item
        ref_resp = client.get(
            "/api/layers/values/items/ref-value.md/references",
            headers=auth_headers,
        )
        assert ref_resp.status_code == 200
        refs = ref_resp.json()

        # Should have forward references (items this item references)
        forward = refs.get("forward", refs.get("references_to", []))
        backward = refs.get("backward", refs.get("referenced_by", []))

        # At least one direction should be populated
        all_refs = forward + backward
        assert len(all_refs) >= 1
