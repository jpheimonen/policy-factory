"""Tests for the CascadeController state machine."""

import asyncio

import pytest

from policy_factory.cascade.controller import CascadeController, CascadeState
from policy_factory.events import (
    CascadeCancelled,
    CascadeCompleted,
    CascadeFailed,
    CascadePaused,
    CascadeResumed,
    EventEmitter,
)


@pytest.fixture
def emitter() -> EventEmitter:
    """Provide a fresh EventEmitter."""
    return EventEmitter()


@pytest.fixture
def controller(emitter: EventEmitter) -> CascadeController:
    """Provide a fresh CascadeController in RUNNING state."""
    return CascadeController("test-cascade-id", emitter)


class TestControllerInitialState:
    """Tests for the controller's initial state."""

    def test_initial_state_is_running(self, controller: CascadeController) -> None:
        """Controller starts in RUNNING state."""
        assert controller.state == CascadeState.RUNNING

    def test_cascade_id(self, controller: CascadeController) -> None:
        """Controller exposes the cascade ID."""
        assert controller.cascade_id == "test-cascade-id"

    def test_pause_not_requested_initially(self, controller: CascadeController) -> None:
        """Pause is not requested initially."""
        assert controller.is_pause_requested() is False


class TestValidTransitions:
    """Tests for valid state transitions."""

    @pytest.mark.asyncio
    async def test_running_to_paused(self, controller: CascadeController) -> None:
        """RUNNING → PAUSED is valid."""
        result = await controller.pause(
            error="Test error",
            error_layer="values",
            error_step="generation",
        )
        assert result is True
        assert controller.state == CascadeState.PAUSED
        assert controller.error_message == "Test error"
        assert controller.error_layer == "values"
        assert controller.error_step == "generation"

    @pytest.mark.asyncio
    async def test_running_to_completed(self, controller: CascadeController) -> None:
        """RUNNING → COMPLETED is valid."""
        result = await controller.complete()
        assert result is True
        assert controller.state == CascadeState.COMPLETED

    @pytest.mark.asyncio
    async def test_running_to_failed(self, controller: CascadeController) -> None:
        """RUNNING → FAILED is valid."""
        result = await controller.fail(
            "Fatal error",
            error_layer="policies",
            error_step="synthesis",
        )
        assert result is True
        assert controller.state == CascadeState.FAILED
        assert controller.error_message == "Fatal error"
        assert controller.error_layer == "policies"
        assert controller.error_step == "synthesis"

    @pytest.mark.asyncio
    async def test_paused_to_running(self, controller: CascadeController) -> None:
        """PAUSED → RUNNING (resume) is valid."""
        await controller.pause()
        result = await controller.resume()
        assert result is True
        assert controller.state == CascadeState.RUNNING
        # Error info is cleared on resume
        assert controller.error_message is None

    @pytest.mark.asyncio
    async def test_paused_to_cancelled(self, controller: CascadeController) -> None:
        """PAUSED → CANCELLED is valid."""
        await controller.pause()
        result = await controller.cancel()
        assert result is True
        assert controller.state == CascadeState.CANCELLED


class TestInvalidTransitions:
    """Tests for invalid state transitions (should return False)."""

    @pytest.mark.asyncio
    async def test_running_to_cancelled_invalid(
        self, controller: CascadeController
    ) -> None:
        """RUNNING → CANCELLED is invalid (must pause first)."""
        result = await controller.cancel()
        assert result is False
        assert controller.state == CascadeState.RUNNING

    @pytest.mark.asyncio
    async def test_paused_to_completed_invalid(
        self, controller: CascadeController
    ) -> None:
        """PAUSED → COMPLETED is invalid."""
        await controller.pause()
        result = await controller.complete()
        assert result is False
        assert controller.state == CascadeState.PAUSED

    @pytest.mark.asyncio
    async def test_paused_to_failed_invalid(
        self, controller: CascadeController
    ) -> None:
        """PAUSED → FAILED is invalid."""
        await controller.pause()
        result = await controller.fail("error")
        assert result is False
        assert controller.state == CascadeState.PAUSED

    @pytest.mark.asyncio
    async def test_completed_is_terminal(
        self, controller: CascadeController
    ) -> None:
        """COMPLETED is terminal — no transitions out."""
        await controller.complete()

        assert await controller.pause() is False
        assert await controller.resume() is False
        assert await controller.cancel() is False
        assert await controller.fail("error") is False
        assert controller.state == CascadeState.COMPLETED

    @pytest.mark.asyncio
    async def test_failed_is_terminal(
        self, controller: CascadeController
    ) -> None:
        """FAILED is terminal — no transitions out."""
        await controller.fail("error")

        assert await controller.pause() is False
        assert await controller.resume() is False
        assert await controller.cancel() is False
        assert await controller.complete() is False
        assert controller.state == CascadeState.FAILED

    @pytest.mark.asyncio
    async def test_cancelled_is_terminal(
        self, controller: CascadeController
    ) -> None:
        """CANCELLED is terminal — no transitions out."""
        await controller.pause()
        await controller.cancel()

        assert await controller.pause() is False
        assert await controller.resume() is False
        assert await controller.complete() is False
        assert await controller.fail("error") is False
        assert controller.state == CascadeState.CANCELLED

    @pytest.mark.asyncio
    async def test_running_to_running_invalid(
        self, controller: CascadeController
    ) -> None:
        """RUNNING → RUNNING (resume when not paused) is invalid."""
        result = await controller.resume()
        assert result is False
        assert controller.state == CascadeState.RUNNING


