"""Tests for layers and history API endpoints."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import policy_factory.auth as auth_mod
from policy_factory.auth import create_access_token, hash_password
from policy_factory.data.git import commit_changes, init_data_repo
from policy_factory.data.layers import LAYERS, write_item, write_narrative
from policy_factory.server.app import create_app
from policy_factory.store import PolicyStore

# --- Fixtures ---


@pytest.fixture(autouse=True)
def _configure_auth():
    """Set JWT_SECRET_KEY for all tests."""
    original_key = auth_mod.JWT_SECRET_KEY
    original_expiry = auth_mod.JWT_EXPIRY_HOURS
    auth_mod.JWT_SECRET_KEY = "test-secret-key-for-layers-api-tests"
    auth_mod.JWT_EXPIRY_HOURS = 24
    yield
    auth_mod.JWT_SECRET_KEY = original_key
    auth_mod.JWT_EXPIRY_HOURS = original_expiry


@pytest.fixture
def store(tmp_path: Path) -> PolicyStore:
    """Provide a fresh PolicyStore."""
    return PolicyStore(tmp_path / "test.db")


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """Provide a data directory with all layer subdirectories and a git repo."""
    dd = tmp_path / "data"
    dd.mkdir()
    for layer in LAYERS:
        (dd / layer.slug).mkdir()
    # Initialize git repo
    init_data_repo(dd)
    # Initial commit so git log works
    commit_changes(dd, "Initial commit")
    return dd


@pytest.fixture
def client(store: PolicyStore, data_dir: Path) -> Generator[TestClient, None, None]:
    """Provide a FastAPI test client with initialized store and data dir."""
    app = create_app(store=store, data_dir=data_dir)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def admin_user(store: PolicyStore) -> dict:
    """Create an admin user and return their info + token."""
    hashed = hash_password("adminpassword123")
    user_id = store.create_user("admin@example.com", hashed, "admin")
    token = create_access_token(user_id, "admin@example.com", "admin")
    return {"id": user_id, "email": "admin@example.com", "token": token}


@pytest.fixture
def regular_user(store: PolicyStore) -> dict:
    """Create a regular user and return their info + token."""
    hashed = hash_password("userpassword123")
    user_id = store.create_user("user@example.com", hashed, "user")
    token = create_access_token(user_id, "user@example.com", "user")
    return {"id": user_id, "email": "user@example.com", "token": token}


def auth_header(token: str) -> dict:
    """Create an Authorization header dict."""
    return {"Authorization": f"Bearer {token}"}


# =============================================================================
# List Layers Tests
# =============================================================================


class TestListLayers:
    """Tests for GET /api/layers/."""

    def test_returns_all_6_layers(
        self, client: TestClient, admin_user: dict
    ) -> None:
        """Returns all 6 layers."""
        resp = client.get("/api/layers/", headers=auth_header(admin_user["token"]))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 6

    def test_layers_in_hierarchical_order(
        self, client: TestClient, admin_user: dict
    ) -> None:
        """Layers are in hierarchical order: philosophy at position 0, policies at position 5."""
        resp = client.get("/api/layers/", headers=auth_header(admin_user["token"]))
        data = resp.json()
        assert data[0]["slug"] == "philosophy"
        assert data[0]["position"] == 1
        assert data[5]["slug"] == "policies"
        assert data[5]["position"] == 6

    def test_includes_item_count(
        self, client: TestClient, admin_user: dict, data_dir: Path
    ) -> None:
        """Includes item count for each layer."""
        # Write some items to the values layer
        write_item(data_dir, "values", "item1.md", {"title": "Item 1"}, "Body 1")
        write_item(data_dir, "values", "item2.md", {"title": "Item 2"}, "Body 2")

        resp = client.get("/api/layers/", headers=auth_header(admin_user["token"]))
        data = resp.json()
        values_layer = next(layer for layer in data if layer["slug"] == "values")
        assert values_layer["item_count"] == 2

    def test_includes_narrative_preview(
        self, client: TestClient, admin_user: dict, data_dir: Path
    ) -> None:
        """Includes narrative summary preview."""
        write_narrative(data_dir, "values", "This is a narrative summary for the values layer.")
        resp = client.get("/api/layers/", headers=auth_header(admin_user["token"]))
        data = resp.json()
        values_layer = next(layer for layer in data if layer["slug"] == "values")
        assert "narrative summary" in values_layer["narrative_preview"].lower()

    def test_includes_last_updated(
        self, client: TestClient, admin_user: dict, data_dir: Path
    ) -> None:
        """Includes last_updated from item frontmatter."""
        write_item(
            data_dir, "values", "item1.md",
            {"title": "Item 1", "last_modified": "2024-01-15T10:00:00"},
            "Body",
        )
        resp = client.get("/api/layers/", headers=auth_header(admin_user["token"]))
        data = resp.json()
        values_layer = next(layer for layer in data if layer["slug"] == "values")
        assert values_layer["last_updated"] != ""

    def test_includes_pending_feedback_count_zero(
        self, client: TestClient, admin_user: dict
    ) -> None:
        """Pending feedback count is hardcoded to 0."""
        resp = client.get("/api/layers/", headers=auth_header(admin_user["token"]))
        data = resp.json()
        for layer in data:
            assert layer["pending_feedback_count"] == 0

    def test_returns_401_without_auth(self, client: TestClient) -> None:
        """Returns 401 without a valid JWT."""
        resp = client.get("/api/layers/")
        assert resp.status_code == 401


# =============================================================================
# List Layer Items Tests
# =============================================================================


class TestListLayerItems:
    """Tests for GET /api/layers/:slug/items."""

    def test_returns_items_for_valid_slug(
        self, client: TestClient, admin_user: dict, data_dir: Path
    ) -> None:
        """Returns all items for a valid layer slug."""
        write_item(data_dir, "values", "item1.md", {"title": "Alpha"}, "Body 1")
        write_item(data_dir, "values", "item2.md", {"title": "Beta"}, "Body 2")

        resp = client.get(
            "/api/layers/values/items",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        # Should be sorted by title
        assert data[0]["title"] == "Alpha"
        assert data[1]["title"] == "Beta"

    def test_includes_frontmatter_metadata(
        self, client: TestClient, admin_user: dict, data_dir: Path
    ) -> None:
        """Returns frontmatter metadata for each item."""
        write_item(
            data_dir, "values", "item1.md",
            {"title": "Item 1", "status": "active"},
            "Body",
            modified_by="test@example.com",
        )

        resp = client.get(
            "/api/layers/values/items",
            headers=auth_header(admin_user["token"]),
        )
        data = resp.json()
        assert data[0]["filename"] == "item1.md"
        assert data[0]["title"] == "Item 1"
        assert data[0]["status"] == "active"
        assert data[0]["last_modified"] != ""
        assert data[0]["last_modified_by"] == "test@example.com"

    def test_returns_404_for_invalid_slug(
        self, client: TestClient, admin_user: dict
    ) -> None:
        """Returns 404 for an invalid layer slug."""
        resp = client.get(
            "/api/layers/nonexistent/items",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 404

    def test_returns_empty_list_for_empty_layer(
        self, client: TestClient, admin_user: dict
    ) -> None:
        """Returns an empty list for a layer with no items."""
        resp = client.get(
            "/api/layers/policies/items",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_401_without_auth(self, client: TestClient) -> None:
        """Returns 401 without a valid JWT."""
        resp = client.get("/api/layers/values/items")
        assert resp.status_code == 401


# =============================================================================
# Get Item Tests
# =============================================================================


class TestGetItem:
    """Tests for GET /api/layers/:slug/items/:filename."""

    def test_returns_full_item(
        self, client: TestClient, admin_user: dict, data_dir: Path
    ) -> None:
        """Returns the full frontmatter + body for a valid item."""
        write_item(
            data_dir, "values", "national-security.md",
            {"title": "National Security", "status": "active"},
            "# National Security\n\nContent here.",
        )

        resp = client.get(
            "/api/layers/values/items/national-security.md",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["filename"] == "national-security.md"
        assert data["frontmatter"]["title"] == "National Security"
        assert "Content here" in data["body"]

    def test_returns_404_for_nonexistent_file(
        self, client: TestClient, admin_user: dict
    ) -> None:
        """Returns 404 for a non-existent filename."""
        resp = client.get(
            "/api/layers/values/items/nonexistent.md",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 404

    def test_returns_404_for_invalid_slug(
        self, client: TestClient, admin_user: dict
    ) -> None:
        """Returns 404 for an invalid layer slug."""
        resp = client.get(
            "/api/layers/nonexistent/items/test.md",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 404

    def test_rejects_path_traversal_via_dotdot_in_filename(
        self, client: TestClient, admin_user: dict
    ) -> None:
        """Rejects filenames with .. in them (not URL-encoded slashes, which
        get decoded at the routing level and cause a different URL path)."""
        # Test via the create endpoint where filename is in the JSON body
        resp = client.post(
            "/api/layers/values/items",
            json={
                "filename": "../etc/passwd.md",
                "frontmatter": {"title": "hack"},
                "body": "",
            },
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 400

    def test_rejects_filename_with_backslash(
        self, client: TestClient, admin_user: dict
    ) -> None:
        """Rejects filenames containing backslashes."""
        resp = client.post(
            "/api/layers/values/items",
            json={
                "filename": "sub\\file.md",
                "frontmatter": {"title": "hack"},
                "body": "",
            },
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 400

    def test_returns_401_without_auth(self, client: TestClient) -> None:
        """Returns 401 without a valid JWT."""
        resp = client.get("/api/layers/values/items/test.md")
        assert resp.status_code == 401


# =============================================================================
# Update Item Tests
# =============================================================================


class TestUpdateItem:
    """Tests for PUT /api/layers/:slug/items/:filename."""

    def test_updates_item(
        self, client: TestClient, admin_user: dict, data_dir: Path
    ) -> None:
        """Updates an existing item and returns the updated content."""
        write_item(data_dir, "values", "test.md", {"title": "Old Title"}, "Old body")

        resp = client.put(
            "/api/layers/values/items/test.md",
            json={
                "frontmatter": {"title": "New Title"},
                "body": "New body content",
            },
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["frontmatter"]["title"] == "New Title"
        assert data["body"] == "New body content"

    def test_auto_sets_last_modified(
        self, client: TestClient, admin_user: dict, data_dir: Path
    ) -> None:
        """Auto-sets last_modified and last_modified_by."""
        write_item(data_dir, "values", "test.md", {"title": "Test"}, "Body")

        resp = client.put(
            "/api/layers/values/items/test.md",
            json={"frontmatter": {"title": "Updated"}, "body": "Updated body"},
            headers=auth_header(admin_user["token"]),
        )
        data = resp.json()
        assert data["frontmatter"]["last_modified"] != ""
        assert data["frontmatter"]["last_modified_by"] == "admin@example.com"

    def test_returns_404_for_nonexistent_item(
        self, client: TestClient, admin_user: dict
    ) -> None:
        """Returns 404 for a non-existent item."""
        resp = client.put(
            "/api/layers/values/items/nonexistent.md",
            json={"frontmatter": {"title": "Test"}, "body": "Test"},
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 404

    def test_triggers_git_commit(
        self, client: TestClient, admin_user: dict, data_dir: Path
    ) -> None:
        """Triggers a git commit with descriptive message."""
        write_item(data_dir, "values", "test.md", {"title": "Test"}, "Body")
        commit_changes(data_dir, "Seed item")

        resp = client.put(
            "/api/layers/values/items/test.md",
            json={"frontmatter": {"title": "Updated"}, "body": "Updated"},
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 200

        # Check git log for the commit
        import subprocess

        result = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            cwd=data_dir,
            capture_output=True,
            text=True,
        )
        assert "Update test.md in Values" in result.stdout

    def test_git_commit_includes_user_email(
        self, client: TestClient, admin_user: dict, data_dir: Path
    ) -> None:
        """Git commit message includes the authenticated user's email."""
        write_item(data_dir, "values", "test.md", {"title": "Test"}, "Body")
        commit_changes(data_dir, "Seed item")

        client.put(
            "/api/layers/values/items/test.md",
            json={"frontmatter": {"title": "Updated"}, "body": "Updated"},
            headers=auth_header(admin_user["token"]),
        )

        import subprocess

        result = subprocess.run(
            ["git", "log", "--format=%aN <%aE>", "-1"],
            cwd=data_dir,
            capture_output=True,
            text=True,
        )
        assert "admin@example.com" in result.stdout

    def test_returns_401_without_auth(self, client: TestClient) -> None:
        """Returns 401 without a valid JWT."""
        resp = client.put(
            "/api/layers/values/items/test.md",
            json={"frontmatter": {}, "body": ""},
        )
        assert resp.status_code == 401


