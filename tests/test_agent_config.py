"""Tests for agent configuration, model resolution, and tool resolution."""

import pytest

from policy_factory.agent.config import (
    _DEFAULT_MODELS,
    _ENV_VAR_MAP,
    MCP_SERVER_REF,
    AgentConfig,
    resolve_allowed_tools,
    resolve_model,
    resolve_tool_set,
    resolve_use_search,
)
from policy_factory.agent.tools import TOOL_SET_FULL, TOOL_SET_NONE, TOOL_SET_READ_ONLY


class TestResolveModel:
    """Tests for the resolve_model() function."""

    # --- CLI-default roles (Claude SDK, model=None) ---

    def test_generator_defaults_to_none(self) -> None:
        assert resolve_model("generator") is None

    def test_critic_defaults_to_none(self) -> None:
        assert resolve_model("critic") is None

    def test_heartbeat_sa_update_defaults_to_none(self) -> None:
        assert resolve_model("heartbeat-sa-update") is None

    def test_seed_defaults_to_none(self) -> None:
        assert resolve_model("seed") is None

    def test_strategic_seed_defaults_to_none(self) -> None:
        assert resolve_model("strategic-seed") is None

    def test_tactical_seed_defaults_to_none(self) -> None:
        assert resolve_model("tactical-seed") is None

    def test_policies_seed_defaults_to_none(self) -> None:
        assert resolve_model("policies-seed") is None

    def test_conversation_defaults_to_none(self) -> None:
        """Conversation role uses CLI default (Opus) for tool-using capability."""
        assert resolve_model("conversation") is None

    # --- Gemini model roles (tool-free, cheap) ---

    def test_heartbeat_skim_defaults_to_gemini_flash(self) -> None:
        model = resolve_model("heartbeat-skim")
        assert model is not None
        assert model.startswith("gemini-")

    def test_heartbeat_triage_defaults_to_gemini_flash(self) -> None:
        model = resolve_model("heartbeat-triage")
        assert model is not None
        assert model.startswith("gemini-")

    def test_synthesis_defaults_to_gemini_flash(self) -> None:
        model = resolve_model("synthesis")
        assert model is not None
        assert model.startswith("gemini-")

    def test_classifier_defaults_to_gemini_flash_lite(self) -> None:
        model = resolve_model("classifier")
        assert "gemini-2.5-flash-lite" == model

    def test_idea_evaluator_defaults_to_gemini_flash(self) -> None:
        model = resolve_model("idea-evaluator")
        assert model is not None
        assert model.startswith("gemini-")

    def test_idea_generator_defaults_to_gemini_flash(self) -> None:
        model = resolve_model("idea-generator")
        assert model is not None
        assert model.startswith("gemini-")

    def test_values_seed_defaults_to_gemini_flash(self) -> None:
        model = resolve_model("values-seed")
        assert model is not None
        assert model.startswith("gemini-")

    def test_unknown_role_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown agent role"):
            resolve_model("nonexistent-role")

    # --- Env var overrides ---

    def test_env_var_overrides_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("POLICY_FACTORY_MODEL_GENERATOR", "claude-custom-model")
        model = resolve_model("generator")
        assert model == "claude-custom-model"

    def test_env_var_overrides_none_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Env var override works for roles whose default is None."""
        monkeypatch.setenv("POLICY_FACTORY_MODEL_STRATEGIC_SEED", "claude-opus-4-0-20250514")
        assert resolve_model("strategic-seed") == "claude-opus-4-0-20250514"

    def test_env_var_overrides_tactical_seed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("POLICY_FACTORY_MODEL_TACTICAL_SEED", "claude-sonnet-4-20250514")
        assert resolve_model("tactical-seed") == "claude-sonnet-4-20250514"

    def test_env_var_overrides_policies_seed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("POLICY_FACTORY_MODEL_POLICIES_SEED", "claude-sonnet-4-20250514")
        assert resolve_model("policies-seed") == "claude-sonnet-4-20250514"

    def test_env_var_overrides_conversation(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Conversation model can be overridden via POLICY_FACTORY_MODEL_CONVERSATION."""
        monkeypatch.setenv("POLICY_FACTORY_MODEL_CONVERSATION", "claude-sonnet-4-20250514")
        assert resolve_model("conversation") == "claude-sonnet-4-20250514"

    def test_env_var_empty_string_uses_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("POLICY_FACTORY_MODEL_CRITIC", "")
        model = resolve_model("critic")
        assert model == _DEFAULT_MODELS["critic"]

    # --- Structural checks ---

    def test_all_roles_have_env_var_mapping(self) -> None:
        """Every role should have both a default model entry and an env var mapping."""
        for role in _DEFAULT_MODELS:
            assert role in _ENV_VAR_MAP, f"Role {role!r} missing env var mapping"

    def test_gemini_roles_return_strings(self) -> None:
        """Gemini-backed roles still return their hardcoded model strings."""
        gemini_roles = [
            "synthesis", "classifier", "heartbeat-skim", "heartbeat-triage",
            "idea-evaluator", "idea-generator", "values-seed",
        ]
        for role in gemini_roles:
            model = resolve_model(role)
            assert isinstance(model, str), f"Gemini role {role!r} should return a string"
            assert len(model) > 0, f"Gemini role {role!r} returned empty string"

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

    def test_heartbeat_skim_gets_empty_list(self) -> None:
        """Heartbeat skim uses Gemini Google Search grounding, no Claude tools."""
        tools = resolve_allowed_tools("heartbeat-skim")
        assert tools == []

    def test_heartbeat_triage_gets_empty_list(self) -> None:
        """Heartbeat triage uses Gemini Google Search grounding, no Claude tools."""
        tools = resolve_allowed_tools("heartbeat-triage")
        assert tools == []

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

    def test_strategic_seed_gets_mcp_ref_no_web_search(self) -> None:
        tools = resolve_allowed_tools("strategic-seed")
        assert tools == [MCP_SERVER_REF]
        assert "WebSearch" not in tools

    def test_tactical_seed_gets_mcp_ref_no_web_search(self) -> None:
        tools = resolve_allowed_tools("tactical-seed")
        assert tools == [MCP_SERVER_REF]
        assert "WebSearch" not in tools

    def test_policies_seed_gets_mcp_ref_no_web_search(self) -> None:
        tools = resolve_allowed_tools("policies-seed")
        assert tools == [MCP_SERVER_REF]
        assert "WebSearch" not in tools

    def test_conversation_gets_mcp_ref_no_web_search(self) -> None:
        """Conversation agent gets MCP file tools but no WebSearch."""
        tools = resolve_allowed_tools("conversation")
        assert tools == [MCP_SERVER_REF]
        assert "WebSearch" not in tools

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

    def test_strategic_seed_gets_full_tools(self) -> None:
        assert resolve_tool_set("strategic-seed") == TOOL_SET_FULL

    def test_tactical_seed_gets_full_tools(self) -> None:
        assert resolve_tool_set("tactical-seed") == TOOL_SET_FULL

    def test_policies_seed_gets_full_tools(self) -> None:
        assert resolve_tool_set("policies-seed") == TOOL_SET_FULL

    def test_conversation_gets_full_tools(self) -> None:
        """Conversation agent gets full file tools (list, read, write, delete)."""
        assert resolve_tool_set("conversation") == TOOL_SET_FULL

    def test_unknown_role_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown agent role"):
            resolve_tool_set("nonexistent-role")


