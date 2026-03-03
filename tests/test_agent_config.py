"""Tests for agent configuration, model resolution, and tool resolution."""

import pytest

from policy_factory.agent.config import (
    MCP_SERVER_REF,
    _DEFAULT_MODELS,
    _ENV_VAR_MAP,
    AgentConfig,
    resolve_allowed_tools,
    resolve_model,
    resolve_tool_set,
)
from policy_factory.agent.tools import TOOL_SET_FULL, TOOL_SET_NONE, TOOL_SET_READ_ONLY


class TestResolveModel:
    """Tests for the resolve_model() function."""

    def test_generator_defaults_to_opus(self) -> None:
        model = resolve_model("generator")
        assert "opus" in model.lower()

    def test_critic_defaults_to_sonnet(self) -> None:
        model = resolve_model("critic")
        assert "sonnet" in model.lower()

    def test_synthesis_defaults_to_sonnet(self) -> None:
        model = resolve_model("synthesis")
        assert "sonnet" in model.lower()

    def test_heartbeat_skim_defaults_to_haiku(self) -> None:
        model = resolve_model("heartbeat-skim")
        assert "haiku" in model.lower()

    def test_heartbeat_triage_defaults_to_haiku(self) -> None:
        model = resolve_model("heartbeat-triage")
        assert "haiku" in model.lower()

    def test_heartbeat_sa_update_defaults_to_opus(self) -> None:
        model = resolve_model("heartbeat-sa-update")
        assert "opus" in model.lower()

    def test_classifier_defaults_to_sonnet(self) -> None:
        model = resolve_model("classifier")
        assert "sonnet" in model.lower()

    def test_idea_evaluator_defaults_to_sonnet(self) -> None:
        model = resolve_model("idea-evaluator")
        assert "sonnet" in model.lower()

    def test_idea_generator_defaults_to_sonnet(self) -> None:
        model = resolve_model("idea-generator")
        assert "sonnet" in model.lower()

    def test_seed_defaults_to_sonnet(self) -> None:
        model = resolve_model("seed")
        assert "sonnet" in model.lower()

    def test_values_seed_defaults_to_sonnet(self) -> None:
        model = resolve_model("values-seed")
        assert "sonnet" in model.lower()

    def test_unknown_role_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown agent role"):
            resolve_model("nonexistent-role")

    def test_env_var_overrides_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("POLICY_FACTORY_MODEL_GENERATOR", "claude-custom-model")
        model = resolve_model("generator")
        assert model == "claude-custom-model"

    def test_env_var_empty_string_uses_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("POLICY_FACTORY_MODEL_CRITIC", "")
        model = resolve_model("critic")
        assert model == _DEFAULT_MODELS["critic"]

    def test_all_roles_have_defaults(self) -> None:
        """Every role should have both a default model and an env var mapping."""
        for role in _DEFAULT_MODELS:
            assert role in _ENV_VAR_MAP, f"Role {role!r} missing env var mapping"
            model = resolve_model(role)
            assert isinstance(model, str)
            assert len(model) > 0

    def test_all_env_vars_are_unique(self) -> None:
        """Each role should have a unique environment variable name."""
        env_vars = list(_ENV_VAR_MAP.values())
        assert len(env_vars) == len(set(env_vars)), "Duplicate environment variable names found"


class TestAgentConfig:
    """Tests for the AgentConfig dataclass."""

    def test_model_defaults_to_none(self) -> None:
        config = AgentConfig()
        assert config.model is None

    def test_system_prompt_defaults_to_none(self) -> None:
        config = AgentConfig()
        assert config.system_prompt is None

    def test_role_defaults_to_none(self) -> None:
        config = AgentConfig()
        assert config.role is None

    def test_custom_model(self) -> None:
        config = AgentConfig(model="claude-opus-4-0-20250514")
        assert config.model == "claude-opus-4-0-20250514"

    def test_custom_system_prompt(self) -> None:
        config = AgentConfig(system_prompt="Be helpful.")
        assert config.system_prompt == "Be helpful."

    def test_custom_role(self) -> None:
        config = AgentConfig(role="generator")
        assert config.role == "generator"

    def test_all_fields_set(self) -> None:
        config = AgentConfig(
            model="claude-sonnet-4-20250514",
            system_prompt="You are a critic.",
            role="critic",
        )
        assert config.model == "claude-sonnet-4-20250514"
        assert config.system_prompt == "You are a critic."
        assert config.role == "critic"


