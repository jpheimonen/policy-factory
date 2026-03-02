"""Tests for the file tools module (agent/tools.py).

Tests cover:
- Path validation (sandbox security)
- list_files tool behavior
- read_file tool behavior
- write_file tool behavior
- delete_file tool behavior
- Tool definition structures
"""

from __future__ import annotations

from pathlib import Path

import pytest

from policy_factory.agent.tools import (
    DELETE_FILE_TOOL,
    FILE_TOOLS,
    FILE_TOOLS_WITH_WEB_SEARCH,
    LIST_FILES_TOOL,
    READ_FILE_TOOL,
    READ_ONLY_TOOLS,
    WEB_SEARCH_ONLY,
    WEB_SEARCH_TOOL,
    WRITE_FILE_TOOL,
    SandboxViolationError,
    delete_file,
    list_files,
    read_file,
    validate_path,
    write_file,
)


# ---------------------------------------------------------------------------
# Path validation tests
# ---------------------------------------------------------------------------


class TestPathValidation:
    """Tests for the validate_path function and sandbox security."""

    def test_valid_relative_path(self, tmp_path: Path) -> None:
        """Valid relative path within sandbox is accepted."""
        (tmp_path / "values").mkdir()
        (tmp_path / "values" / "test.md").write_text("content")

        resolved = validate_path(tmp_path, "values/test.md")
        assert resolved == (tmp_path / "values" / "test.md").resolve()

    def test_valid_nested_path(self, tmp_path: Path) -> None:
        """Nested relative paths within sandbox are accepted."""
        (tmp_path / "layer" / "subdir").mkdir(parents=True)
        (tmp_path / "layer" / "subdir" / "file.md").write_text("content")

        resolved = validate_path(tmp_path, "layer/subdir/file.md")
        assert resolved == (tmp_path / "layer" / "subdir" / "file.md").resolve()

    def test_valid_absolute_path_within_sandbox(self, tmp_path: Path) -> None:
        """Absolute path within sandbox is accepted."""
        (tmp_path / "values").mkdir()
        (tmp_path / "values" / "test.md").write_text("content")
        abs_path = str(tmp_path / "values" / "test.md")

        resolved = validate_path(tmp_path, abs_path)
        assert resolved == (tmp_path / "values" / "test.md").resolve()

    def test_reject_single_traversal(self, tmp_path: Path) -> None:
        """Path with ../ that escapes sandbox is rejected."""
        with pytest.raises(SandboxViolationError, match="escapes sandbox"):
            validate_path(tmp_path, "../escape.md")

    def test_reject_double_traversal(self, tmp_path: Path) -> None:
        """Path with multiple ../ that escapes sandbox is rejected."""
        with pytest.raises(SandboxViolationError, match="escapes sandbox"):
            validate_path(tmp_path, "../../escape.md")

    def test_reject_traversal_after_valid_dir(self, tmp_path: Path) -> None:
        """Path that goes into a dir then escapes is rejected."""
        (tmp_path / "values").mkdir()
        with pytest.raises(SandboxViolationError, match="escapes sandbox"):
            validate_path(tmp_path, "values/../../escape.md")

    def test_reject_traversal_deeply_nested(self, tmp_path: Path) -> None:
        """Deeply nested traversal that escapes is rejected."""
        (tmp_path / "a" / "b" / "c").mkdir(parents=True)
        with pytest.raises(SandboxViolationError, match="escapes sandbox"):
            validate_path(tmp_path, "a/b/c/../../../../escape.md")

    def test_reject_absolute_path_outside_sandbox(self, tmp_path: Path) -> None:
        """Absolute path outside sandbox is rejected."""
        with pytest.raises(SandboxViolationError, match="Absolute path outside sandbox"):
            validate_path(tmp_path, "/etc/passwd")

    def test_reject_absolute_path_sibling(self, tmp_path: Path) -> None:
        """Absolute path to sibling directory is rejected."""
        sibling = tmp_path.parent / "sibling"
        sibling.mkdir(exist_ok=True)
        (sibling / "file.md").write_text("content")

        with pytest.raises(SandboxViolationError, match="Absolute path outside sandbox"):
            validate_path(tmp_path, str(sibling / "file.md"))

    def test_reject_symlink_escaping_sandbox(self, tmp_path: Path) -> None:
        """Symlink that resolves outside sandbox is rejected."""
        # Create a target outside the sandbox
        outside = tmp_path.parent / "outside"
        outside.mkdir(exist_ok=True)
        target_file = outside / "secret.md"
        target_file.write_text("secret content")

        # Create symlink inside sandbox pointing outside
        symlink = tmp_path / "escape_link"
        symlink.symlink_to(target_file)

        with pytest.raises(SandboxViolationError, match="escapes sandbox"):
            validate_path(tmp_path, "escape_link")

    def test_reject_symlink_dir_escaping_sandbox(self, tmp_path: Path) -> None:
        """Symlink directory that resolves outside sandbox is rejected."""
        # Create a target directory outside the sandbox
        outside = tmp_path.parent / "outside_dir"
        outside.mkdir(exist_ok=True)
        (outside / "secret.md").write_text("secret content")

        # Create symlink directory inside sandbox pointing outside
        symlink_dir = tmp_path / "escape_dir"
        symlink_dir.symlink_to(outside)

        with pytest.raises(SandboxViolationError, match="escapes sandbox"):
            validate_path(tmp_path, "escape_dir/secret.md")

    def test_accept_symlink_within_sandbox(self, tmp_path: Path) -> None:
        """Symlink that resolves within sandbox is accepted."""
        # Create target inside sandbox
        (tmp_path / "values").mkdir()
        target = tmp_path / "values" / "real.md"
        target.write_text("content")

        # Create symlink also inside sandbox
        symlink = tmp_path / "values" / "link.md"
        symlink.symlink_to(target)

        resolved = validate_path(tmp_path, "values/link.md")
        assert resolved == target.resolve()

    def test_path_with_dot_segment(self, tmp_path: Path) -> None:
        """Path with ./ segment is normalized correctly."""
        (tmp_path / "values").mkdir()
        (tmp_path / "values" / "test.md").write_text("content")

        resolved = validate_path(tmp_path, "./values/test.md")
        assert resolved == (tmp_path / "values" / "test.md").resolve()

    def test_nonexistent_path_within_sandbox(self, tmp_path: Path) -> None:
        """Nonexistent path within sandbox is accepted (for writing)."""
        resolved = validate_path(tmp_path, "new-layer/new-file.md")
        assert resolved == (tmp_path / "new-layer" / "new-file.md").resolve()


