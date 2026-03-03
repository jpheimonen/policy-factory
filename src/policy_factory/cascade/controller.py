"""Cascade controller with strict state machine for pause/resume/cancel.

Adapted from cc-runner's ``SessionController``. Provides cooperative
pause detection via ``asyncio.Event`` flags: the orchestrator checks the
pause flag between steps and the controller signals state transitions.

State machine:
    RUNNING → PAUSED (user pause or error)
    RUNNING → COMPLETED (cascade finishes)
    RUNNING → FAILED (unrecoverable error)
    PAUSED  → RUNNING (user resume)
    PAUSED  → CANCELLED (user cancel)

No other transitions are valid.
"""

from __future__ import annotations

import asyncio
import enum
import logging

from policy_factory.events import (
    CascadeCancelled,
    CascadeCompleted,
    CascadeFailed,
    CascadePaused,
    CascadeResumed,
    EventEmitter,
)

logger = logging.getLogger(__name__)


class CascadeState(enum.Enum):
    """Cascade lifecycle states."""

    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Valid transitions: from_state → set of valid to_states
_VALID_TRANSITIONS: dict[CascadeState, set[CascadeState]] = {
    CascadeState.RUNNING: {
        CascadeState.PAUSED,
        CascadeState.COMPLETED,
        CascadeState.FAILED,
    },
    CascadeState.PAUSED: {
        CascadeState.RUNNING,
        CascadeState.CANCELLED,
    },
    # Terminal states — no outgoing transitions
    CascadeState.COMPLETED: set(),
    CascadeState.FAILED: set(),
    CascadeState.CANCELLED: set(),
}


