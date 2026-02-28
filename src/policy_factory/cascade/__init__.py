"""Cascade orchestrator package.

Public API for triggering and controlling cascades, running critics,
and synthesising critic assessments.
"""

from .content import gather_cross_layer_context, gather_layer_content
from .controller import CascadeController, CascadeState
from .critic_runner import CriticRunnerResult, SingleCriticResult, run_critics
from .critics import (
    CRITIC_ARCHETYPES,
    CriticArchetype,
    get_all_archetypes,
    get_archetype,
    get_archetype_slugs,
)
from .orchestrator import (
    layers_below,
    layers_from,
    trigger_cascade,
)
from .synthesis_runner import SynthesisRunnerResult, run_synthesis

__all__ = [
    "CRITIC_ARCHETYPES",
    "CascadeController",
    "CascadeState",
    "CriticArchetype",
    "CriticRunnerResult",
    "SingleCriticResult",
    "SynthesisRunnerResult",
    "gather_cross_layer_context",
    "gather_layer_content",
    "get_all_archetypes",
    "get_archetype",
    "get_archetype_slugs",
    "layers_below",
    "layers_from",
    "run_critics",
    "run_synthesis",
    "trigger_cascade",
]
