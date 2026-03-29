"""Conversation turn runner — orchestrates a single conversation turn.

The conversation runner is the core orchestration module for processing
a single conversation turn. It:

1. Assembles the complete prompt (system prompt, full stack context,
   conversation history, user message)
2. Executes the agent via AgentSession
3. Detects file edits from tool calls
4. Commits changes to git
5. Queues a pending cascade if foundational layers were edited
6. Persists messages to the store

This module bridges the REST API, agent system, event system, and
cascade integration.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from policy_factory.agent.config import AgentConfig, resolve_model
from policy_factory.agent.prompts import build_agent_prompt
from policy_factory.agent.session import AgentSession
from policy_factory.data.git import commit_changes
from policy_factory.data.layers import (
    FOUNDATIONAL_LAYERS,
    LAYERS,
    list_items,
    read_item,
    read_narrative,
)
from policy_factory.events import (
    ConversationCascadePending,
    ConversationFileEdit,
    ConversationStarted,
    ConversationTextChunk,
    ConversationTurnComplete,
    ConversationTurnError,
    EventEmitter,
)
from policy_factory.store import PolicyStore

logger = logging.getLogger(__name__)

# Token limits for context truncation
# We use a rough estimate of 4 characters per token
MAX_PROMPT_TOKENS = 150_000
TARGET_PROMPT_TOKENS = 120_000
CHARS_PER_TOKEN = 4


# ---------------------------------------------------------------------------
# File edit detection
# ---------------------------------------------------------------------------

# Patterns for detecting file edit tool calls in agent output.
# Each tuple: (pattern, flags, case_insensitive_action)
_FILE_EDIT_PATTERNS: list[tuple[str, int, bool]] = [
    # Pattern 1: Tool use XML-style format (common in Claude CLI output)
    # <tool_use name="write_file">{"path": "values/foo.md", "content": "..."}
    (
        r'<tool_use[^>]*name="(write_file|delete_file)"[^>]*>.*?"path"\s*:\s*"([^"]+)"',
        re.DOTALL,
        False,
    ),
    # Pattern 2: MCP tool call format with JSON arguments
    # Tool: write_file
    # Arguments: {"path": "layer/file.md", "content": "..."}
    (
        r'Tool:\s*(write_file|delete_file).*?Arguments:\s*\{[^}]*"path"\s*:\s*"([^"]+)"',
        re.DOTALL | re.IGNORECASE,
        True,
    ),
    # Pattern 3: Function-call style
    # write_file(path="layer/file.md", content="...")
    (
        r'(write_file|delete_file)\s*\(\s*(?:path\s*=\s*)?["\']([^"\']+)["\']',
        re.IGNORECASE,
        True,
    ),
    # Pattern 4: JSON object with tool_name and input
    # {"tool_name": "write_file", "input": {"path": "..."}}
    (
        r'"(?:tool_name|name)"\s*:\s*"(write_file|delete_file)".*?"path"\s*:\s*"([^"]+)"',
        re.DOTALL,
        False,
    ),
]


def _extract_file_edits(full_output: str) -> list[tuple[str, str]]:
    """Extract file edits from agent output.

    Parses the agent's full_output to find write_file and delete_file
    tool calls. Returns a list of (path, action) tuples where action
    is "write" or "delete".

    The format of tool calls in the output depends on the Claude CLI
    format. We look for patterns like:
    - Tool call: write_file with path="layer/file.md"
    - write_file(path="layer/file.md", ...)
    - {"name": "write_file", "arguments": {"path": "..."}}

    Args:
        full_output: The complete output from the agent session.

    Returns:
        List of (file_path, action) tuples.
    """
    edits: list[tuple[str, str]] = []
    seen_paths: set[str] = set()

    for pattern, flags, case_insensitive in _FILE_EDIT_PATTERNS:
        for match in re.finditer(pattern, full_output, flags):
            action_raw, path = match.groups()
            action_cmp = action_raw.lower() if case_insensitive else action_raw
            action = "write" if action_cmp == "write_file" else "delete"
            if path not in seen_paths:
                seen_paths.add(path)
                edits.append((path, action))

    return edits


def _parse_file_path(file_path: str) -> tuple[str, str] | None:
    """Parse a file path into layer_slug and filename.

    Expected format: layer-slug/filename.md

    Args:
        file_path: The file path from a tool call.

    Returns:
        Tuple of (layer_slug, filename) or None if invalid.
    """
    if "/" not in file_path:
        return None

    parts = file_path.split("/", 1)
    if len(parts) != 2:
        return None

    layer_slug, filename = parts
    valid_slugs = {layer.slug for layer in LAYERS}
    if layer_slug not in valid_slugs:
        return None

    return layer_slug, filename


# ---------------------------------------------------------------------------
# Context gathering
# ---------------------------------------------------------------------------


def gather_full_stack_context(data_dir: Path) -> str:
    """Gather content from all layers in the policy stack.

    Reads all 6 layers from bottom (philosophy) to top (policies),
    including the README.md narrative and all item content for each layer.

    Args:
        data_dir: Root data directory.

    Returns:
        A formatted text string containing the full policy stack context.
    """
    parts: list[str] = []

    for layer in LAYERS:
        layer_slug = layer.slug
        layer_display = layer.display_name

        parts.append(f"## {layer_display} Layer\n")

        # Read narrative summary
        narrative = read_narrative(data_dir, layer_slug)
        if narrative:
            parts.append(f"### Narrative Summary\n{narrative}\n")

        # Read all items
        items = list_items(data_dir, layer_slug)
        if items:
            parts.append("### Items\n")
            for item_summary in items:
                try:
                    fm, body = read_item(data_dir, layer_slug, item_summary.filename)
                    title = fm.get("title", item_summary.filename)
                    status = fm.get("status", "")

                    item_header = f"#### {title}"
                    if status:
                        item_header += f" (Status: {status})"
                    item_header += f"\n*File: {layer_slug}/{item_summary.filename}*\n"

                    parts.append(item_header)
                    if body.strip():
                        parts.append(body.strip() + "\n")
                except Exception:
                    logger.warning(
                        "Failed to read item %s/%s for context",
                        layer_slug,
                        item_summary.filename,
                    )
                    continue

    if not parts:
        return "(No content available in the policy stack.)"

    return "\n".join(parts)


def _estimate_tokens(text: str) -> int:
    """Estimate the number of tokens in a text string.

    Uses a rough heuristic of 4 characters per token, which is
    a reasonable approximation for English text with code.

    Args:
        text: The text to estimate.

    Returns:
        Estimated number of tokens.
    """
    return len(text) // CHARS_PER_TOKEN


# ---------------------------------------------------------------------------
# Prompt assembly
# ---------------------------------------------------------------------------


def _build_conversation_prompt(
    system_prompt: str,
    stack_context: str,
    conversation_history: list[dict[str, str]],
    user_message: str,
    item_content: str | None = None,
    layer_summary: str | None = None,
) -> str:
    """Assemble the complete conversation prompt.

    Combines:
    - System prompt (conversation agent instructions)
    - Full policy stack context
    - Conversation history (previous messages)
    - Current user message
    - Optionally, specific item content or layer summary if discussing

    Args:
        system_prompt: The conversation system prompt.
        stack_context: Full policy stack context string.
        conversation_history: List of {role, content} message dicts.
        user_message: The current user message.
        item_content: Optional specific item content being discussed.
        layer_summary: Optional layer summary being discussed.

    Returns:
        The assembled prompt string.
    """
    parts: list[str] = []

    # System prompt first
    parts.append("# System Instructions\n")
    parts.append(system_prompt)
    parts.append("\n")

    # Full stack context
    parts.append("# Policy Stack Context\n")
    parts.append(stack_context)
    parts.append("\n")

    # If discussing a specific item, include it prominently
    if item_content:
        parts.append("# Current Item Being Discussed\n")
        parts.append(item_content)
        parts.append("\n")

    # If discussing a layer, include its summary prominently
    if layer_summary:
        parts.append("# Current Layer Being Discussed\n")
        parts.append(layer_summary)
        parts.append("\n")

    # Conversation history
    if conversation_history:
        parts.append("# Conversation History\n")
        for msg in conversation_history:
            role = msg["role"].capitalize()
            content = msg["content"]
            parts.append(f"**{role}:** {content}\n")
        parts.append("\n")

    # Current user message
    parts.append("# Current Message\n")
    parts.append(f"**User:** {user_message}\n")

    return "\n".join(parts)


def _truncate_history(
    conversation_history: list[dict[str, str]],
    current_prompt_tokens: int,
) -> list[dict[str, str]]:
    """Truncate oldest messages from conversation history.

    When the prompt exceeds MAX_PROMPT_TOKENS, removes the oldest
    messages until the estimated token count is under TARGET_PROMPT_TOKENS.

    Args:
        conversation_history: List of {role, content} message dicts.
        current_prompt_tokens: Current estimated token count.

    Returns:
        Truncated conversation history (may be empty).
    """
    if current_prompt_tokens <= MAX_PROMPT_TOKENS:
        return conversation_history

    excess_tokens = current_prompt_tokens - TARGET_PROMPT_TOKENS
    truncated = list(conversation_history)

    while truncated and excess_tokens > 0:
        # Remove oldest message (first in list)
        oldest = truncated.pop(0)
        removed_tokens = _estimate_tokens(oldest["content"])
        excess_tokens -= removed_tokens
        logger.warning(
            "Truncated message from history (removed ~%d tokens, excess now ~%d)",
            removed_tokens,
            max(0, excess_tokens),
        )

    return truncated


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def run_conversation_turn(
    conversation_id: str,
    user_content: str,
    store: PolicyStore,
    emitter: EventEmitter,
    data_dir: Path,
) -> None:
    """Run a single conversation turn.

    This is the main entry point called by the API layer. It orchestrates:
    1. Storing the user message
    2. Emitting ConversationStarted event
    3. Assembling the prompt with context
    4. Running the agent
    5. Streaming text chunks
    6. Detecting file edits
    7. Committing changes to git
    8. Queueing cascade if needed
    9. Storing the assistant message

    Args:
        conversation_id: Which conversation this turn belongs to.
        user_content: The user's message text.
        store: PolicyStore for message persistence and cascade pending.
        emitter: EventEmitter for streaming events.
        data_dir: The policy data directory for file operations.

    This function is async and returns None — results are streamed via
    events and persisted to the store.
    """
    # Get conversation to determine context (layer/item)
    conversation = store.get_conversation(conversation_id)
    if conversation is None:
        await emitter.emit(
            ConversationTurnError(
                conversation_id=conversation_id,
                error_message=f"Conversation not found: {conversation_id}",
            )
        )
        return

    # Note: User message is already stored by the API endpoint before
    # calling run_conversation_turn. We don't store it here to avoid duplicates.

    # Emit ConversationStarted event
    await emitter.emit(ConversationStarted(conversation_id=conversation_id))

    try:
        # Gather full stack context
        stack_context = gather_full_stack_context(data_dir)

        # Get conversation history (all previous messages)
        messages = store.get_messages(conversation_id)
        # Exclude the current user message (last in list) — it goes in the prompt separately
        history_messages = messages[:-1] if messages else []
        conversation_history = [
            {"role": msg.role, "content": msg.content}
            for msg in history_messages
        ]

        # If discussing a specific item, get its content
        item_content: str | None = None
        if conversation.filename:
            try:
                fm, body = read_item(
                    data_dir, conversation.layer_slug, conversation.filename
                )
                title = fm.get("title", conversation.filename)
                file_ref = f"{conversation.layer_slug}/{conversation.filename}"
                item_content = f"**{title}**\n*File: {file_ref}*\n\n{body}"
            except FileNotFoundError:
                item_content = f"(Item {conversation.filename} not found)"

        # If discussing a layer (not a specific item), get its summary
        layer_summary: str | None = None
        if not conversation.filename:
            narrative = read_narrative(data_dir, conversation.layer_slug)
            if narrative:
                layer_summary = f"**{conversation.layer_slug} Layer Summary**\n\n{narrative}"

        # Load the conversation system prompt
        # Note: The prompt will be created in step 010; for now we provide a fallback
        try:
            system_prompt = build_agent_prompt("conversation", "system")
        except FileNotFoundError:
            logger.warning(
                "Conversation system prompt not found, using fallback"
            )
            system_prompt = _get_fallback_system_prompt()

        # Assemble the full prompt
        full_prompt = _build_conversation_prompt(
            system_prompt=system_prompt,
            stack_context=stack_context,
            conversation_history=conversation_history,
            user_message=user_content,
            item_content=item_content,
            layer_summary=layer_summary,
        )

        # Check token count and truncate if necessary
        prompt_tokens = _estimate_tokens(full_prompt)
        if prompt_tokens > MAX_PROMPT_TOKENS:
            # Check if stack content alone exceeds limits
            stack_tokens = _estimate_tokens(stack_context)
            system_tokens = _estimate_tokens(system_prompt)
            base_tokens = stack_tokens + system_tokens + _estimate_tokens(user_content)

            if base_tokens > TARGET_PROMPT_TOKENS:
                # Fatal error — cannot truncate stack
                error_msg = (
                    f"Policy stack context too large ({base_tokens} estimated tokens). "
                    f"Cannot fit within {TARGET_PROMPT_TOKENS} token limit."
                )
                logger.error(error_msg)
                await emitter.emit(
                    ConversationTurnError(
                        conversation_id=conversation_id,
                        error_message=error_msg,
                    )
                )
                # Store error message
                store.add_message(
                    conversation_id,
                    "assistant",
                    f"[Error: {error_msg}]",
                    files_edited=[],
                )
                return

            # Truncate conversation history
            logger.warning(
                "Prompt exceeds %d tokens (%d estimated), truncating history",
                MAX_PROMPT_TOKENS,
                prompt_tokens,
            )
            conversation_history = _truncate_history(
                conversation_history, prompt_tokens
            )

            # Rebuild prompt with truncated history
            full_prompt = _build_conversation_prompt(
                system_prompt=system_prompt,
                stack_context=stack_context,
                conversation_history=conversation_history,
                user_message=user_content,
                item_content=item_content,
                layer_summary=layer_summary,
            )

        # Resolve model for conversation role
        model = resolve_model("conversation")

        # Create agent config
        config = AgentConfig(
            model=model,
            role="conversation",
        )

        # Create agent session
        # We create a custom emitter wrapper to emit ConversationTextChunk
        # instead of AgentTextChunk
        agent_label = f"Conversation agent [{conversation_id[:8]}]"
        session = AgentSession(
            config=config,
            emitter=_ConversationEmitterWrapper(emitter, conversation_id),
            context_id=conversation_id,
            agent_label=agent_label,
            data_dir=data_dir,
        )

        # Run the agent
        result = await session.run(full_prompt)

        if result.is_error:
            # Agent failed — emit error event but don't commit
            error_msg = result.result_text or "Agent execution failed"
            await emitter.emit(
                ConversationTurnError(
                    conversation_id=conversation_id,
                    error_message=error_msg,
                )
            )
            # Store partial/error message
            store.add_message(
                conversation_id,
                "assistant",
                f"[Error: {error_msg}]",
                files_edited=[],
            )
            return

        # Extract the assistant's response text
        assistant_text = result.result_text

        # Detect file edits from tool calls
        file_edits = _extract_file_edits(result.full_output)

        # Build list of files_edited paths (layer_slug/filename format)
        files_edited: list[str] = []
        foundational_edits: list[str] = []

        for file_path, action in file_edits:
            parsed = _parse_file_path(file_path)
            if parsed:
                layer_slug, filename = parsed
                files_edited.append(f"{layer_slug}/{filename}")

                # Emit file edit event
                await emitter.emit(
                    ConversationFileEdit(
                        conversation_id=conversation_id,
                        layer_slug=layer_slug,
                        filename=filename,
                        action=action,
                    )
                )

                # Track foundational layer edits
                if layer_slug in FOUNDATIONAL_LAYERS:
                    foundational_edits.append(layer_slug)

        # If any files were edited, commit to git
        if files_edited:
            try:
                # Build commit message
                edit_summary = ", ".join(files_edited[:3])
                if len(files_edited) > 3:
                    edit_summary += f" (+{len(files_edited) - 3} more)"
                commit_msg = f"Conversation edit: {edit_summary} [conv {conversation_id[:8]}]"

                commit_changes(data_dir, commit_msg)
                logger.info("Committed conversation changes: %s", commit_msg)
            except Exception as git_exc:
                logger.warning(
                    "Git commit failed after conversation: %s",
                    git_exc,
                )

            # Queue pending cascade if foundational layers were edited
            if foundational_edits:
                # Find the lowest layer (smallest position) among edits
                lowest_layer = min(
                    foundational_edits,
                    key=lambda slug: next(
                        layer.position for layer in LAYERS if layer.slug == slug
                    ),
                )

                pending_entry = store.create_or_update_pending_cascade(
                    conversation_id=conversation_id,
                    starting_layer=lowest_layer,
                )

                # Emit cascade pending event
                await emitter.emit(
                    ConversationCascadePending(
                        conversation_id=conversation_id,
                        starting_layer=pending_entry.starting_layer,
                    )
                )

                logger.info(
                    "Queued pending cascade from %s [conv %s]",
                    pending_entry.starting_layer,
                    conversation_id[:8],
                )

        # Store assistant message with files_edited metadata
        message_id = store.add_message(
            conversation_id,
            "assistant",
            assistant_text,
            files_edited=files_edited if files_edited else None,
        )

        # Emit turn complete event
        await emitter.emit(
            ConversationTurnComplete(
                conversation_id=conversation_id,
                message_id=message_id,
                files_edited=files_edited,
            )
        )

    except Exception as exc:
        # Handle unexpected errors
        error_msg = str(exc)
        logger.exception(
            "Conversation turn failed [conv %s]: %s",
            conversation_id[:8],
            error_msg,
        )

        await emitter.emit(
            ConversationTurnError(
                conversation_id=conversation_id,
                error_message=error_msg,
            )
        )

        # Store error message (don't commit any partial file changes)
        store.add_message(
            conversation_id,
            "assistant",
            f"[Error: {error_msg}]",
            files_edited=[],
        )


# ---------------------------------------------------------------------------
# Helper classes
# ---------------------------------------------------------------------------


class _ConversationEmitterWrapper:
    """Wrapper that translates AgentTextChunk to ConversationTextChunk.

    The AgentSession emits AgentTextChunk events, but we want
    ConversationTextChunk events for the conversation runner.
    This wrapper intercepts emit calls and translates them.
    """

    def __init__(self, emitter: EventEmitter, conversation_id: str) -> None:
        self._emitter = emitter
        self._conversation_id = conversation_id

    async def emit(self, event: object) -> None:
        """Emit an event, translating AgentTextChunk to ConversationTextChunk."""
        from policy_factory.events import AgentTextChunk

        if isinstance(event, AgentTextChunk):
            # Translate to conversation event
            await self._emitter.emit(
                ConversationTextChunk(
                    conversation_id=self._conversation_id,
                    text=event.text,
                )
            )
        else:
            # Pass through other events
            await self._emitter.emit(event)  # type: ignore[arg-type]


def _get_fallback_system_prompt() -> str:
    """Return a minimal fallback system prompt.

    Used when the conversation system prompt file hasn't been
    created yet (step 010).
    """
    return """You are an AI policy advisor helping to discuss and refine policy content.

You have access to tools to read and modify policy files:
- list_files: List markdown files in a directory
- read_file: Read file content
- write_file: Create or update a file
- delete_file: Remove a file

When modifying policy content:
- Maintain YAML frontmatter structure
- Preserve references to other layers
- Update last_modified metadata

Be direct, substantive, and avoid filler phrases. Push back when you have
strong logical or evidence basis for your position.
"""
