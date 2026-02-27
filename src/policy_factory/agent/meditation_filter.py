"""Meditation content filter for streamed agent output.

The meditation preamble instructs the AI to count down from 10 to 1,
reflecting on biases at each step.  This filter detects the countdown
in the streamed output and suppresses meditation content from the
WebSocket broadcast.  Users see only post-meditation analysis.

The full unfiltered output — including meditation — is always captured
separately for logging and auditability.
"""

from __future__ import annotations

import re


class MeditationFilter:
    """Stateful filter that detects and suppresses meditation countdown content.

    Usage::

        filt = MeditationFilter()
        for chunk in streamed_chunks:
            should_stream = filt.process(chunk)
            if should_stream:
                emit_to_clients(chunk)

    The filter transitions through three states:

    1. **detecting** — waiting to see if the output starts with a
       meditation countdown (number "10" near the beginning).
    2. **meditating** — inside the countdown section; chunks are
       suppressed.
    3. **streaming** — past the countdown; all chunks are allowed.

    If no countdown pattern is detected in the first chunk(s) of text
    (conservative threshold), the filter assumes no meditation is
    present and streams everything.
    """

    # Detection: look for "10" near the start as a standalone number
    # followed by period/colon/paren/dash
    _START_PATTERN = re.compile(
        r"(?:^|\n)\s*10\s*[\.\:\)\-]"
    )

    # The countdown ends when "1" appears as a standalone number
    # NOT preceded by another digit (so "10", "11" don't match)
    # and followed by period/colon/paren/dash
    _END_PATTERN = re.compile(
        r"(?:^|\n)\s*(?<!\d)1\s*[\.\:\)\-]"
    )

    def __init__(self) -> None:
        self._state: str = "detecting"  # detecting | meditating | streaming
        self._buffer: str = ""
        self._detection_threshold: int = 500  # chars to accumulate before giving up
        self._found_end: bool = False  # True after the "1" marker is found

    @property
    def state(self) -> str:
        """Current filter state: ``"detecting"``, ``"meditating"``, or ``"streaming"``."""
        return self._state

    def process(self, chunk: str) -> bool:
        """Process a text chunk and decide whether to stream it.

        Args:
            chunk: A text chunk from the agent's streamed output.

        Returns:
            ``True`` if the chunk should be broadcast to clients,
            ``False`` if it should be suppressed (meditation content).
        """
        if self._state == "streaming":
            return True

        if self._state == "meditating":
            self._buffer += chunk

            if self._found_end:
                # We already found the "1" marker — look for the next
                # newline to mark the transition to streaming
                # (the line containing "1" is still meditation)
                self._state = "streaming"
                return True

            # Look for the end of meditation (countdown reaching 1)
            # We need "1" that is NOT part of "10", "11", etc.
            if self._END_PATTERN.search(self._buffer):
                # Find the last occurrence of the end pattern
                match = None
                for match in self._END_PATTERN.finditer(self._buffer):
                    pass

                if match:
                    end_pos = match.end()
                    remaining = self._buffer[end_pos:]
                    # If there's text after the "1" marker on a new line,
                    # transition to streaming
                    newline_pos = remaining.find("\n")
                    if newline_pos >= 0:
                        self._state = "streaming"
                        return False  # This chunk still contains meditation
                    else:
                        # "1" found but no newline after it yet —
                        # mark that we found the end, transition on next chunk
                        self._found_end = True
                        return False

            return False

        # State: detecting
        self._buffer += chunk

        # Check if meditation pattern is present
        if self._START_PATTERN.search(self._buffer):
            self._state = "meditating"
            return False

        # If we've accumulated enough text without seeing "10", assume
        # no meditation is present and stream everything
        if len(self._buffer) >= self._detection_threshold:
            self._state = "streaming"
            return True

        # Still detecting — don't stream yet (might be meditation)
        return False

    def reset(self) -> None:
        """Reset the filter to its initial state."""
        self._state = "detecting"
        self._buffer = ""
        self._found_end = False
