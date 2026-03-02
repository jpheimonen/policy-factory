"""File operation tools for Policy Factory agents.

Provides sandboxed file tools that agents can invoke through the Anthropic
tool use API. All paths are validated to ensure they resolve within the
configured data directory.

Tools:
- list_files: List markdown filenames in a directory
- read_file: Read file content
- write_file: Create or overwrite a file
- delete_file: Remove a file (idempotent)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Path validation
# ---------------------------------------------------------------------------


class SandboxViolationError(Exception):
    """Raised when a path resolves outside the sandbox."""

    pass


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


def _error_result(message: str) -> dict[str, Any]:
    """Create an error result dict for tool responses."""
    return {"error": message}


def _success_result(data: Any) -> dict[str, Any]:
    """Create a success result dict for tool responses."""
    return {"success": True, "data": data}


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


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
# Tool definitions (Anthropic API format)
# ---------------------------------------------------------------------------

LIST_FILES_TOOL = {
    "name": "list_files",
    "description": (
        "List markdown filenames in a directory within the data folder. "
        "Returns a list of .md filenames, excluding README.md."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": (
                    "Directory path relative to the data root "
                    "(e.g., 'values', 'situational-awareness')"
                ),
            },
        },
        "required": ["path"],
    },
}

READ_FILE_TOOL = {
    "name": "read_file",
    "description": (
        "Read the content of a file within the data folder. "
        "Returns the full file content as text."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": (
                    "File path relative to the data root "
                    "(e.g., 'values/national-security.md')"
                ),
            },
        },
        "required": ["path"],
    },
}

WRITE_FILE_TOOL = {
    "name": "write_file",
    "description": (
        "Create or overwrite a file within the data folder. "
        "Parent directories are created automatically if needed."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": (
                    "File path relative to the data root "
                    "(e.g., 'values/new-value.md')"
                ),
            },
            "content": {
                "type": "string",
                "description": "The content to write to the file",
            },
        },
        "required": ["path", "content"],
    },
}

DELETE_FILE_TOOL = {
    "name": "delete_file",
    "description": (
        "Delete a file within the data folder. "
        "Succeeds silently if the file does not exist (idempotent)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": (
                    "File path relative to the data root "
                    "(e.g., 'values/old-value.md')"
                ),
            },
        },
        "required": ["path"],
    },
}


# ---------------------------------------------------------------------------
# Server-side tool definitions (handled by Anthropic's API)
# ---------------------------------------------------------------------------

# Web search is a server-side tool handled automatically by Anthropic's API.
# Results come back automatically - no client-side tool execution needed.
WEB_SEARCH_TOOL: dict[str, Any] = {
    "type": "web_search_20250305",
    "name": "web_search",
}

# ---------------------------------------------------------------------------
# Tool sets
# ---------------------------------------------------------------------------

# All file tools
FILE_TOOLS = [LIST_FILES_TOOL, READ_FILE_TOOL, WRITE_FILE_TOOL, DELETE_FILE_TOOL]

# Read-only subset for critic agents
READ_ONLY_TOOLS = [LIST_FILES_TOOL, READ_FILE_TOOL]

# File tools plus web search (for seed and heartbeat-sa-update)
FILE_TOOLS_WITH_WEB_SEARCH = FILE_TOOLS + [WEB_SEARCH_TOOL]

# Web search only (for heartbeat-skim and heartbeat-triage)
WEB_SEARCH_ONLY = [WEB_SEARCH_TOOL]

# Tool name to function mapping (for use by AgentSession)
# Note: web_search is not included - it's handled server-side by Anthropic
TOOL_FUNCTIONS = {
    "list_files": list_files,
    "read_file": read_file,
    "write_file": write_file,
    "delete_file": delete_file,
}
