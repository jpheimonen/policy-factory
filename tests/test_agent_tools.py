"""Tests for the file tools module (agent/tools.py).

Tests cover:
- Path validation (sandbox security)
- list_files tool behavior
- read_file tool behavior
- write_file tool behavior
- delete_file tool behavior
- MCP tool definitions (@tool-decorated objects)
- MCP tool handler wrappers
- Tool context (contextvars isolation)
- MCP server factory
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from policy_factory.agent.tools import (
    FULL_FILE_TOOLS,
    READ_ONLY_FILE_TOOLS,
    TOOL_SET_FULL,
    TOOL_SET_NONE,
    TOOL_SET_READ_ONLY,
    SandboxViolationError,
    _set_tool_context,
    create_tools_server,
    delete_file,
    delete_file_tool,
    get_tool_context,
    list_files,
    list_files_tool,
    read_file,
    read_file_tool,
    validate_path,
    write_file,
    write_file_tool,
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
        content = "Finnish: Suomi \U0001f1eb\U0001f1ee\nJapanese: \u65e5\u672c\u8a9e"
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
        content = "Finnish: Suomi \U0001f1eb\U0001f1ee\nJapanese: \u65e5\u672c\u8a9e"

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
# MCP tool definition tests
# ---------------------------------------------------------------------------


class TestToolDefinitions:
    """Tests for @tool-decorated MCP tool objects."""

    def test_list_files_tool_attributes(self) -> None:
        """list_files tool has correct name, description, and schema."""
        assert list_files_tool.name == "list_files"
        assert list_files_tool.description
        assert len(list_files_tool.description) > 10
        assert "path" in list_files_tool.input_schema

    def test_read_file_tool_attributes(self) -> None:
        """read_file tool has correct name, description, and schema."""
        assert read_file_tool.name == "read_file"
        assert read_file_tool.description
        assert len(read_file_tool.description) > 10
        assert "path" in read_file_tool.input_schema

    def test_write_file_tool_attributes(self) -> None:
        """write_file tool has correct name, description, and schema."""
        assert write_file_tool.name == "write_file"
        assert write_file_tool.description
        assert len(write_file_tool.description) > 10
        assert "path" in write_file_tool.input_schema
        assert "content" in write_file_tool.input_schema

    def test_delete_file_tool_attributes(self) -> None:
        """delete_file tool has correct name, description, and schema."""
        assert delete_file_tool.name == "delete_file"
        assert delete_file_tool.description
        assert len(delete_file_tool.description) > 10
        assert "path" in delete_file_tool.input_schema

    def test_write_file_takes_path_and_content(self) -> None:
        """write_file requires both path and content; others require only path."""
        assert set(write_file_tool.input_schema.keys()) == {"path", "content"}
        assert set(list_files_tool.input_schema.keys()) == {"path"}
        assert set(read_file_tool.input_schema.keys()) == {"path"}
        assert set(delete_file_tool.input_schema.keys()) == {"path"}

    def test_all_tools_have_handler(self) -> None:
        """All tool objects expose a callable handler."""
        for t in FULL_FILE_TOOLS:
            assert callable(t.handler), f"Tool {t.name} has no callable handler"

    def test_full_file_tools_contains_all_four(self) -> None:
        """FULL_FILE_TOOLS contains all four tools."""
        assert len(FULL_FILE_TOOLS) == 4
        names = {t.name for t in FULL_FILE_TOOLS}
        assert names == {"list_files", "read_file", "write_file", "delete_file"}

    def test_read_only_tools_subset(self) -> None:
        """READ_ONLY_FILE_TOOLS contains only list_files and read_file."""
        assert len(READ_ONLY_FILE_TOOLS) == 2
        names = {t.name for t in READ_ONLY_FILE_TOOLS}
        assert names == {"list_files", "read_file"}


# ---------------------------------------------------------------------------
# Tool context tests
# ---------------------------------------------------------------------------


def _parse_mcp_result(result: dict[str, Any]) -> dict[str, Any]:
    """Helper: parse the JSON text from an MCP content result."""
    text = result["content"][0]["text"]
    return json.loads(text)


class TestToolContext:
    """Tests for _set_tool_context / get_tool_context."""

    def test_set_and_get(self, tmp_path: Path) -> None:
        """Setting context makes data_dir retrievable."""
        _set_tool_context(tmp_path)
        ctx = get_tool_context()
        assert ctx["data_dir"] == tmp_path

    def test_default_context_when_not_set(self) -> None:
        """get_tool_context returns a default with data_dir=None when unset."""
        import contextvars

        # Run inside a blank contextvars.Context so the ContextVar has no value
        blank = contextvars.Context()

        def _check() -> None:
            ctx = get_tool_context()
            assert ctx["data_dir"] is None

        blank.run(_check)

    def test_concurrent_task_isolation(self, tmp_path: Path) -> None:
        """Concurrent asyncio tasks have isolated contexts."""

        async def _run() -> None:
            dir_a = tmp_path / "a"
            dir_b = tmp_path / "b"
            dir_a.mkdir()
            dir_b.mkdir()

            results: dict[str, Path | None] = {}
            barrier = asyncio.Barrier(2)

            async def task_a() -> None:
                _set_tool_context(dir_a)
                await barrier.wait()  # sync with task_b
                ctx = get_tool_context()
                results["a"] = ctx["data_dir"]

            async def task_b() -> None:
                _set_tool_context(dir_b)
                await barrier.wait()  # sync with task_a
                ctx = get_tool_context()
                results["b"] = ctx["data_dir"]

            # Run in separate tasks to get separate contextvars scopes
            await asyncio.gather(
                asyncio.create_task(task_a()),
                asyncio.create_task(task_b()),
            )

            assert results["a"] == dir_a
            assert results["b"] == dir_b

        asyncio.run(_run())


# ---------------------------------------------------------------------------
# MCP tool handler tests
# ---------------------------------------------------------------------------


class TestMCPHandlers:
    """Tests for the async MCP tool handler wrappers."""

    @pytest.fixture(autouse=True)
    def _setup_context(self, tmp_path: Path) -> None:
        """Set up a tool context with tmp_path before each test."""
        _set_tool_context(tmp_path)
        self.data_dir = tmp_path

    @pytest.mark.asyncio
    async def test_list_files_handler(self) -> None:
        """list_files MCP handler returns results in MCP content format."""
        (self.data_dir / "values").mkdir()
        (self.data_dir / "values" / "item.md").write_text("content")

        result = await list_files_tool.handler({"path": "values"})
        parsed = _parse_mcp_result(result)
        assert parsed["success"] is True
        assert parsed["data"] == ["item.md"]

    @pytest.mark.asyncio
    async def test_read_file_handler(self) -> None:
        """read_file MCP handler returns file content in MCP format."""
        (self.data_dir / "values").mkdir()
        (self.data_dir / "values" / "test.md").write_text("hello world")

        result = await read_file_tool.handler({"path": "values/test.md"})
        parsed = _parse_mcp_result(result)
        assert parsed["success"] is True
        assert parsed["data"] == "hello world"

    @pytest.mark.asyncio
    async def test_write_file_handler(self) -> None:
        """write_file MCP handler writes file and returns success."""
        (self.data_dir / "values").mkdir()

        result = await write_file_tool.handler(
            {"path": "values/new.md", "content": "new content"}
        )
        parsed = _parse_mcp_result(result)
        assert parsed["success"] is True
        assert (self.data_dir / "values" / "new.md").read_text() == "new content"

    @pytest.mark.asyncio
    async def test_delete_file_handler(self) -> None:
        """delete_file MCP handler deletes file and returns success."""
        (self.data_dir / "values").mkdir()
        target = self.data_dir / "values" / "bye.md"
        target.write_text("gone")

        result = await delete_file_tool.handler({"path": "values/bye.md"})
        parsed = _parse_mcp_result(result)
        assert parsed["success"] is True
        assert not target.exists()

    @pytest.mark.asyncio
    async def test_sandbox_violation_returned_as_error(self) -> None:
        """Sandbox violations are caught and returned as MCP error results."""
        result = await read_file_tool.handler({"path": "../escape.md"})
        parsed = _parse_mcp_result(result)
        assert parsed["success"] is False
        assert "escapes sandbox" in parsed["error"]

    @pytest.mark.asyncio
    async def test_io_error_returned_as_error(self) -> None:
        """I/O errors (e.g. nonexistent file) are returned as MCP error results."""
        result = await read_file_tool.handler({"path": "nonexistent.md"})
        parsed = _parse_mcp_result(result)
        assert parsed["success"] is False
        assert "does not exist" in parsed["error"]

    @pytest.mark.asyncio
    async def test_handler_with_no_context(self) -> None:
        """Handler returns error when tool context has no data_dir."""
        # Explicitly clear the context so data_dir is None
        _set_tool_context(None)

        result = await list_files_tool.handler({"path": "values"})
        parsed = _parse_mcp_result(result)
        assert parsed["success"] is False
        assert "data_dir" in parsed["error"].lower()

        # Restore context for other tests in this class
        _set_tool_context(self.data_dir)


# ---------------------------------------------------------------------------
# MCP server factory tests
# ---------------------------------------------------------------------------


class TestCreateToolsServer:
    """Tests for the create_tools_server factory function."""

    def test_returns_dict_with_server_name(self, tmp_path: Path) -> None:
        """Factory returns a dict keyed by 'policy-factory-tools'."""
        result = create_tools_server(data_dir=tmp_path, tool_set=TOOL_SET_FULL)
        assert "policy-factory-tools" in result

    def test_full_tool_set(self, tmp_path: Path) -> None:
        """Full tool set includes all four tools."""
        result = create_tools_server(data_dir=tmp_path, tool_set=TOOL_SET_FULL)
        assert "policy-factory-tools" in result
        # The server object is created successfully (type is McpSdkServerConfig)
        server = result["policy-factory-tools"]
        assert server is not None

    def test_read_only_tool_set(self, tmp_path: Path) -> None:
        """Read-only tool set creates server successfully."""
        result = create_tools_server(data_dir=tmp_path, tool_set=TOOL_SET_READ_ONLY)
        assert "policy-factory-tools" in result
        server = result["policy-factory-tools"]
        assert server is not None

    def test_none_tool_set(self, tmp_path: Path) -> None:
        """None tool set creates server with no tools."""
        result = create_tools_server(data_dir=tmp_path, tool_set=TOOL_SET_NONE)
        assert "policy-factory-tools" in result

    def test_invalid_tool_set_raises(self, tmp_path: Path) -> None:
        """Unknown tool set identifier raises ValueError."""
        with pytest.raises(ValueError, match="Unknown tool set"):
            create_tools_server(data_dir=tmp_path, tool_set="invalid")

    def test_sets_tool_context(self, tmp_path: Path) -> None:
        """Factory sets the tool context with the given data_dir."""
        create_tools_server(data_dir=tmp_path, tool_set=TOOL_SET_FULL)
        ctx = get_tool_context()
        assert ctx["data_dir"] == tmp_path
