"""Gemini client for lightweight agent tasks.

Provides a direct google-genai integration for roles that don't need
Claude CLI tools (MCP file tools).  These roles are pure text-in /
text-out — classification, synthesis, idea generation, idea evaluation,
values seeding, and heartbeat skim/triage (which receive pre-fetched
RSS headlines in the prompt).

Using Gemini Flash for these tasks is ~40x cheaper than Claude and
avoids the Claude CLI requirement entirely.

Two model tiers:
- ``gemini-2.5-flash`` — default for most roles (fast, capable)
- ``gemini-2.5-flash-lite`` — cheapest tier for trivial tasks

API key resolution follows the cc-runner pattern:
1. ``GOOGLE_API_KEY`` environment variable
2. ``GEMINI_API_KEY`` environment variable (copied to ``GOOGLE_API_KEY``)
3. ``.env`` file via ``python-dotenv``
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

# Suppress noisy google-genai SDK logging
logging.getLogger("google.genai").setLevel(logging.ERROR)
logging.getLogger("google.genai.models").setLevel(logging.ERROR)
logging.getLogger("google_genai").setLevel(logging.ERROR)


def _ensure_api_key() -> str | None:
    """Resolve a Google API key from the environment.

    Checks ``GOOGLE_API_KEY`` first, falls back to ``GEMINI_API_KEY``
    (copying it to ``GOOGLE_API_KEY`` for SDK compatibility), and loads
    ``.env`` files via ``python-dotenv`` if available.

    Returns:
        The API key string, or ``None`` if no key is found.
    """
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    google_key = os.environ.get("GOOGLE_API_KEY")
    if google_key:
        return google_key

    gemini_key = os.environ.get("GEMINI_API_KEY")
    if gemini_key:
        os.environ["GOOGLE_API_KEY"] = gemini_key
        logger.info("Copied GEMINI_API_KEY to GOOGLE_API_KEY for SDK compatibility")
        return gemini_key

    return None


def is_gemini_model(model: str | None) -> bool:
    """Check whether a model string refers to a Gemini model.

    Args:
        model: Model identifier string, or ``None``.

    Returns:
        ``True`` if the model starts with ``"gemini-"`` (case-insensitive).
    """
    if model is None:
        return False
    return model.lower().startswith("gemini-")


async def generate(
    prompt: str,
    model: str = "gemini-2.5-flash",
    system_prompt: str | None = None,
) -> str:
    """Call Gemini and return the text response.

    This is a single-shot generation — no tool loop, no session state.
    Runs the blocking ``google-genai`` call in an executor to avoid
    blocking the event loop.

    Args:
        prompt: The user prompt to send.
        model: Gemini model identifier (e.g. ``"gemini-2.5-flash"``).
        system_prompt: Optional system instruction.

    Returns:
        The model's text response.

    Raises:
        RuntimeError: If no API key is found or the API call fails.
    """
    import asyncio

    api_key = _ensure_api_key()
    if not api_key:
        raise RuntimeError(
            "No Google API key found. Set GOOGLE_API_KEY or GEMINI_API_KEY "
            "in the environment or .env file."
        )

    def _call() -> str:
        from google import genai

        client = genai.Client(api_key=api_key)

        # Build config with optional system instruction
        config: dict = {}
        if system_prompt:
            config["system_instruction"] = system_prompt

        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=config if config else None,
        )

        return response.text or ""

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _call)
