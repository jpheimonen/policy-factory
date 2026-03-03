"""Layer directory utilities for the five-layer policy stack.

Provides layer definitions, item CRUD, narrative summaries, and
cross-layer reference resolution.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .markdown import read_markdown, write_markdown

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Layer definitions
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LayerInfo:
    """Metadata for a single layer in the policy stack."""

    slug: str
    display_name: str
    position: int  # 1 = bottom (values), 5 = top (policies)


# Ordered bottom-to-top
LAYERS: list[LayerInfo] = [
    LayerInfo(slug="values", display_name="Values", position=1),
    LayerInfo(slug="situational-awareness", display_name="Situational Awareness", position=2),
    LayerInfo(slug="strategic-objectives", display_name="Strategic Objectives", position=3),
    LayerInfo(slug="tactical-objectives", display_name="Tactical Objectives", position=4),
    LayerInfo(slug="policies", display_name="Policies", position=5),
]

LAYER_SLUGS: set[str] = {layer.slug for layer in LAYERS}
_LAYER_BY_SLUG: dict[str, LayerInfo] = {layer.slug: layer for layer in LAYERS}


def get_layer(slug: str) -> LayerInfo | None:
    """Return the LayerInfo for a given slug, or None if invalid."""
    return _LAYER_BY_SLUG.get(slug)


def validate_layer_slug(slug: str) -> LayerInfo:
    """Validate a layer slug and return its info.

    Args:
        slug: The layer slug to validate.

    Returns:
        The corresponding LayerInfo.

    Raises:
        ValueError: If the slug is not a valid layer.
    """
    layer = get_layer(slug)
    if layer is None:
        valid = ", ".join(sorted(LAYER_SLUGS))
        raise ValueError(f"Invalid layer slug: {slug!r}. Valid slugs: {valid}")
    return layer


def get_layer_path(data_root: Path, slug: str) -> Path:
    """Return the filesystem path for a layer directory.

    Args:
        data_root: Root data directory (e.g. ``data/``).
        slug: A valid layer slug.

    Returns:
        Path to the layer directory.

    Raises:
        ValueError: If the slug is invalid.
    """
    validate_layer_slug(slug)
    return data_root / slug


# ---------------------------------------------------------------------------
# Item listing / CRUD
# ---------------------------------------------------------------------------

@dataclass
class ItemSummary:
    """Summary metadata for a layer item (used in listings)."""

    filename: str
    title: str
    status: str
    last_modified: str
    last_modified_by: str


def list_items(data_root: Path, slug: str) -> list[ItemSummary]:
    """List all items in a layer directory.

    Scans for ``.md`` files, excluding ``README.md``, reads YAML frontmatter
    and returns summary metadata sorted by title (then filename as fallback).

    Args:
        data_root: Root data directory.
        slug: Layer slug.

    Returns:
        Sorted list of ItemSummary objects.
    """
    layer_dir = get_layer_path(data_root, slug)
    if not layer_dir.is_dir():
        return []

    items: list[ItemSummary] = []
    for md_file in sorted(layer_dir.glob("*.md")):
        if md_file.name.lower() == "readme.md":
            continue

        try:
            fm, _body = read_markdown(md_file)
        except Exception:
            logger.warning("Failed to read %s, skipping", md_file)
            continue

        items.append(
            ItemSummary(
                filename=md_file.name,
                title=str(fm.get("title", md_file.stem)),
                status=str(fm.get("status", "")),
                last_modified=str(fm.get("last_modified", "")),
                last_modified_by=str(fm.get("last_modified_by", "")),
            )
        )

    # Sort by title (case-insensitive), then filename as tiebreaker
    items.sort(key=lambda item: (item.title.lower(), item.filename))
    return items


def read_item(data_root: Path, slug: str, filename: str) -> tuple[dict, str]:
    """Read a single item from a layer.

    Args:
        data_root: Root data directory.
        slug: Layer slug.
        filename: The markdown filename (e.g. ``national-security.md``).

    Returns:
        Tuple of (frontmatter_dict, body_string).

    Raises:
        ValueError: If the layer slug is invalid.
        FileNotFoundError: If the file does not exist.
    """
    layer_dir = get_layer_path(data_root, slug)
    return read_markdown(layer_dir / filename)


def write_item(
    data_root: Path,
    slug: str,
    filename: str,
    frontmatter: dict,
    body: str,
    *,
    modified_by: str = "system",
) -> None:
    """Write (create or update) an item in a layer.

    Automatically sets ``last_modified`` to the current UTC timestamp
    and ``last_modified_by`` to the given author.

    Args:
        data_root: Root data directory.
        slug: Layer slug.
        filename: The markdown filename.
        frontmatter: Dict of frontmatter fields.
        body: Markdown body content.
        modified_by: Who is making the change (email or agent name).
    """
    layer_dir = get_layer_path(data_root, slug)

    # Stamp modification metadata
    fm = dict(frontmatter)
    fm["last_modified"] = datetime.now(timezone.utc).isoformat()
    fm["last_modified_by"] = modified_by

    write_markdown(layer_dir / filename, fm, body)


def delete_item(data_root: Path, slug: str, filename: str) -> None:
    """Delete an item from a layer (idempotent).

    Args:
        data_root: Root data directory.
        slug: Layer slug.
        filename: The markdown filename.
    """
    layer_dir = get_layer_path(data_root, slug)
    target = layer_dir / filename
    if target.exists():
        target.unlink()


# ---------------------------------------------------------------------------
# Narrative summary (README.md)
# ---------------------------------------------------------------------------

def read_narrative(data_root: Path, slug: str) -> str:
    """Read the narrative summary (README.md) for a layer.

    Returns:
        The content of README.md, or an empty string if it doesn't exist.
    """
    layer_dir = get_layer_path(data_root, slug)
    readme = layer_dir / "README.md"
    if not readme.exists():
        return ""
    return readme.read_text(encoding="utf-8")


def write_narrative(data_root: Path, slug: str, content: str) -> None:
    """Write or update the narrative summary (README.md) for a layer.

    Args:
        data_root: Root data directory.
        slug: Layer slug.
        content: The narrative summary content.
    """
    layer_dir = get_layer_path(data_root, slug)
    layer_dir.mkdir(parents=True, exist_ok=True)
    (layer_dir / "README.md").write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Cross-layer reference resolution
# ---------------------------------------------------------------------------

@dataclass
class Reference:
    """A resolved cross-layer reference."""

    layer_slug: str
    filename: str
    title: str


def resolve_references(
    data_root: Path,
    slug: str,
    filename: str,
) -> tuple[list[Reference], list[Reference]]:
    """Resolve cross-layer references for a given item.

    References in frontmatter use the format ``layer-slug/filename.md``
    (e.g. ``values/national-security.md``). This function returns both
    forward references (items this item explicitly references) and backward
    references (items in other layers that reference this item).

    Args:
        data_root: Root data directory.
        slug: Layer slug of the item.
        filename: Filename of the item.

    Returns:
        A tuple of (forward_references, backward_references).
        Each list contains Reference objects with layer_slug, filename, and title.
    """
    # --- Forward references ---
    forward: list[Reference] = []
    try:
        fm, _body = read_item(data_root, slug, filename)
    except FileNotFoundError:
        return [], []

    refs = fm.get("references", [])
    if isinstance(refs, list):
        for ref_str in refs:
            ref_str = str(ref_str)
            ref = _parse_reference(data_root, ref_str)
            if ref is not None:
                forward.append(ref)

    # --- Backward references ---
    item_ref_id = f"{slug}/{filename}"
    backward: list[Reference] = []
    for layer in LAYERS:
        layer_dir = data_root / layer.slug
        if not layer_dir.is_dir():
            continue
        for md_file in sorted(layer_dir.glob("*.md")):
            if md_file.name.lower() == "readme.md":
                continue
            # Skip self
            if layer.slug == slug and md_file.name == filename:
                continue

            try:
                other_fm, _body = read_markdown(md_file)
            except Exception:
                continue

            other_refs = other_fm.get("references", [])
            if isinstance(other_refs, list):
                for ref_str in other_refs:
                    if str(ref_str) == item_ref_id:
                        backward.append(
                            Reference(
                                layer_slug=layer.slug,
                                filename=md_file.name,
                                title=str(other_fm.get("title", md_file.stem)),
                            )
                        )
                        break  # This item already references us, no need to check more refs

    return forward, backward


def _parse_reference(data_root: Path, ref_str: str) -> Reference | None:
    """Parse a reference string and resolve it to a Reference.

    Expected format: ``layer-slug/filename.md``.

    Returns:
        A Reference if the referenced file exists, None otherwise.
    """
    if "/" not in ref_str:
        return None

    parts = ref_str.split("/", 1)
    ref_slug, ref_filename = parts[0], parts[1]

    if ref_slug not in LAYER_SLUGS:
        return None

    ref_path = data_root / ref_slug / ref_filename
    if not ref_path.exists():
        return None

    try:
        fm, _body = read_markdown(ref_path)
    except Exception:
        return None

    return Reference(
        layer_slug=ref_slug,
        filename=ref_filename,
        title=str(fm.get("title", ref_path.stem)),
    )