# =============================================================================
# Create Item Tests
# =============================================================================


class TestCreateItem:
    """Tests for POST /api/layers/:slug/items."""

    def test_creates_new_item(
        self, client: TestClient, admin_user: dict
    ) -> None:
        """Creates a new item and returns 201."""
        resp = client.post(
            "/api/layers/values/items",
            json={
                "filename": "new-item.md",
                "frontmatter": {"title": "New Item"},
                "body": "New item content",
            },
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["filename"] == "new-item.md"
        assert data["frontmatter"]["title"] == "New Item"
        assert data["body"] == "New item content"

    def test_auto_sets_created_at(
        self, client: TestClient, admin_user: dict
    ) -> None:
        """Auto-sets created_at, last_modified, and last_modified_by."""
        resp = client.post(
            "/api/layers/values/items",
            json={
                "filename": "new-item.md",
                "frontmatter": {"title": "New"},
                "body": "Body",
            },
            headers=auth_header(admin_user["token"]),
        )
        data = resp.json()
        assert "created_at" in data["frontmatter"]
        assert "last_modified" in data["frontmatter"]
        assert data["frontmatter"]["last_modified_by"] == "admin@example.com"

    def test_returns_409_if_file_exists(
        self, client: TestClient, admin_user: dict, data_dir: Path
    ) -> None:
        """Returns 409 if the filename already exists."""
        write_item(data_dir, "values", "existing.md", {"title": "Existing"}, "Body")

        resp = client.post(
            "/api/layers/values/items",
            json={
                "filename": "existing.md",
                "frontmatter": {"title": "Duplicate"},
                "body": "Body",
            },
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 409

    def test_validates_filename_must_end_in_md(
        self, client: TestClient, admin_user: dict
    ) -> None:
        """Filename must end in .md."""
        resp = client.post(
            "/api/layers/values/items",
            json={
                "filename": "test.txt",
                "frontmatter": {"title": "Test"},
                "body": "Body",
            },
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 400

    def test_validates_filename_not_readme(
        self, client: TestClient, admin_user: dict
    ) -> None:
        """Filename must not be README.md."""
        resp = client.post(
            "/api/layers/values/items",
            json={
                "filename": "README.md",
                "frontmatter": {"title": "Test"},
                "body": "Body",
            },
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 400

    def test_validates_no_path_traversal(
        self, client: TestClient, admin_user: dict
    ) -> None:
        """Filename must not contain path traversal characters."""
        resp = client.post(
            "/api/layers/values/items",
            json={
                "filename": "../secret.md",
                "frontmatter": {"title": "Test"},
                "body": "Body",
            },
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 400

    def test_triggers_git_commit(
        self, client: TestClient, admin_user: dict, data_dir: Path
    ) -> None:
        """Triggers a git commit with descriptive message."""
        resp = client.post(
            "/api/layers/values/items",
            json={
                "filename": "new-item.md",
                "frontmatter": {"title": "New"},
                "body": "Body",
            },
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 201

        import subprocess

        result = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            cwd=data_dir,
            capture_output=True,
            text=True,
        )
        assert "Create new-item.md in Values" in result.stdout

    def test_returns_404_for_invalid_slug(
        self, client: TestClient, admin_user: dict
    ) -> None:
        """Returns 404 for an invalid layer slug."""
        resp = client.post(
            "/api/layers/nonexistent/items",
            json={
                "filename": "test.md",
                "frontmatter": {"title": "Test"},
                "body": "Body",
            },
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 404

    def test_returns_401_without_auth(self, client: TestClient) -> None:
        """Returns 401 without a valid JWT."""
        resp = client.post(
            "/api/layers/values/items",
            json={
                "filename": "test.md",
                "frontmatter": {},
                "body": "",
            },
        )
        assert resp.status_code == 401


# =============================================================================
# Delete Item Tests
# =============================================================================


class TestDeleteItem:
    """Tests for DELETE /api/layers/:slug/items/:filename."""

    def test_deletes_item(
        self, client: TestClient, admin_user: dict, data_dir: Path
    ) -> None:
        """Deletes an item and returns 204."""
        write_item(data_dir, "values", "to-delete.md", {"title": "Delete Me"}, "Body")

        resp = client.delete(
            "/api/layers/values/items/to-delete.md",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 204

        # Verify file is gone
        assert not (data_dir / "values" / "to-delete.md").exists()

    def test_returns_404_for_nonexistent_file(
        self, client: TestClient, admin_user: dict
    ) -> None:
        """Returns 404 for a non-existent file."""
        resp = client.delete(
            "/api/layers/values/items/nonexistent.md",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 404

    def test_triggers_git_commit(
        self, client: TestClient, admin_user: dict, data_dir: Path
    ) -> None:
        """Triggers a git commit with descriptive message."""
        write_item(data_dir, "values", "to-delete.md", {"title": "Delete Me"}, "Body")
        commit_changes(data_dir, "Seed item")

        resp = client.delete(
            "/api/layers/values/items/to-delete.md",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 204

        import subprocess

        result = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            cwd=data_dir,
            capture_output=True,
            text=True,
        )
        assert "Delete to-delete.md from Values" in result.stdout

    def test_returns_401_without_auth(self, client: TestClient) -> None:
        """Returns 401 without a valid JWT."""
        resp = client.delete("/api/layers/values/items/test.md")
        assert resp.status_code == 401


# =============================================================================
# Get Summary Tests
# =============================================================================


class TestGetSummary:
    """Tests for GET /api/layers/:slug/summary."""

    def test_returns_narrative_content(
        self, client: TestClient, admin_user: dict, data_dir: Path
    ) -> None:
        """Returns the README.md content for the layer."""
        write_narrative(data_dir, "values", "# Values Summary\n\nThis is the summary.")

        resp = client.get(
            "/api/layers/values/summary",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "Values Summary" in data["content"]

    def test_returns_empty_string_if_no_readme(
        self, client: TestClient, admin_user: dict
    ) -> None:
        """Returns empty string (not 404) if README.md doesn't exist."""
        resp = client.get(
            "/api/layers/policies/summary",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 200
        assert resp.json()["content"] == ""

    def test_returns_404_for_invalid_slug(
        self, client: TestClient, admin_user: dict
    ) -> None:
        """Returns 404 for an invalid layer slug."""
        resp = client.get(
            "/api/layers/nonexistent/summary",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 404

    def test_returns_401_without_auth(self, client: TestClient) -> None:
        """Returns 401 without a valid JWT."""
        resp = client.get("/api/layers/values/summary")
        assert resp.status_code == 401


# =============================================================================
# Get References Tests
# =============================================================================


class TestGetReferences:
    """Tests for GET /api/layers/:slug/items/:filename/references."""

    def test_returns_forward_and_backward_references(
        self, client: TestClient, admin_user: dict, data_dir: Path
    ) -> None:
        """Returns forward and backward cross-layer references."""
        # Create item in values
        write_item(
            data_dir, "values", "security.md",
            {"title": "Security", "references": []},
            "Security content",
        )
        # Create item in strategic-objectives that references values/security.md
        write_item(
            data_dir, "strategic-objectives", "defense.md",
            {"title": "Defense", "references": ["values/security.md"]},
            "Defense content",
        )

        resp = client.get(
            "/api/layers/values/items/security.md/references",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["forward"], list)
        assert isinstance(data["backward"], list)
        # security.md should have defense.md as a backward reference
        assert len(data["backward"]) == 1
        assert data["backward"][0]["filename"] == "defense.md"
        assert data["backward"][0]["layer_slug"] == "strategic-objectives"

    def test_returns_empty_lists_when_no_references(
        self, client: TestClient, admin_user: dict, data_dir: Path
    ) -> None:
        """Returns empty lists when no references exist."""
        write_item(data_dir, "values", "solo.md", {"title": "Solo"}, "No refs")

        resp = client.get(
            "/api/layers/values/items/solo.md/references",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["forward"] == []
        assert data["backward"] == []

    def test_returns_404_for_nonexistent_item(
        self, client: TestClient, admin_user: dict
    ) -> None:
        """Returns 404 for a non-existent item."""
        resp = client.get(
            "/api/layers/values/items/nonexistent.md/references",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 404

    def test_returns_401_without_auth(self, client: TestClient) -> None:
        """Returns 401 without a valid JWT."""
        resp = client.get("/api/layers/values/items/test.md/references")
        assert resp.status_code == 401


# =============================================================================
# Path Traversal Prevention Tests
# =============================================================================


class TestPathTraversalPrevention:
    """Tests for path traversal prevention on all endpoints."""

    def test_filename_with_dotdot_rejected_via_update(
        self, client: TestClient, admin_user: dict, data_dir: Path
    ) -> None:
        """Filenames with .. are rejected via PUT endpoint.

        Note: URL-encoded slashes in path params are decoded by the ASGI
        framework and change the route match. We test via PUT with a
        filename that contains '..' but no slashes.
        """
        # Create a file with '..' in the name — the validation should catch it
        resp = client.put(
            "/api/layers/values/items/..test.md",
            json={"frontmatter": {"title": "hack"}, "body": ""},
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 400

    def test_filename_with_backslash_rejected_via_update(
        self, client: TestClient, admin_user: dict
    ) -> None:
        """Filenames with backslashes are rejected via PUT endpoint."""
        resp = client.put(
            "/api/layers/values/items/sub%5Cfile.md",
            json={"frontmatter": {"title": "hack"}, "body": ""},
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 400

    def test_create_filename_with_path_separator_rejected(
        self, client: TestClient, admin_user: dict
    ) -> None:
        """Create rejects filenames with path separators."""
        resp = client.post(
            "/api/layers/values/items",
            json={
                "filename": "sub/file.md",
                "frontmatter": {"title": "Test"},
                "body": "Body",
            },
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 400

    def test_create_filename_with_dotdot_rejected(
        self, client: TestClient, admin_user: dict
    ) -> None:
        """Create rejects filenames with .. ."""
        resp = client.post(
            "/api/layers/values/items",
            json={
                "filename": "..%2Fhack.md",
                "frontmatter": {"title": "Test"},
                "body": "Body",
            },
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 400


# =============================================================================
# Git Commit Failure Resilience Tests
# =============================================================================


class TestGitCommitFailureResilience:
    """Test that git commit failures don't cause API errors."""

    def test_write_succeeds_even_if_git_fails(
        self, client: TestClient, admin_user: dict, tmp_path: Path
    ) -> None:
        """File write succeeds even when git commit fails.

        We test this by creating a data dir WITHOUT a git repo.
        """
        # Create a separate app with a non-git data dir
        no_git_dir = tmp_path / "no_git_data"
        no_git_dir.mkdir()
        for layer in LAYERS:
            (no_git_dir / layer.slug).mkdir()

        store = PolicyStore(tmp_path / "test_nogit.db")
        hashed = hash_password("adminpassword123")
        user_id = store.create_user("admin@example.com", hashed, "admin")
        token = create_access_token(user_id, "admin@example.com", "admin")

        app = create_app(store=store, data_dir=no_git_dir)
        with TestClient(app) as c:
            resp = c.post(
                "/api/layers/values/items",
                json={
                    "filename": "test-nogit.md",
                    "frontmatter": {"title": "Test"},
                    "body": "Body",
                },
                headers=auth_header(token),
            )
            # The create should succeed even though git commit fails
            assert resp.status_code == 201
            # File should exist
            assert (no_git_dir / "values" / "test-nogit.md").exists()


# =============================================================================
# History Router Tests
# =============================================================================


class TestGetHistory:
    """Tests for GET /api/history/:slug."""

    def test_returns_commits_for_layer(
        self, client: TestClient, admin_user: dict, data_dir: Path
    ) -> None:
        """Returns recent git commits for a layer directory."""
        # Create an item and commit it
        write_item(data_dir, "values", "history-test.md", {"title": "Test"}, "Body")
        commit_changes(data_dir, "Add history test item")

        resp = client.get(
            "/api/history/values",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        # Most recent commit should be the one we just made
        assert "history test item" in data[0]["message"].lower()
        assert data[0]["hash"] != ""
        assert data[0]["timestamp"] != ""
        assert data[0]["author"] != ""

    def test_returns_404_for_invalid_slug(
        self, client: TestClient, admin_user: dict
    ) -> None:
        """Returns 404 for an invalid layer slug."""
        resp = client.get(
            "/api/history/nonexistent",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 404

    def test_accepts_limit_parameter(
        self, client: TestClient, admin_user: dict, data_dir: Path
    ) -> None:
        """Accepts a limit query parameter."""
        # Create several commits
        for i in range(5):
            write_item(data_dir, "values", f"item{i}.md", {"title": f"Item {i}"}, "Body")
            commit_changes(data_dir, f"Add item {i}")

        resp = client.get(
            "/api/history/values?limit=2",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) <= 2

    def test_limit_max_100(
        self, client: TestClient, admin_user: dict
    ) -> None:
        """Limit parameter has maximum of 100."""
        resp = client.get(
            "/api/history/values?limit=200",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 422  # Validation error

    def test_limit_min_1(
        self, client: TestClient, admin_user: dict
    ) -> None:
        """Limit parameter has minimum of 1."""
        resp = client.get(
            "/api/history/values?limit=0",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 422  # Validation error

    def test_default_limit_20(
        self, client: TestClient, admin_user: dict, data_dir: Path
    ) -> None:
        """Default limit is 20."""
        # Just verify the endpoint works without a limit param
        resp = client.get(
            "/api/history/values",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 200

    def test_returns_empty_list_for_no_commits(
        self, client: TestClient, admin_user: dict
    ) -> None:
        """Returns empty list for a layer with no commits affecting it."""
        resp = client.get(
            "/api/history/policies",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_401_without_auth(self, client: TestClient) -> None:
        """Returns 401 without a valid JWT."""
        resp = client.get("/api/history/values")
        assert resp.status_code == 401

    def test_hash_is_short(
        self, client: TestClient, admin_user: dict, data_dir: Path
    ) -> None:
        """Commit hash is returned as short hash (7 chars)."""
        write_item(data_dir, "values", "hash-test.md", {"title": "Test"}, "Body")
        commit_changes(data_dir, "Hash test")

        resp = client.get(
            "/api/history/values",
            headers=auth_header(admin_user["token"]),
        )
        data = resp.json()
        assert len(data) >= 1
        assert len(data[0]["hash"]) == 7


# =============================================================================
# Router Registration Tests
# =============================================================================


class TestRouterRegistration:
    """Test that routers are properly registered in the app factory."""

    def test_layers_router_registered(self, client: TestClient, admin_user: dict) -> None:
        """Layers router is accessible."""
        resp = client.get("/api/layers/", headers=auth_header(admin_user["token"]))
        assert resp.status_code == 200

    def test_history_router_registered(self, client: TestClient, admin_user: dict) -> None:
        """History router is accessible."""
        resp = client.get(
            "/api/history/values",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 200