class TestEventEmission:
    """Tests for events emitted during state transitions."""

    @pytest.mark.asyncio
    async def test_pause_emits_event(
        self, controller: CascadeController, emitter: EventEmitter
    ) -> None:
        """Pausing emits a CascadePaused event."""
        events = []
        emitter.subscribe(lambda e: events.append(e))

        await controller.pause(error="test", error_layer="values", error_step="generation")

        assert len(events) == 1
        assert isinstance(events[0], CascadePaused)
        assert events[0].cascade_id == "test-cascade-id"
        assert events[0].error == "test"
        assert events[0].paused_layer == "values"

    @pytest.mark.asyncio
    async def test_resume_emits_event(
        self, controller: CascadeController, emitter: EventEmitter
    ) -> None:
        """Resuming emits a CascadeResumed event."""
        events = []
        emitter.subscribe(lambda e: events.append(e))

        await controller.pause()
        await controller.resume()

        assert len(events) == 2
        assert isinstance(events[1], CascadeResumed)
        assert events[1].cascade_id == "test-cascade-id"

    @pytest.mark.asyncio
    async def test_cancel_emits_event(
        self, controller: CascadeController, emitter: EventEmitter
    ) -> None:
        """Cancelling emits a CascadeCancelled event."""
        events = []
        emitter.subscribe(lambda e: events.append(e))

        await controller.pause()
        await controller.cancel()

        assert len(events) == 2
        assert isinstance(events[1], CascadeCancelled)

    @pytest.mark.asyncio
    async def test_complete_emits_event(
        self, controller: CascadeController, emitter: EventEmitter
    ) -> None:
        """Completing emits a CascadeCompleted event."""
        events = []
        emitter.subscribe(lambda e: events.append(e))

        await controller.complete()

        assert len(events) == 1
        assert isinstance(events[0], CascadeCompleted)

    @pytest.mark.asyncio
    async def test_fail_emits_event(
        self, controller: CascadeController, emitter: EventEmitter
    ) -> None:
        """Failing emits a CascadeFailed event."""
        events = []
        emitter.subscribe(lambda e: events.append(e))

        await controller.fail("fatal error", "policies", "synthesis")

        assert len(events) == 1
        assert isinstance(events[0], CascadeFailed)
        assert events[0].error == "fatal error"
        assert events[0].failed_layer == "policies"


class TestCooperativePause:
    """Tests for cooperative pause detection."""

    def test_request_pause(self, controller: CascadeController) -> None:
        """request_pause sets the flag without changing state."""
        controller.request_pause()
        assert controller.is_pause_requested() is True
        assert controller.state == CascadeState.RUNNING

    @pytest.mark.asyncio
    async def test_pause_clears_after_resume(
        self, controller: CascadeController
    ) -> None:
        """Resuming clears the pause flag."""
        controller.request_pause()
        await controller.pause()
        await controller.resume()
        assert controller.is_pause_requested() is False


class TestPositionTracking:
    """Tests for current position tracking."""

    def test_set_current_layer(self, controller: CascadeController) -> None:
        """Setting current_layer works."""
        controller.current_layer = "strategic-objectives"
        assert controller.current_layer == "strategic-objectives"

    def test_set_current_step(self, controller: CascadeController) -> None:
        """Setting current_step works."""
        controller.current_step = "critics"
        assert controller.current_step == "critics"


class TestWaitForResumeOrCancel:
    """Tests for the wait_for_resume_or_cancel method."""

    @pytest.mark.asyncio
    async def test_wait_returns_running_on_resume(
        self, controller: CascadeController
    ) -> None:
        """wait_for_resume_or_cancel returns RUNNING when resumed."""
        await controller.pause()

        async def resume_later():
            await asyncio.sleep(0.01)
            await controller.resume()

        asyncio.create_task(resume_later())
        state = await controller.wait_for_resume_or_cancel()
        assert state == CascadeState.RUNNING

    @pytest.mark.asyncio
    async def test_wait_returns_cancelled_on_cancel(
        self, controller: CascadeController
    ) -> None:
        """wait_for_resume_or_cancel returns CANCELLED when cancelled."""
        await controller.pause()

        async def cancel_later():
            await asyncio.sleep(0.01)
            await controller.cancel()

        asyncio.create_task(cancel_later())
        state = await controller.wait_for_resume_or_cancel()
        assert state == CascadeState.CANCELLED