class TestResolveUseSearch:
    """Tests for the resolve_use_search() function."""

    def test_heartbeat_skim_needs_search(self) -> None:
        assert resolve_use_search("heartbeat-skim") is True

    def test_heartbeat_triage_needs_search(self) -> None:
        assert resolve_use_search("heartbeat-triage") is True

    def test_generator_no_search(self) -> None:
        assert resolve_use_search("generator") is False

    def test_critic_no_search(self) -> None:
        assert resolve_use_search("critic") is False

    def test_synthesis_no_search(self) -> None:
        assert resolve_use_search("synthesis") is False

    def test_classifier_no_search(self) -> None:
        assert resolve_use_search("classifier") is False

    def test_seed_no_search(self) -> None:
        assert resolve_use_search("seed") is False

    def test_values_seed_no_search(self) -> None:
        assert resolve_use_search("values-seed") is False

    def test_idea_evaluator_no_search(self) -> None:
        assert resolve_use_search("idea-evaluator") is False

    def test_idea_generator_no_search(self) -> None:
        assert resolve_use_search("idea-generator") is False

    def test_strategic_seed_no_search(self) -> None:
        assert resolve_use_search("strategic-seed") is False

    def test_tactical_seed_no_search(self) -> None:
        assert resolve_use_search("tactical-seed") is False

    def test_policies_seed_no_search(self) -> None:
        assert resolve_use_search("policies-seed") is False

    def test_conversation_no_search(self) -> None:
        """Conversation agent doesn't need web search grounding by default."""
        assert resolve_use_search("conversation") is False

    def test_unknown_role_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown agent role"):
            resolve_use_search("nonexistent-role")
