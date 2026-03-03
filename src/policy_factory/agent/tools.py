"""File operation tools for Policy Factory agents.

Provides sandboxed file tools served as MCP tool handlers via the
``claude-agent-sdk``.  All paths are validated to ensure they resolve
within the configured data directory.

Tools:
- list_files: List markdown filenames in a directory
- read_file: Read file content
- write_file: Create or overwrite a file
- delete_file: Remove a file (idempotent)
"""

from __future__ import annotations

import contextvars
import json
import logging
import os
from pathlib import Path
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool context (contextvars) — per-asyncio-task isolation
# ---------------------------------------------------------------------------

_tool_context_var: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar(
    "tool_context"
)


def _default_tool_context() -> dict[str, Any]:
    """Return a fresh default tool context dict."""
    return {"data_dir": None}


def _set_tool_context(data_dir: Path | None = None) -> None:
    """Set the tool context for the current asyncio task.

    Each task gets its own isolated context dict, so concurrent sessions
    (e.g. heartbeat + cascade running simultaneously) cannot interfere.

    Args:
        data_dir: The root data directory (sandbox boundary) for file tools.
    """
    ctx = {"data_dir": data_dir}
    _tool_context_var.set(ctx)


def get_tool_context() -> dict[str, Any]:
    """Get the tool context for the current asyncio task.

    Returns:
        The task-local tool context dict containing ``data_dir``.
        Falls back to a default (``data_dir=None``) context if none has been set.
    """
    try:
        return _tool_context_var.get()
    except LookupError:
        # No context set yet for this task — return a default.
        ctx = _default_tool_context()
        _tool_context_var.set(ctx)
        return ctx


# ---------------------------------------------------------------------------
# MCP result helper
# ---------------------------------------------------------------------------


