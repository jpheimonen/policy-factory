"""Layer content gathering utilities for critic and synthesis prompts.

Provides helpers to assemble the full content of a layer (narrative
summary + all items) as a single formatted text blob suitable for
substitution into prompt templates as ``{layer_content}``.

This is used by the cascade orchestrator before calling the critic
runner, so the content is gathered once and passed to both the critic
runner and synthesis runner.
"""

from __future__ import annotations

import logging
from pathlib import Path

from policy_factory.data.layers import list_items, read_item, read_narrative

logger = logging.getLogger(__name__)


def gather_layer_content(data_dir: Path, layer_slug: str) -> str:
    """Gather the full content of a layer as formatted text.

    Reads the layer's narrative summary (README.md) and all items
    with their frontmatter and markdown body, assembling them into
    a single text string suitable for prompt template substitution.

    Args:
        data_dir: Root data directory.
        layer_slug: The layer slug to gather content from.

    Returns:
        A formatted text string containing the narrative summary
        followed by each item with its title and content.
    """
    parts: list[str] = []

    # Narrative summary first
    narrative = read_narrative(data_dir, layer_slug)
    if narrative:
        parts.append(f"## Narrative Summary\n\n{narrative}")

    # All items in the layer
    items = list_items(data_dir, layer_slug)
    if items:
        parts.append("## Items\n")
        for item_summary in items:
            try:
                fm, body = read_item(data_dir, layer_slug, item_summary.filename)
                title = fm.get("title", item_summary.filename)
                status = fm.get("status", "")

                item_header = f"### {title}"
                if status:
                    item_header += f" (Status: {status})"

                item_parts = [item_header]
                if body.strip():
                    item_parts.append(body.strip())

                parts.append("\n".join(item_parts))
            except Exception:
                logger.warning(
                    "Failed to read item %s/%s for content gathering",
                    layer_slug,
                    item_summary.filename,
                )
                continue

    if not parts:
        return f"(No content available for the {layer_slug} layer.)"

    return "\n\n".join(parts)


def gather_cross_layer_context(
    data_dir: Path,
    layer_slug: str,
) -> str:
    """Gather content from adjacent layers for cross-layer context.

    Provides a brief summary of the layers immediately above and below
    the target layer, so critics have context about how the layer
    fits into the broader policy stack.

    Args:
        data_dir: Root data directory.
        layer_slug: The target layer slug.

    Returns:
        A formatted text string with brief summaries of adjacent layers.
    """
    from policy_factory.data.layers import LAYERS

    layer_order = [layer.slug for layer in LAYERS]
    if layer_slug not in layer_order:
        return "(No cross-layer context available.)"

    idx = layer_order.index(layer_slug)
    parts: list[str] = []

    # Layer below
    if idx > 0:
        below_slug = layer_order[idx - 1]
        below_display = below_slug.replace("-", " ").title()
        below_narrative = read_narrative(data_dir, below_slug)
        if below_narrative:
            # Truncate to first few lines for brevity
            preview = "\n".join(below_narrative.split("\n")[:10])
            parts.append(f"### Layer Below: {below_display}\n\n{preview}")
        else:
            parts.append(f"### Layer Below: {below_display}\n\n(No narrative summary.)")

    # Layer above
    if idx < len(layer_order) - 1:
        above_slug = layer_order[idx + 1]
        above_display = above_slug.replace("-", " ").title()
        above_narrative = read_narrative(data_dir, above_slug)
        if above_narrative:
            preview = "\n".join(above_narrative.split("\n")[:10])
            parts.append(f"### Layer Above: {above_display}\n\n{preview}")
        else:
            parts.append(f"### Layer Above: {above_display}\n\n(No narrative summary.)")

    if not parts:
        return "(This layer has no adjacent layers.)"

    return "\n\n".join(parts)
