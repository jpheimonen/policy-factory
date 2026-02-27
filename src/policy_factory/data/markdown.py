"""Markdown file utilities with YAML frontmatter support.

Provides reading and writing of markdown files that have YAML frontmatter
delimited by ``---``. Follows the cc-runner frontmatter parsing pattern
but returns raw dicts instead of typed dataclasses, since each layer's
items have different frontmatter schemas.
"""

from __future__ import annotations

from pathlib import Path

import yaml


def read_markdown(path: Path) -> tuple[dict, str]:
    """Read a markdown file and parse its YAML frontmatter.

    Args:
        path: Path to the markdown file.

    Returns:
        A tuple of (frontmatter_dict, body_string).
        - If the file has valid YAML frontmatter, returns the parsed dict and the body.
        - If the file has no frontmatter (no opening ``---``), returns ({}, full_content).
        - If the YAML is malformed, returns ({}, full_content) — graceful degradation.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    if not path.exists():
        raise FileNotFoundError(f"Markdown file not found: {path}")

    content = path.read_text(encoding="utf-8")
    return parse_frontmatter(content)


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from a markdown string.

    Args:
        text: The full markdown text (possibly with frontmatter).

    Returns:
        A tuple of (frontmatter_dict, body_string).
    """
    if not text.startswith("---"):
        return {}, text

    # Find the closing ---
    end_idx = text.find("\n---", 3)
    if end_idx == -1:
        # No closing delimiter — treat as no frontmatter
        return {}, text

    yaml_block = text[4:end_idx]  # Skip opening "---\n"
    body = text[end_idx + 4:]  # Skip closing "\n---"

    # Strip one leading newline from body if present
    if body.startswith("\n"):
        body = body[1:]

    try:
        data = yaml.safe_load(yaml_block)
        if not isinstance(data, dict):
            # YAML parsed but not a dict (e.g. a scalar or list)
            return {}, text
    except yaml.YAMLError:
        # Malformed YAML — graceful degradation
        return {}, text

    return data, body


def write_markdown(path: Path, frontmatter: dict, body: str) -> None:
    """Write a markdown file with YAML frontmatter.

    Args:
        path: Path to the markdown file. Parent directories are created if needed.
        frontmatter: Dict of frontmatter fields. If empty, no YAML block is written.
        body: The markdown body content.
    """
    # Ensure parent directories exist
    path.parent.mkdir(parents=True, exist_ok=True)

    if frontmatter:
        # Serialize YAML with deterministic key ordering and consistent formatting
        yaml_str = yaml.dump(
            frontmatter,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=True,
            width=120,
        )
        content = f"---\n{yaml_str}---\n{body}"
    else:
        content = body

    path.write_text(content, encoding="utf-8")
