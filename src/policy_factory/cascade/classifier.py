"""Input classifier — determines which layer free-text user input affects.

The classifier is a lightweight AI agent that receives the user's input
text and brief descriptions of each layer, then returns the target layer
with an explanation. Classification completes synchronously within the
API request (it's a fast, lightweight agent call).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from policy_factory.data.layers import LAYER_SLUGS, LAYERS, list_items, read_narrative
from policy_factory.events import EventEmitter
from policy_factory.store import PolicyStore

logger = logging.getLogger(__name__)

# Default fallback layer when classification fails
_FALLBACK_LAYER = "situational-awareness"


@dataclass
class ClassificationResult:
    """Result of classifying user input to a target layer."""

    target_layer: str
    secondary_layers: list[str]
    confidence: str  # high, medium, low
    explanation: str


def _build_layer_summaries(data_dir: Path) -> str:
    """Build brief descriptions of each layer for the classifier prompt.

    Includes display name, item count, and a snippet of the narrative
    summary.
    """
    parts: list[str] = []

    for layer in LAYERS:
        items = list_items(data_dir, layer.slug)
        narrative = read_narrative(data_dir, layer.slug)
        narrative_snippet = narrative[:150].strip() if narrative else "(empty)"
        if len(narrative) > 150:
            narrative_snippet += "..."

        parts.append(
            f"- **{layer.display_name}** (`{layer.slug}`) — "
            f"{len(items)} items. Summary: {narrative_snippet}"
        )

    return "\n".join(parts)


def _parse_classification_output(output: str) -> ClassificationResult:
    """Parse the structured classification result from the agent output.

    Expects the format:
        PRIMARY_LAYER: <slug>
        SECONDARY_LAYERS: <comma-separated slugs or "none">
        CONFIDENCE: <high/medium/low>
        EXPLANATION: <text>

    Falls back to situational-awareness if parsing fails.
    """
    target_layer = _FALLBACK_LAYER
    secondary_layers: list[str] = []
    confidence = "medium"
    explanation = "Classification could not be parsed; defaulting to situational-awareness."

    # Extract PRIMARY_LAYER
    primary_match = re.search(
        r"PRIMARY_LAYER:\s*(.+?)(?:\n|$)", output, re.IGNORECASE
    )
    if primary_match:
        raw = primary_match.group(1).strip().strip("`").strip()
        # Validate against known slugs
        if raw in LAYER_SLUGS:
            target_layer = raw
        else:
            logger.warning(
                "Classifier returned invalid layer slug %r, falling back to %s",
                raw,
                _FALLBACK_LAYER,
            )

    # Extract SECONDARY_LAYERS
    secondary_match = re.search(
        r"SECONDARY_LAYERS:\s*(.+?)(?:\n|$)", output, re.IGNORECASE
    )
    if secondary_match:
        raw_sec = secondary_match.group(1).strip()
        if raw_sec.lower() != "none":
            for slug in raw_sec.split(","):
                slug = slug.strip().strip("`").strip()
                if slug in LAYER_SLUGS and slug != target_layer:
                    secondary_layers.append(slug)

    # Extract CONFIDENCE
    confidence_match = re.search(
        r"CONFIDENCE:\s*(.+?)(?:\n|$)", output, re.IGNORECASE
    )
    if confidence_match:
        raw_conf = confidence_match.group(1).strip().lower()
        if raw_conf in ("high", "medium", "low"):
            confidence = raw_conf

    # Extract EXPLANATION
    explanation_match = re.search(
        r"EXPLANATION:\s*(.+?)(?:\n\n|$)", output, re.IGNORECASE | re.DOTALL
    )
    if explanation_match:
        explanation = explanation_match.group(1).strip()

    return ClassificationResult(
        target_layer=target_layer,
        secondary_layers=secondary_layers,
        confidence=confidence,
        explanation=explanation,
    )


async def classify_input(
    user_input: str,
    store: PolicyStore,
    emitter: EventEmitter,
    data_dir: Path,
    cascade_id: str | None = None,
) -> ClassificationResult:
    """Classify user input to determine which layer it affects.

    Runs the classifier agent synchronously (awaited), records the
    agent run in the database, and returns the classification result.

    Args:
        user_input: The user's free-text input.
        store: PolicyStore for recording agent runs.
        emitter: EventEmitter for streaming.
        data_dir: Root data directory.
        cascade_id: Optional cascade ID for attribution.

    Returns:
        A ClassificationResult with the target layer and explanation.
    """
    from policy_factory.agent.config import AgentConfig, resolve_model
    from policy_factory.agent.prompts import build_agent_prompt
    from policy_factory.agent.session import AgentSession

    # Build layer summaries for the prompt
    layer_summaries = _build_layer_summaries(data_dir)

    # Resolve classifier model
    model = resolve_model("classifier")

    # Build the classifier prompt
    prompt = build_agent_prompt(
        "classifier",
        "classifier",
        layer_summaries=layer_summaries,
        user_input=user_input,
    )

    # Create agent config
    config = AgentConfig(
        model=model,
        role="classifier",
    )

    # Record agent run start
    agent_label = "Input classifier"
    agent_run_id = store.create_agent_run(
        cascade_id=cascade_id,
        agent_type="classifier",
        agent_label=agent_label,
        model=model,
        target_layer=None,
    )

    # Create and run the session
    session = AgentSession(
        config=config,
        emitter=emitter,
        context_id=cascade_id or "",
        agent_label=agent_label,
        data_dir=data_dir,
    )

    try:
        result = await session.run(prompt)

        # Parse the classification from agent output
        classification = _parse_classification_output(result.full_output)

        store.complete_agent_run(
            agent_run_id,
            success=True,
            cost=result.total_cost_usd,
            output_text=result.full_output,
        )

        return classification

    except Exception as exc:
        store.complete_agent_run(
            agent_run_id,
            success=False,
            error_message=str(exc),
        )
        # On failure, return a safe default
        logger.error("Classifier agent failed: %s", exc)
        return ClassificationResult(
            target_layer=_FALLBACK_LAYER,
            secondary_layers=[],
            confidence="low",
            explanation=f"Classification failed ({exc}); defaulting to situational-awareness.",
        )