# ---------------------------------------------------------------------------
# list_files tests
# ---------------------------------------------------------------------------


class TestListFiles:
    """Tests for the list_files tool."""

    def test_returns_md_files(self, tmp_path: Path) -> None:
        """Returns markdown filenames in directory."""
        (tmp_path / "values").mkdir()
        (tmp_path / "values" / "item-a.md").write_text("# A")
        (tmp_path / "values" / "item-b.md").write_text("# B")
        (tmp_path / "values" / "data.json").write_text("{}")  # Not .md

        result = list_files(tmp_path, "values")
        assert result["success"] is True
        assert sorted(result["data"]) == ["item-a.md", "item-b.md"]

    def test_excludes_readme(self, tmp_path: Path) -> None:
        """README.md is excluded from results."""
        (tmp_path / "values").mkdir()
        (tmp_path / "values" / "item.md").write_text("content")
        (tmp_path / "values" / "README.md").write_text("# Summary")
        (tmp_path / "values" / "readme.md").write_text("# Also summary")  # Lowercase

        result = list_files(tmp_path, "values")
        assert result["success"] is True
        assert "README.md" not in result["data"]
        assert "readme.md" not in result["data"]
        assert result["data"] == ["item.md"]

    def test_empty_directory(self, tmp_path: Path) -> None:
        """Returns empty list for empty directory."""
        (tmp_path / "values").mkdir()

        result = list_files(tmp_path, "values")
        assert result["success"] is True
        assert result["data"] == []

    def test_directory_with_only_readme(self, tmp_path: Path) -> None:
        """Directory with only README.md returns empty list."""
        (tmp_path / "values").mkdir()
        (tmp_path / "values" / "README.md").write_text("# Summary")

        result = list_files(tmp_path, "values")
        assert result["success"] is True
        assert result["data"] == []

    def test_error_path_outside_sandbox(self, tmp_path: Path) -> None:
        """Returns error for paths outside sandbox."""
        result = list_files(tmp_path, "../escape")
        assert "error" in result
        assert "escapes sandbox" in result["error"]

    def test_error_nonexistent_directory(self, tmp_path: Path) -> None:
        """Returns error for nonexistent directory."""
        result = list_files(tmp_path, "nonexistent")
        assert "error" in result
        assert "does not exist" in result["error"]

    def test_error_path_is_file(self, tmp_path: Path) -> None:
        """Returns error when path is not a directory."""
        (tmp_path / "file.md").write_text("content")

        result = list_files(tmp_path, "file.md")
        assert "error" in result
        assert "not a directory" in result["error"]

    def test_sorted_results(self, tmp_path: Path) -> None:
        """Results are returned in sorted order."""
        (tmp_path / "values").mkdir()
        (tmp_path / "values" / "z-last.md").write_text("")
        (tmp_path / "values" / "a-first.md").write_text("")
        (tmp_path / "values" / "m-middle.md").write_text("")

        result = list_files(tmp_path, "values")
        assert result["success"] is True
        assert result["data"] == ["a-first.md", "m-middle.md", "z-last.md"]

    def test_excludes_subdirectories(self, tmp_path: Path) -> None:
        """Subdirectories are not included in results."""
        (tmp_path / "values").mkdir()
        (tmp_path / "values" / "subdir").mkdir()
        (tmp_path / "values" / "item.md").write_text("")

        result = list_files(tmp_path, "values")
        assert result["success"] is True
        assert result["data"] == ["item.md"]