class TestResolveAllowedTools:
    """Tests for the resolve_allowed_tools() function."""

    def test_generator_gets_mcp_ref_no_web_search(self) -> None:
        tools = resolve_allowed_tools("generator")
        assert MCP_SERVER_REF in tools
        assert "WebSearch" not in tools

    def test_critic_gets_mcp_ref_no_web_search(self) -> None:
        tools = resolve_allowed_tools("critic")
        assert MCP_SERVER_REF in tools
        assert "WebSearch" not in tools

    def test_synthesis_gets_empty_list(self) -> None:
        tools = resolve_allowed_tools("synthesis")
        assert tools == []

    def test_classifier_gets_empty_list(self) -> None:
        tools = resolve_allowed_tools("classifier")
        assert tools == []

    def test_heartbeat_skim_gets_web_search_only(self) -> None:
        tools = resolve_allowed_tools("heartbeat-skim")
        assert "WebSearch" in tools
        assert MCP_SERVER_REF not in tools
        assert len(tools) == 1

    def test_heartbeat_triage_gets_web_search_only(self) -> None:
        tools = resolve_allowed_tools("heartbeat-triage")
        assert "WebSearch" in tools
        assert MCP_SERVER_REF not in tools
        assert len(tools) == 1

    def test_heartbeat_sa_update_gets_mcp_ref_and_web_search(self) -> None:
        tools = resolve_allowed_tools("heartbeat-sa-update")
        assert MCP_SERVER_REF in tools
        assert "WebSearch" in tools
        assert len(tools) == 2

    def test_seed_gets_mcp_ref_and_web_search(self) -> None:
        tools = resolve_allowed_tools("seed")
        assert MCP_SERVER_REF in tools
        assert "WebSearch" in tools
        assert len(tools) == 2

    def test_values_seed_gets_empty_list(self) -> None:
        tools = resolve_allowed_tools("values-seed")
        assert tools == []

    def test_idea_evaluator_gets_empty_list(self) -> None:
        tools = resolve_allowed_tools("idea-evaluator")
        assert tools == []

    def test_idea_generator_gets_empty_list(self) -> None:
        tools = resolve_allowed_tools("idea-generator")
        assert tools == []

    def test_unknown_role_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown agent role"):
            resolve_allowed_tools("nonexistent-role")

    def test_returns_copy_not_reference(self) -> None:
        """Ensure we can't accidentally mutate the internal tool list."""
        tools1 = resolve_allowed_tools("generator")
        tools2 = resolve_allowed_tools("generator")
        assert tools1 is not tools2
        # Mutating one shouldn't affect the other
        tools1.append("extra")
        tools3 = resolve_allowed_tools("generator")
        assert "extra" not in tools3


class TestResolveToolSet:
    """Tests for the resolve_tool_set() function."""

    def test_generator_gets_full_tools(self) -> None:
        assert resolve_tool_set("generator") == TOOL_SET_FULL

    def test_critic_gets_read_only_tools(self) -> None:
        assert resolve_tool_set("critic") == TOOL_SET_READ_ONLY

    def test_heartbeat_sa_update_gets_full_tools(self) -> None:
        assert resolve_tool_set("heartbeat-sa-update") == TOOL_SET_FULL

    def test_seed_gets_full_tools(self) -> None:
        assert resolve_tool_set("seed") == TOOL_SET_FULL

    def test_synthesis_gets_no_tools(self) -> None:
        assert resolve_tool_set("synthesis") == TOOL_SET_NONE

    def test_classifier_gets_no_tools(self) -> None:
        assert resolve_tool_set("classifier") == TOOL_SET_NONE

    def test_values_seed_gets_no_tools(self) -> None:
        assert resolve_tool_set("values-seed") == TOOL_SET_NONE

    def test_idea_evaluator_gets_no_tools(self) -> None:
        assert resolve_tool_set("idea-evaluator") == TOOL_SET_NONE

    def test_idea_generator_gets_no_tools(self) -> None:
        assert resolve_tool_set("idea-generator") == TOOL_SET_NONE

    def test_heartbeat_skim_gets_no_tools(self) -> None:
        assert resolve_tool_set("heartbeat-skim") == TOOL_SET_NONE

    def test_heartbeat_triage_gets_no_tools(self) -> None:
        assert resolve_tool_set("heartbeat-triage") == TOOL_SET_NONE

    def test_unknown_role_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown agent role"):
            resolve_tool_set("nonexistent-role")
