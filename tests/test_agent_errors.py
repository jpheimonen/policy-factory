"""Tests for agent error types."""

import pytest

from policy_factory.agent.errors import AgentError, ContextOverflowError


class TestAgentError:
    """Tests for the AgentError exception."""

    def test_message_is_stored(self) -> None:
        err = AgentError("something went wrong")
        assert err.message == "something went wrong"
        assert str(err) == "something went wrong"

    def test_optional_agent_role(self) -> None:
        err = AgentError("fail", agent_role="critic")
        assert err.agent_role == "critic"

    def test_optional_cascade_id(self) -> None:
        err = AgentError("fail", cascade_id="cascade-123")
        assert err.cascade_id == "cascade-123"

    def test_defaults_to_none(self) -> None:
        err = AgentError("fail")
        assert err.agent_role is None
        assert err.cascade_id is None

    def test_is_exception(self) -> None:
        with pytest.raises(AgentError):
            raise AgentError("test")


class TestContextOverflowError:
    """Tests for the ContextOverflowError exception."""

    def test_is_agent_error(self) -> None:
        err = ContextOverflowError("prompt is too long")
        assert isinstance(err, AgentError)
        assert isinstance(err, Exception)

    def test_message_is_stored(self) -> None:
        err = ContextOverflowError("prompt is too long")
        assert err.message == "prompt is too long"
        assert str(err) == "prompt is too long"

    def test_can_be_caught_as_agent_error(self) -> None:
        with pytest.raises(AgentError):
            raise ContextOverflowError("overflow")

    def test_can_be_caught_specifically(self) -> None:
        with pytest.raises(ContextOverflowError):
            raise ContextOverflowError("overflow")