# ---------------------------------------------------------------------------
# read_file tests
# ---------------------------------------------------------------------------


class TestReadFile:
    """Tests for the read_file tool."""

    def test_returns_content(self, tmp_path: Path) -> None:
        """Returns content for existing file."""
        (tmp_path / "values").mkdir()
        content = "---\ntitle: Test\n---\n\nBody content."
        (tmp_path / "values" / "test.md").write_text(content)

        result = read_file(tmp_path, "values/test.md")
        assert result["success"] is True
        assert result["data"] == content

    def test_unicode_content(self, tmp_path: Path) -> None:
        """Returns unicode content correctly."""
        (tmp_path / "values").mkdir()
        content = "Finnish: Suomi 🇫🇮\nJapanese: 日本語"
        (tmp_path / "values" / "unicode.md").write_text(content, encoding="utf-8")

        result = read_file(tmp_path, "values/unicode.md")
        assert result["success"] is True
        assert result["data"] == content

    def test_error_nonexistent_file(self, tmp_path: Path) -> None:
        """Returns error for nonexistent file."""
        (tmp_path / "values").mkdir()

        result = read_file(tmp_path, "values/missing.md")
        assert "error" in result
        assert "does not exist" in result["error"]

    def test_error_path_outside_sandbox(self, tmp_path: Path) -> None:
        """Returns error for paths outside sandbox."""
        result = read_file(tmp_path, "../escape.md")
        assert "error" in result
        assert "escapes sandbox" in result["error"]

    def test_error_path_is_directory(self, tmp_path: Path) -> None:
        """Returns error when path is a directory."""
        (tmp_path / "values").mkdir()

        result = read_file(tmp_path, "values")
        assert "error" in result
        assert "not a file" in result["error"]

    def test_empty_file(self, tmp_path: Path) -> None:
        """Returns empty string for empty file."""
        (tmp_path / "values").mkdir()
        (tmp_path / "values" / "empty.md").write_text("")

        result = read_file(tmp_path, "values/empty.md")
        assert result["success"] is True
        assert result["data"] == ""