def make_result(
    success: bool,
    data: Any | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    """Create a structured tool result in MCP content format.

    Args:
        success: Whether the operation succeeded.
        data: Result data (for success cases).
        error: Error message (for failure cases).

    Returns:
        A dict with the MCP content format::

            {"content": [{"type": "text", "text": "<json-encoded result>"}]}
    """
    result: dict[str, Any] = {"success": success}
    if data is not None:
        result["data"] = data
    if error:
        result["error"] = error

    return {"content": [{"type": "text", "text": json.dumps(result)}]}


# ---------------------------------------------------------------------------
# Path validation
# ---------------------------------------------------------------------------


class SandboxViolationError(Exception):
    """Raised when a path resolves outside the sandbox."""


def validate_path(data_dir: Path, relative_path: str) -> Path:
    """Validate and resolve a path within the data directory sandbox.

    Args:
        data_dir: The root data directory (sandbox boundary).
        relative_path: The path to validate (relative to data_dir).

    Returns:
        The resolved absolute Path if valid.

    Raises:
        SandboxViolationError: If the path would escape the sandbox.
    """
    # Reject absolute paths that don't start with data_dir
    if os.path.isabs(relative_path):
        abs_path = Path(relative_path)
        # Check if it's within data_dir
        try:
            abs_path.resolve().relative_to(data_dir.resolve())
        except ValueError:
            raise SandboxViolationError(
                f"Absolute path outside sandbox: {relative_path}"
            )
        # It's an absolute path within data_dir, use it
        target = abs_path
    else:
        target = data_dir / relative_path

    # Resolve to absolute path (follows symlinks)
    resolved = target.resolve()
    data_dir_resolved = data_dir.resolve()

    # Check that resolved path is within data_dir
    try:
        resolved.relative_to(data_dir_resolved)
    except ValueError:
        raise SandboxViolationError(
            f"Path escapes sandbox: {relative_path} resolves to {resolved}"
        )

    # Check for symlink that resolves outside sandbox
    # (already handled by resolve(), but let's be explicit)
    if target.is_symlink():
        link_target = target.resolve()
        try:
            link_target.relative_to(data_dir_resolved)
        except ValueError:
            raise SandboxViolationError(
                f"Symlink resolves outside sandbox: {relative_path}"
            )

    return resolved


# ---------------------------------------------------------------------------
# Tool implementations (unchanged — pure file I/O with sandbox validation)
# ---------------------------------------------------------------------------


def _error_result(message: str) -> dict[str, Any]:
    """Create an error result dict for tool responses."""
    return {"error": message}


def _success_result(data: Any) -> dict[str, Any]:
    """Create a success result dict for tool responses."""
    return {"success": True, "data": data}


def list_files(data_dir: Path, path: str) -> dict[str, Any]:
    """List markdown filenames in a directory.

    Args:
        data_dir: The root data directory (sandbox boundary).
        path: Directory path relative to data_dir.

    Returns:
        A dict with either:
        - {"success": True, "data": ["file1.md", "file2.md", ...]}
        - {"error": "error message"}
    """
    try:
        resolved = validate_path(data_dir, path)
    except SandboxViolationError as e:
        return _error_result(str(e))

    if not resolved.exists():
        return _error_result(f"Directory does not exist: {path}")

    if not resolved.is_dir():
        return _error_result(f"Path is not a directory: {path}")

    # List .md files, excluding README.md
    files: list[str] = []
    for item in sorted(resolved.iterdir()):
        if item.is_file() and item.suffix == ".md":
            if item.name.lower() != "readme.md":
                files.append(item.name)

    return _success_result(files)


def read_file(data_dir: Path, path: str) -> dict[str, Any]:
    """Read file content.

    Args:
        data_dir: The root data directory (sandbox boundary).
        path: File path relative to data_dir.

    Returns:
        A dict with either:
        - {"success": True, "data": "file content..."}
        - {"error": "error message"}
    """
    try:
        resolved = validate_path(data_dir, path)
    except SandboxViolationError as e:
        return _error_result(str(e))

    if not resolved.exists():
        return _error_result(f"File does not exist: {path}")

    if not resolved.is_file():
        return _error_result(f"Path is not a file: {path}")

    try:
        content = resolved.read_text(encoding="utf-8")
        return _success_result(content)
    except Exception as e:
        return _error_result(f"Failed to read file: {e}")


def write_file(data_dir: Path, path: str, content: str) -> dict[str, Any]:
    """Create or overwrite a file with provided content.

    Creates parent directories if needed.

    Args:
        data_dir: The root data directory (sandbox boundary).
        path: File path relative to data_dir.
        content: The content to write.

    Returns:
        A dict with either:
        - {"success": True, "data": "File written successfully"}
        - {"error": "error message"}
    """
    try:
        resolved = validate_path(data_dir, path)
    except SandboxViolationError as e:
        return _error_result(str(e))

    try:
        # Create parent directories if needed
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")
        return _success_result("File written successfully")
    except Exception as e:
        return _error_result(f"Failed to write file: {e}")


def delete_file(data_dir: Path, path: str) -> dict[str, Any]:
    """Remove a file (idempotent - succeeds even if file doesn't exist).

    Args:
        data_dir: The root data directory (sandbox boundary).
        path: File path relative to data_dir.

    Returns:
        A dict with either:
        - {"success": True, "data": "File deleted"} or "File did not exist"
        - {"error": "error message"}
    """
    try:
        resolved = validate_path(data_dir, path)
    except SandboxViolationError as e:
        return _error_result(str(e))

    if not resolved.exists():
        return _success_result("File did not exist")

    if not resolved.is_file():
        return _error_result(f"Path is not a file: {path}")

    try:
        resolved.unlink()
        return _success_result("File deleted")
    except Exception as e:
        return _error_result(f"Failed to delete file: {e}")


# ---------------------------------------------------------------------------
# MCP tool handlers — async wrappers decorated with @tool
# ---------------------------------------------------------------------------


def _invoke_file_tool(
    impl_fn: Any,
    args: dict[str, Any],
    arg_keys: tuple[str, ...] = ("path",),
) -> dict[str, Any]:
    """Invoke a file tool implementation with context and result conversion.

    Shared logic for all MCP tool handlers: resolves the tool context,
    validates ``data_dir``, calls the implementation function, and
    converts the implementation result dict to MCP result format.

    Args:
        impl_fn: The file tool implementation function (e.g. ``list_files``).
        args: The MCP tool arguments dict from the SDK.
        arg_keys: Keys to extract from ``args`` (after ``data_dir``).

    Returns:
        An MCP-formatted result dict.
    """
    ctx = get_tool_context()
    data_dir = ctx["data_dir"]
    if data_dir is None:
        return make_result(False, error="Tool context not initialised (no data_dir)")
    try:
        call_args = [data_dir] + [args.get(k, "") for k in arg_keys]
        result = impl_fn(*call_args)
        if "error" in result:
            return make_result(False, error=result["error"])
        return make_result(True, data=result["data"])
    except Exception as e:
        return make_result(False, error=str(e))


@tool(
    "list_files",
    "List markdown filenames in a directory within the data folder. "
    "Returns a list of .md filenames, excluding README.md.",
    {"path": str},
)
async def list_files_tool(args: dict[str, Any]) -> dict[str, Any]:
    """MCP handler for list_files."""
    return _invoke_file_tool(list_files, args)


@tool(
    "read_file",
    "Read the content of a file within the data folder. "
    "Returns the full file content as text.",
    {"path": str},
)
async def read_file_tool(args: dict[str, Any]) -> dict[str, Any]:
    """MCP handler for read_file."""
    return _invoke_file_tool(read_file, args)


@tool(
    "write_file",
    "Create or overwrite a file within the data folder. "
    "Parent directories are created automatically if needed.",
    {"path": str, "content": str},
)
async def write_file_tool(args: dict[str, Any]) -> dict[str, Any]:
    """MCP handler for write_file."""
    return _invoke_file_tool(write_file, args, arg_keys=("path", "content"))


@tool(
    "delete_file",
    "Delete a file within the data folder. "
    "Succeeds silently if the file does not exist (idempotent).",
    {"path": str},
)
async def delete_file_tool(args: dict[str, Any]) -> dict[str, Any]:
    """MCP handler for delete_file."""
    return _invoke_file_tool(delete_file, args)


# ---------------------------------------------------------------------------
# Tool set constants — MCP tool objects grouped by role needs
# ---------------------------------------------------------------------------

#: All four file tool handlers (for generator, heartbeat-sa-update, seed roles).
FULL_FILE_TOOLS = [list_files_tool, read_file_tool, write_file_tool, delete_file_tool]

#: Read-only subset (for critic role).
READ_ONLY_FILE_TOOLS = [list_files_tool, read_file_tool]

#: Tool set identifier constants used by the server factory.
TOOL_SET_FULL = "full"
TOOL_SET_READ_ONLY = "read_only"
TOOL_SET_NONE = "none"


# ---------------------------------------------------------------------------
# MCP server factory
# ---------------------------------------------------------------------------


def create_tools_server(
    data_dir: Path | None = None,
    tool_set: str = TOOL_SET_FULL,
) -> dict[str, Any]:
    """Create an MCP server with the appropriate file tools.

    Args:
        data_dir: The root data directory for sandboxed file operations.
        tool_set: Which tools to include. One of:
            - ``"full"``  — all four file tools
            - ``"read_only"`` — list_files and read_file only
            - ``"none"`` — no tools (returns an empty server)

    Returns:
        A dict mapping the server name ``"policy-factory-tools"`` to the
        ``McpSdkServerConfig``, ready for ``ClaudeAgentOptions.mcp_servers``.

    Raises:
        ValueError: If *tool_set* is not a recognised identifier.
    """
    _set_tool_context(data_dir)

    if tool_set == TOOL_SET_FULL:
        tools = list(FULL_FILE_TOOLS)
    elif tool_set == TOOL_SET_READ_ONLY:
        tools = list(READ_ONLY_FILE_TOOLS)
    elif tool_set == TOOL_SET_NONE:
        tools = []
    else:
        raise ValueError(f"Unknown tool set: {tool_set!r}")

    server = create_sdk_mcp_server(
        name="policy-factory-tools",
        version="1.0.0",
        tools=tools,
    )
    return {"policy-factory-tools": server}
