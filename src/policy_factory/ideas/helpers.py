"""Stack summary helper and score parsing utilities for the idea pipeline.

Provides:
- ``gather_stack_summary`` — Assembles brief summaries of all 6 layers
  for use in evaluation and generation prompts.
- ``parse_evaluation_scores`` — Extracts 6-axis numeric scores from the
  evaluation agent's output text.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from policy_factory.data.layers import LAYERS, list_items, read_narrative

logger = logging.getLogger(__name__)

# Maps layer slugs to template variable names used in prompts.
_SLUG_TO_VAR: dict[str, str] = {
    "philosophy": "philosophy_summary",
    "values": "values_summary",
    "situational-awareness": "sa_summary",
    "strategic-objectives": "strategic_summary",
    "tactical-objectives": "tactical_summary",
    "policies": "policies_summary",
}


def gather_stack_summary(data_dir: Path) -> dict[str, str]:
    """Gather brief summaries of all 6 layers.

    For each layer in hierarchical order (philosophy to policies):
    - Reads the narrative summary (README.md).
    - Reads item titles from the layer (not full content).
    - Assembles a brief per-layer summary.

    Returns a dict mapping template variable names to summary text::

        {
            "philosophy_summary": "...",
            "values_summary": "...",
            "sa_summary": "...",
            "strategic_summary": "...",
            "tactical_summary": "...",
            "policies_summary": "...",
        }

    Args:
        data_dir: Root data directory.

    Returns:
        Dict of template variable name → summary text.
    """
    summaries: dict[str, str] = {}

    for layer in LAYERS:
        var_name = _SLUG_TO_VAR.get(layer.slug, layer.slug)
        parts: list[str] = []

        # Narrative summary
        try:
            narrative = read_narrative(data_dir, layer.slug)
            if narrative:
                # Truncate to first 20 lines for brevity
                preview_lines = narrative.strip().split("\n")[:20]
                parts.append("\n".join(preview_lines))
        except Exception:
            logger.warning("Failed to read narrative for %s", layer.slug)

        # Item titles
        try:
            items = list_items(data_dir, layer.slug)
            if items:
                titles = [f"- {item.title}" for item in items]
                parts.append("**Items:**\n" + "\n".join(titles))
        except Exception:
            logger.warning("Failed to list items for %s", layer.slug)

        if parts:
            summaries[var_name] = "\n\n".join(parts)
        else:
            summaries[var_name] = f"(No content available for the {layer.display_name} layer.)"

    return summaries


def gather_stack_summary_text(data_dir: Path) -> str:
    """Gather all 6 layer summaries as a single formatted text block.

    Convenience wrapper around ``gather_stack_summary`` that combines
    all summaries into one text string.

    Args:
        data_dir: Root data directory.

    Returns:
        A single formatted text block with all layer summaries.
    """
    summaries = gather_stack_summary(data_dir)
    parts: list[str] = []

    for layer in LAYERS:
        var_name = _SLUG_TO_VAR.get(layer.slug, layer.slug)
        summary = summaries.get(var_name, "(No content.)")
        parts.append(f"## {layer.display_name}\n\n{summary}")

    return "\n\n---\n\n".join(parts)


# ---------------------------------------------------------------------------
# Score parsing
# ---------------------------------------------------------------------------

# The 6 axes as defined in the evaluation prompt template.
# Note: the evaluation prompt uses different axis names than the spec's
# "strategic fit, feasibility, cost, risk, public acceptance, international impact".
# We map the prompt's axes to the spec's axes.
_SCORE_PATTERNS: list[tuple[str, str]] = [
    # (regex pattern matching label, target field name)
    (r"Feasibility", "feasibility"),
    (r"Alignment\s+with\s+values", "strategic_fit"),
    (r"Political\s+viability", "public_acceptance"),
    (r"Evidence\s+basis", "cost"),
    (r"Implementation\s+complexity", "risk"),
    (r"Innovation", "international_impact"),
]


def parse_evaluation_scores(text: str) -> dict[str, float] | None:
    """Extract 6-axis numeric scores from the evaluation agent's output.

    Looks for lines like ``- Feasibility: 7/10`` in the output.

    Args:
        text: The raw evaluation agent output.

    Returns:
        A dict with keys matching the score axes
        (``strategic_fit``, ``feasibility``, ``cost``, ``risk``,
        ``public_acceptance``, ``international_impact``), each a float.
        Returns ``None`` if fewer than 3 scores could be extracted
        (likely the AI didn't follow the format).
    """
    if not text or not text.strip():
        return None

    scores: dict[str, float] = {}

    for pattern, field_name in _SCORE_PATTERNS:
        match = re.search(
            rf'-\s*\*?\*?{pattern}\*?\*?\s*:\s*(\d+(?:\.\d+)?)\s*/\s*10',
            text,
            re.IGNORECASE,
        )
        if match:
            try:
                scores[field_name] = float(match.group(1))
            except (ValueError, IndexError):
                continue

    # Require at least 3 scores to consider parsing successful
    if len(scores) < 3:
        return None

    # Fill in missing scores with 5.0 (neutral default)
    all_fields = [
        "strategic_fit",
        "feasibility",
        "cost",
        "risk",
        "public_acceptance",
        "international_impact",
    ]
    for field in all_fields:
        if field not in scores:
            scores[field] = 5.0
            logger.warning("Missing score for %s, defaulting to 5.0", field)

    return scores


def get_default_scores() -> dict[str, float]:
    """Return default scores (all zeros) for when parsing fails.

    Returns:
        A dict with all 6 axes set to 0.0.
    """
    return {
        "strategic_fit": 0.0,
        "feasibility": 0.0,
        "cost": 0.0,
        "risk": 0.0,
        "public_acceptance": 0.0,
        "international_impact": 0.0,
    }


def parse_generated_ideas(text: str) -> list[dict[str, Any]]:
    """Parse the generation agent's output into individual ideas.

    Looks for ``## Idea: <title>`` headers followed by a ``**Summary**: ...``
    block. Each matched section becomes one idea.

    Args:
        text: The raw generation agent output.

    Returns:
        A list of dicts, each with ``"title"`` and ``"text"`` keys.
        Returns an empty list if no ideas could be parsed.
    """
    if not text or not text.strip():
        return []

    # Split by "## Idea:" headers
    idea_pattern = re.compile(
        r'##\s+Idea:\s*(.+?)(?=\n)',
        re.IGNORECASE,
    )

    # Find all idea sections
    sections = idea_pattern.split(text)

    ideas: list[dict[str, Any]] = []

    # sections[0] is preamble, then alternating: title, content, title, content
    if len(sections) >= 3:
        for i in range(1, len(sections), 2):
            title = sections[i].strip()
            content = sections[i + 1] if i + 1 < len(sections) else ""

            # Extract summary
            summary_match = re.search(
                r'\*\*Summary\*\*\s*:\s*(.+?)(?=\*\*|##|$)',
                content,
                re.IGNORECASE | re.DOTALL,
            )
            if summary_match:
                summary_text = summary_match.group(1).strip()
            else:
                # Use the full content block as the idea text
                summary_text = content.strip()

            if title and summary_text:
                ideas.append({
                    "title": title,
                    "text": f"{title}: {summary_text}",
                })

    # Fallback: if we didn't get structured ideas, try splitting by numbered items
    if not ideas:
        numbered_pattern = re.compile(
            r'\n\d+\.\s+\*\*(.+?)\*\*\s*[-:]\s*(.+?)(?=\n\d+\.|\Z)',
            re.DOTALL,
        )
        for match in numbered_pattern.finditer(text):
            title = match.group(1).strip()
            body = match.group(2).strip()
            if title and body:
                ideas.append({
                    "title": title,
                    "text": f"{title}: {body}",
                })

    return ideas
