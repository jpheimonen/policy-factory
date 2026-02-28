"""Idea pipeline — evaluation, generation, and stack summary utilities.

Public API:
- ``evaluate_idea`` — Run the full evaluation pipeline for a single idea.
- ``generate_ideas`` — AI-generate new policy ideas.
- ``gather_stack_summary`` — Gather brief summaries of all 5 layers.
"""

from .evaluator import evaluate_idea
from .generator import generate_ideas
from .helpers import gather_stack_summary

__all__ = [
    "evaluate_idea",
    "gather_stack_summary",
    "generate_ideas",
]