class CascadeController:
    """Controls a running cascade with strict state machine.

    Provides cooperative pause/resume/cancel functionality. The
    orchestrator checks ``is_pause_requested()`` between steps
    and the controller signals transitions via async methods.

    Args:
        cascade_id: Unique ID for this cascade run.
        emitter: EventEmitter for broadcasting state change events.
    """

    def __init__(
        self,
        cascade_id: str,
        emitter: EventEmitter,
    ) -> None:
        self._cascade_id = cascade_id
        self._emitter = emitter
        self._state = CascadeState.RUNNING

        # asyncio.Event for cooperative pause detection
        self._pause_event = asyncio.Event()

        # asyncio.Event for waking up a paused orchestrator
        self._resume_event = asyncio.Event()

        # Current position tracking
        self._current_layer: str = ""
        self._current_step: str = ""

        # Error information
        self._error_message: str | None = None
        self._error_layer: str | None = None
        self._error_step: str | None = None

    # -----------------------------------------------------------------------
    # Properties
    # -----------------------------------------------------------------------

    @property
    def cascade_id(self) -> str:
        """The cascade run ID."""
        return self._cascade_id

    @property
    def state(self) -> CascadeState:
        """Current cascade state."""
        return self._state

    @property
    def current_layer(self) -> str:
        """Current layer being processed."""
        return self._current_layer

    @current_layer.setter
    def current_layer(self, value: str) -> None:
        self._current_layer = value

    @property
    def current_step(self) -> str:
        """Current step within the layer."""
        return self._current_step

    @current_step.setter
    def current_step(self, value: str) -> None:
        self._current_step = value

    @property
    def error_message(self) -> str | None:
        """Error message if the cascade is paused or failed."""
        return self._error_message

    @property
    def error_layer(self) -> str | None:
        """Layer where the error occurred."""
        return self._error_layer

    @property
    def error_step(self) -> str | None:
        """Step where the error occurred."""
        return self._error_step

    # -----------------------------------------------------------------------
    # State transition methods
    # -----------------------------------------------------------------------

    def _can_transition(self, to_state: CascadeState) -> bool:
        """Check whether a state transition is valid."""
        return to_state in _VALID_TRANSITIONS.get(self._state, set())

    async def pause(
        self,
        error: str = "",
        error_layer: str = "",
        error_step: str = "",
    ) -> bool:
        """Transition RUNNING → PAUSED.

        Args:
            error: Optional error message that caused the pause.
            error_layer: Layer where the error occurred.
            error_step: Step where the error occurred.

        Returns:
            True if the transition succeeded, False if invalid.
        """
        if not self._can_transition(CascadeState.PAUSED):
            return False

        self._state = CascadeState.PAUSED
        self._pause_event.set()
        self._resume_event.clear()
        self._error_message = error or None
        self._error_layer = error_layer or None
        self._error_step = error_step or None

        await self._emitter.emit(
            CascadePaused(
                cascade_id=self._cascade_id,
                error=error,
                paused_layer=error_layer or self._current_layer,
                paused_step=error_step or self._current_step,
            )
        )
        return True

    async def resume(self) -> bool:
        """Transition PAUSED → RUNNING.

        Returns:
            True if the transition succeeded, False if invalid.
        """
        if not self._can_transition(CascadeState.RUNNING):
            return False

        self._state = CascadeState.RUNNING
        self._pause_event.clear()
        self._error_message = None
        self._error_layer = None
        self._error_step = None

        # Wake up the orchestrator waiting on the resume event
        self._resume_event.set()

        await self._emitter.emit(
            CascadeResumed(cascade_id=self._cascade_id)
        )
        return True

    async def cancel(self) -> bool:
        """Transition PAUSED → CANCELLED.

        Returns:
            True if the transition succeeded, False if invalid.
        """
        if not self._can_transition(CascadeState.CANCELLED):
            return False

        self._state = CascadeState.CANCELLED

        # Wake up the orchestrator so it can clean up
        self._resume_event.set()

        await self._emitter.emit(
            CascadeCancelled(cascade_id=self._cascade_id)
        )
        return True

    async def complete(self) -> bool:
        """Transition RUNNING → COMPLETED.

        Returns:
            True if the transition succeeded, False if invalid.
        """
        if not self._can_transition(CascadeState.COMPLETED):
            return False

        self._state = CascadeState.COMPLETED
        await self._emitter.emit(
            CascadeCompleted(cascade_id=self._cascade_id)
        )
        return True

    async def fail(
        self,
        error_message: str,
        error_layer: str = "",
        error_step: str = "",
    ) -> bool:
        """Transition RUNNING → FAILED.

        Args:
            error_message: Description of the failure.
            error_layer: Layer where the error occurred.
            error_step: Step where the error occurred.

        Returns:
            True if the transition succeeded, False if invalid.
        """
        if not self._can_transition(CascadeState.FAILED):
            return False

        self._state = CascadeState.FAILED
        self._error_message = error_message
        self._error_layer = error_layer or None
        self._error_step = error_step or None

        await self._emitter.emit(
            CascadeFailed(
                cascade_id=self._cascade_id,
                error=error_message,
                failed_layer=error_layer or self._current_layer,
                failed_step=error_step or self._current_step,
            )
        )
        return True

    # -----------------------------------------------------------------------
    # Cooperative pause detection
    # -----------------------------------------------------------------------

    def is_pause_requested(self) -> bool:
        """Non-blocking check of the pause flag.

        The orchestrator calls this between steps.
        """
        return self._pause_event.is_set()

    def request_pause(self) -> None:
        """Set the pause flag without transitioning state.

        This is called by the API when a user requests a pause.
        The orchestrator detects this at the next check point
        and performs the actual transition.
        """
        self._pause_event.set()

    async def wait_for_resume_or_cancel(self) -> CascadeState:
        """Wait until the cascade is resumed or cancelled.

        Used by the orchestrator when paused — blocks until a user
        resumes or cancels via the API.

        Returns:
            The new state after waking up (RUNNING or CANCELLED).
        """
        self._resume_event.clear()
        await self._resume_event.wait()
        return self._state