# ---------------------------------------------------------------------------
# write_file tests
# ---------------------------------------------------------------------------


class TestWriteFile:
    """Tests for the write_file tool."""

    def test_creates_new_file(self, tmp_path: Path) -> None:
        """Creates new file with content."""
        (tmp_path / "values").mkdir()
        content = "---\ntitle: New\n---\n\nContent."

        result = write_file(tmp_path, "values/new.md", content)
        assert result["success"] is True
        assert (tmp_path / "values" / "new.md").exists()
        assert (tmp_path / "values" / "new.md").read_text() == content

    def test_overwrites_existing_file(self, tmp_path: Path) -> None:
        """Overwrites existing file."""
        (tmp_path / "values").mkdir()
        (tmp_path / "values" / "existing.md").write_text("old content")

        result = write_file(tmp_path, "values/existing.md", "new content")
        assert result["success"] is True
        assert (tmp_path / "values" / "existing.md").read_text() == "new content"

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        """Creates parent directories if needed."""
        result = write_file(tmp_path, "new-layer/subdir/file.md", "content")
        assert result["success"] is True
        assert (tmp_path / "new-layer" / "subdir" / "file.md").exists()
        assert (tmp_path / "new-layer" / "subdir" / "file.md").read_text() == "content"

    def test_error_path_outside_sandbox(self, tmp_path: Path) -> None:
        """Returns error for paths outside sandbox."""
        result = write_file(tmp_path, "../escape.md", "malicious content")
        assert "error" in result
        assert "escapes sandbox" in result["error"]
        # Verify file was not created
        assert not (tmp_path.parent / "escape.md").exists()

    def test_unicode_content(self, tmp_path: Path) -> None:
        """Writes unicode content correctly."""
        (tmp_path / "values").mkdir()
        content = "Finnish: Suomi 🇫🇮\nJapanese: 日本語"

        result = write_file(tmp_path, "values/unicode.md", content)
        assert result["success"] is True
        assert (tmp_path / "values" / "unicode.md").read_text(encoding="utf-8") == content

    def test_empty_content(self, tmp_path: Path) -> None:
        """Writes empty content correctly."""
        (tmp_path / "values").mkdir()

        result = write_file(tmp_path, "values/empty.md", "")
        assert result["success"] is True
        assert (tmp_path / "values" / "empty.md").read_text() == ""


# ---------------------------------------------------------------------------
# delete_file tests
# ---------------------------------------------------------------------------


class TestDeleteFile:
    """Tests for the delete_file tool."""

    def test_removes_existing_file(self, tmp_path: Path) -> None:
        """Removes existing file."""
        (tmp_path / "values").mkdir()
        target = tmp_path / "values" / "delete-me.md"
        target.write_text("content")
        assert target.exists()

        result = delete_file(tmp_path, "values/delete-me.md")
        assert result["success"] is True
        assert "deleted" in result["data"].lower()
        assert not target.exists()

    def test_idempotent_nonexistent(self, tmp_path: Path) -> None:
        """Succeeds silently for nonexistent file (idempotent)."""
        (tmp_path / "values").mkdir()

        result = delete_file(tmp_path, "values/nonexistent.md")
        assert result["success"] is True
        assert "did not exist" in result["data"].lower()

    def test_error_path_outside_sandbox(self, tmp_path: Path) -> None:
        """Returns error for paths outside sandbox."""
        result = delete_file(tmp_path, "../escape.md")
        assert "error" in result
        assert "escapes sandbox" in result["error"]

    def test_error_path_is_directory(self, tmp_path: Path) -> None:
        """Returns error when path is a directory."""
        (tmp_path / "values").mkdir()

        result = delete_file(tmp_path, "values")
        assert "error" in result
        assert "not a file" in result["error"]

    def test_parent_directory_preserved(self, tmp_path: Path) -> None:
        """Deleting file does not remove parent directory."""
        (tmp_path / "values").mkdir()
        (tmp_path / "values" / "file.md").write_text("content")

        result = delete_file(tmp_path, "values/file.md")
        assert result["success"] is True
        assert (tmp_path / "values").exists()
        assert (tmp_path / "values").is_dir()


