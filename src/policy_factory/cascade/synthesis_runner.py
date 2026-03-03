"""Synthesis runner — integrates all critic assessments into a unified assessment.

Matches the ``SynthesisRunnerFn`` protocol defined in the orchestrator.
The synthesis agent receives all successful critic outputs and produces
a balanced assessment that explicitly identifies unresolved tensions.

The synthesis runs even with partial critic results (e.g. 4 out of 6).
It only does NOT run when zero critics succeeded.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from policy_factory.events import (
    EventEmitter,
    SynthesisCompleted,
    SynthesisStarted,
)
from policy_factory.store import PolicyStore

from .critic_runner import CriticRunnerResult
from .critics import get_archetype

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class SynthesisRunnerResult:
    """Result from the synthesis agent."""

    success: bool
    synthesis_text: str = ""
    structured_synthesis: dict[str, Any] | None = None
    agent_run_id: str | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Synthesis output parsing
# ---------------------------------------------------------------------------


# Maps section header regex patterns to output field names.
_SYNTHESIS_SECTION_PATTERNS: list[tuple[str, str]] = [
    (r"Areas?\s+of\s+Consensus", "consensus_points"),
    (r"Key\s+Tensions?", "tension_points"),
    (r"Strongest\s+Criticisms?", "strongest_criticisms"),
    (r"Recommended\s+Refinements?", "recommendations"),
]


def parse_synthesis_output(text: str) -> dict[str, Any] | None:
    """Attempt to parse structured synthesis from agent output.

    Extracts consensus points, tension points, and recommendations
    from the synthesis output if the agent followed the expected format.

    Returns ``None`` if no structure can be extracted.
    """
    if not text or not text.strip():
        return None

    structured: dict[str, Any] = {}

    # Extract named sections
    for header_pattern, field_name in _SYNTHESIS_SECTION_PATTERNS:
        match = re.search(
            rf'###\s+{header_pattern}\s*\n(.*?)(?=###|\Z)',
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if match:
            structured[field_name] = match.group(1).strip()

    # Extract overall score
    score_match = re.search(
        r'###\s+Overall\s+Score:\s*(\d+)/10',
        text,
        re.IGNORECASE,
    )
    if score_match:
        structured["overall_score"] = int(score_match.group(1))

    return structured if structured else None


# ---------------------------------------------------------------------------
# Critic output assembly for the synthesis prompt
# ---------------------------------------------------------------------------


def _assemble_critic_outputs(
    critic_results: CriticRunnerResult,
) -> dict[str, str]:
    """Assemble critic outputs into template variables for the synthesis prompt.

    Returns a dict with keys matching the synthesis template variables:
    ``realist_assessment``, ``liberal_assessment``, etc.

    For failed critics, the value notes the absence.
    """
    # Map archetype slugs to synthesis template variable names
    slug_to_var = {
        "realist": "realist_assessment",
        "liberal-institutionalist": "liberal_assessment",
        "nationalist-conservative": "nationalist_assessment",
        "social-democratic": "social_democratic_assessment",
        "libertarian": "libertarian_assessment",
        "green-ecological": "green_assessment",
    }

    outputs: dict[str, str] = {}

    for slug, var_name in slug_to_var.items():
        result = critic_results.get_result_by_archetype(slug)
        archetype = get_archetype(slug)
        display_name = archetype.display_name if archetype else slug

        if result and result.success and result.assessment_text:
            outputs[var_name] = result.assessment_text
        else:
            error_detail = ""
            if result and result.error:
                error_detail = f" Error: {result.error}"
            outputs[var_name] = (
                f"(The {display_name} critic's assessment is not available "
                f"due to an error.{error_detail})"
            )

    return outputs


# ---------------------------------------------------------------------------
# Public API — run synthesis
# ---------------------------------------------------------------------------


def _reconstruct_critic_results_from_store(
    store: PolicyStore,
    cascade_id: str,
    layer_slug: str,
) -> CriticRunnerResult | None:
    """Reconstruct a ``CriticRunnerResult`` from persisted critic records.

    Used when the orchestrator passes ``None`` for critic_results and
    we need to fetch them from the database.

    Returns:
        A ``CriticRunnerResult``, or ``None`` if no stored results exist.
    """
    from .critic_runner import CriticRunnerResult as CriticRunnerRes
    from .critic_runner import SingleCriticResult

    stored = store.get_critic_results(cascade_id, layer_slug)
    if not stored:
        return None

    results_list = [
        SingleCriticResult(
            archetype=cr.archetype,
            success=cr.is_success,
            assessment_text=cr.assessment_text,
            structured_assessment=cr.structured_assessment,
            agent_run_id=cr.agent_run_id,
        )
        for cr in stored
    ]
    return CriticRunnerRes(
        results=results_list,
        successful_count=sum(1 for r in results_list if r.success),
        failed_count=sum(1 for r in results_list if not r.success),
    )


async def _finalize_synthesis_result(
    *,
    cascade_id: str,
    layer_slug: str,
    idea_id: str | None,
    agent_run_id: str,
    store: PolicyStore,
    emitter: EventEmitter,
    success: bool,
    synthesis_text: str = "",
    structured_synthesis: dict[str, Any] | None = None,
    error: str | None = None,
) -> SynthesisRunnerResult:
    """Store synthesis result, emit completion event, and build the return value.

    Shared epilogue for the three exit paths in ``run_synthesis``
    (success, agent error, exception).
    """
    store.store_synthesis_result(
        cascade_id=cascade_id or None,
        layer_slug=layer_slug or None,
        idea_id=idea_id,
        synthesis_text=synthesis_text,
        structured_synthesis=structured_synthesis,
        agent_run_id=agent_run_id,
    )

    await emitter.emit(
        SynthesisCompleted(
            cascade_id=cascade_id or "",
            layer_slug=layer_slug,
        )
    )

    return SynthesisRunnerResult(
        success=success,
        synthesis_text=synthesis_text,
        structured_synthesis=structured_synthesis,
        agent_run_id=agent_run_id,
        error=error,
    )


async def run_synthesis(
    layer_slug: str,
    critic_results: CriticRunnerResult | Any,
    cascade_id: str,
    store: PolicyStore,
    emitter: EventEmitter,
    data_dir: Path,
    *,
    layer_content: str | None = None,
    idea_id: str | None = None,
) -> SynthesisRunnerResult:
    """Run the synthesis agent to integrate critic assessments.

    This matches the ``SynthesisRunnerFn`` protocol from the orchestrator.

    The synthesis runs even with partial critic results. It only skips
    if zero critics succeeded (nothing to synthesise).

    Args:
        layer_slug: Layer being assessed.
        critic_results: The CriticRunnerResult from run_critics().
            Can also be None (passed from orchestrator in step 015).
        cascade_id: Cascade run ID (may be empty for idea evaluations).
        store: The PolicyStore for persistence.
        emitter: EventEmitter for broadcasting events.
        data_dir: Root data directory.
        layer_content: Pre-gathered layer content. If None, gathered
            automatically.
        idea_id: Idea ID (None for cascade critiques).

    Returns:
        A SynthesisRunnerResult with the synthesis text and metadata.
    """
    from policy_factory.agent.config import AgentConfig, resolve_model
    from policy_factory.agent.prompts import build_agent_prompt
    from policy_factory.agent.session import AgentSession

    from .content import gather_layer_content

    # If critic_results is None, reconstruct from the database
    if critic_results is None:
        if cascade_id:
            critic_results = _reconstruct_critic_results_from_store(
                store, cascade_id, layer_slug
            )
        if critic_results is None:
            return SynthesisRunnerResult(
                success=False,
                error="No critic results available for synthesis",
            )

    # Validate type
    if not isinstance(critic_results, CriticRunnerResult):
        return SynthesisRunnerResult(
            success=False,
            error="Invalid critic results type",
        )

    if not critic_results.overall_success:
        logger.warning(
            "Skipping synthesis for %s — zero critics succeeded",
            layer_slug,
        )
        return SynthesisRunnerResult(
            success=False,
            error="No successful critic results to synthesise",
        )

    # Emit start event
    await emitter.emit(
        SynthesisStarted(
            cascade_id=cascade_id or "",
            layer_slug=layer_slug,
        )
    )

    # Gather content if not provided
    if layer_content is None:
        layer_content = gather_layer_content(data_dir, layer_slug)

    # Resolve model for synthesis role
    model = resolve_model("synthesis")

    # Record agent run start
    agent_run_id = store.create_agent_run(
        cascade_id=cascade_id or None,
        agent_type="synthesis",
        agent_label="Synthesis",
        model=model,
        target_layer=layer_slug or None,
    )

    # Shared keyword args for the finalize helper
    finalize_kwargs: dict[str, Any] = dict(
        cascade_id=cascade_id,
        layer_slug=layer_slug,
        idea_id=idea_id,
        agent_run_id=agent_run_id,
        store=store,
        emitter=emitter,
    )

    try:
        # Assemble critic outputs for the prompt
        critic_vars = _assemble_critic_outputs(critic_results)

        # Build the synthesis prompt
        prompt = build_agent_prompt(
            "synthesis",
            "synthesis",
            layer_slug=layer_slug,
            layer_content=layer_content,
            **critic_vars,
        )

        # Create and run the session
        config = AgentConfig(model=model, role="synthesis")
        session = AgentSession(
            config=config,
            emitter=emitter,
            context_id=cascade_id or "",
            agent_label="Synthesis",
            data_dir=data_dir,
        )

        result = await session.run(prompt)

        # Record agent completion
        store.complete_agent_run(
            agent_run_id,
            success=not result.is_error,
            error_message=result.result_text if result.is_error else None,
            cost=result.total_cost_usd,
            output_text=result.full_output,
        )

        if result.is_error:
            return await _finalize_synthesis_result(
                **finalize_kwargs,
                success=False,
                error=result.result_text,
            )

        # Parse synthesis from successful output
        synthesis_text = result.full_output or result.result_text or ""
        structured = parse_synthesis_output(synthesis_text)

        return await _finalize_synthesis_result(
            **finalize_kwargs,
            success=True,
            synthesis_text=synthesis_text,
            structured_synthesis=structured,
        )

    except Exception as exc:
        error_msg = str(exc)
        logger.error(
            "Synthesis failed for %s: %s",
            layer_slug,
            error_msg,
        )

        store.complete_agent_run(
            agent_run_id,
            success=False,
            error_message=error_msg,
        )

        return await _finalize_synthesis_result(
            **finalize_kwargs,
            success=False,
            error=error_msg,
        )
