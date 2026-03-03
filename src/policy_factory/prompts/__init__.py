"""Prompt loading and management for Policy Factory.

Usage::

    from policy_factory.prompts import PromptLoader, load_prompt

    # Using the class directly
    loader = PromptLoader()
    prompt = loader.load("generators", "values")

    # Using convenience functions
    prompt = load_prompt("generators", "values", layer_slug="values")

    # Loading sections
    meditation = load_section("meditation")
    combined = load_sections(["meditation", "other_section"])
"""

from policy_factory.prompts.loader import (
    PromptLoader,
    get_prompt_loader,
    load_prompt,
    load_section,
    load_sections,
)

__all__ = [
    "PromptLoader",
    "get_prompt_loader",
    "load_prompt",
    "load_section",
    "load_sections",
]