# ---------------------------------------------------------------------------
# Tool definition tests
# ---------------------------------------------------------------------------


class TestToolDefinitions:
    """Tests for tool definition structures."""

    def test_file_tools_contains_all_four(self) -> None:
        """FILE_TOOLS contains all four tools."""
        assert len(FILE_TOOLS) == 4
        names = {tool["name"] for tool in FILE_TOOLS}
        assert names == {"list_files", "read_file", "write_file", "delete_file"}

    def test_read_only_tools_subset(self) -> None:
        """READ_ONLY_TOOLS contains only list_files and read_file."""
        assert len(READ_ONLY_TOOLS) == 2
        names = {tool["name"] for tool in READ_ONLY_TOOLS}
        assert names == {"list_files", "read_file"}

    def test_file_tools_with_web_search(self) -> None:
        """FILE_TOOLS_WITH_WEB_SEARCH contains file tools plus web search."""
        assert len(FILE_TOOLS_WITH_WEB_SEARCH) == 5
        names = {tool.get("name") for tool in FILE_TOOLS_WITH_WEB_SEARCH}
        assert "list_files" in names
        assert "read_file" in names
        assert "write_file" in names
        assert "delete_file" in names
        assert "web_search" in names

    def test_web_search_only(self) -> None:
        """WEB_SEARCH_ONLY contains only web search tool."""
        assert len(WEB_SEARCH_ONLY) == 1
        assert WEB_SEARCH_ONLY[0]["name"] == "web_search"

    def test_web_search_tool_is_server_side(self) -> None:
        """Web search tool has server-side type attribute."""
        assert WEB_SEARCH_TOOL.get("type") == "web_search_20250305"

    def test_tool_has_required_fields(self) -> None:
        """All file tools have required schema fields."""
        required_fields = {"name", "description", "input_schema"}

        for tool in FILE_TOOLS:
            assert required_fields.issubset(tool.keys()), f"Tool {tool.get('name')} missing fields"

    def test_list_files_tool_schema(self) -> None:
        """list_files tool has correct input schema."""
        assert LIST_FILES_TOOL["name"] == "list_files"
        schema = LIST_FILES_TOOL["input_schema"]
        assert schema["type"] == "object"
        assert "path" in schema["properties"]
        assert "path" in schema["required"]

    def test_read_file_tool_schema(self) -> None:
        """read_file tool has correct input schema."""
        assert READ_FILE_TOOL["name"] == "read_file"
        schema = READ_FILE_TOOL["input_schema"]
        assert schema["type"] == "object"
        assert "path" in schema["properties"]
        assert "path" in schema["required"]

    def test_write_file_tool_schema(self) -> None:
        """write_file tool has correct input schema."""
        assert WRITE_FILE_TOOL["name"] == "write_file"
        schema = WRITE_FILE_TOOL["input_schema"]
        assert schema["type"] == "object"
        assert "path" in schema["properties"]
        assert "content" in schema["properties"]
        assert set(schema["required"]) == {"path", "content"}

    def test_delete_file_tool_schema(self) -> None:
        """delete_file tool has correct input schema."""
        assert DELETE_FILE_TOOL["name"] == "delete_file"
        schema = DELETE_FILE_TOOL["input_schema"]
        assert schema["type"] == "object"
        assert "path" in schema["properties"]
        assert "path" in schema["required"]

    def test_all_tools_have_descriptions(self) -> None:
        """All tools have non-empty descriptions."""
        for tool in FILE_TOOLS:
            assert tool.get("description"), f"Tool {tool.get('name')} has no description"
            assert len(tool["description"]) > 10, f"Tool {tool.get('name')} has too short description"

    def test_path_properties_have_descriptions(self) -> None:
        """All path properties have descriptions with examples."""
        for tool in FILE_TOOLS:
            schema = tool["input_schema"]
            path_prop = schema["properties"].get("path", {})
            assert "description" in path_prop, f"Tool {tool['name']} path has no description"
