"""Tests for agent configuration and model resolution."""

import pytest

from policy_factory.agent.config import (
    _DEFAULT_MODELS,
    _ENV_VAR_MAP,
    AgentConfig,
    resolve_model,
    resolve_tools,
)


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

    def test_tools_defaults_to_empty_list(self) -> None:
        config = AgentConfig()
        assert config.tools == []

    def test_custom_model(self) -> None:
        config = AgentConfig(model="claude-opus-4-0-20250514")
        assert config.model == "claude-opus-4-0-20250514"

    def test_custom_system_prompt(self) -> None:
        config = AgentConfig(system_prompt="Be helpful.")
        assert config.system_prompt == "Be helpful."

    def test_custom_tools(self) -> None:
        tools = [{"name": "test_tool", "description": "A test tool"}]
        config = AgentConfig(tools=tools)
        assert config.tools == tools


class TestResolveTools:
    """Tests for the resolve_tools() function."""

    def test_generator_gets_file_tools(self) -> None:
        tools = resolve_tools("generator")
        tool_names = [t.get("name") for t in tools]
        assert "list_files" in tool_names
        assert "read_file" in tool_names
        assert "write_file" in tool_names
        assert "delete_file" in tool_names
        assert len(tools) == 4

    def test_critic_gets_read_only_tools(self) -> None:
        tools = resolve_tools("critic")
        tool_names = [t.get("name") for t in tools]
        assert "list_files" in tool_names
        assert "read_file" in tool_names
        assert "write_file" not in tool_names
        assert "delete_file" not in tool_names
        assert len(tools) == 2

    def test_synthesis_gets_no_tools(self) -> None:
        tools = resolve_tools("synthesis")
        assert tools == []

    def test_classifier_gets_no_tools(self) -> None:
        tools = resolve_tools("classifier")
        assert tools == []

    def test_heartbeat_skim_gets_web_search_only(self) -> None:
        tools = resolve_tools("heartbeat-skim")
        assert len(tools) == 1
        assert tools[0].get("type") == "web_search_20250305"

    def test_heartbeat_triage_gets_web_search_only(self) -> None:
        tools = resolve_tools("heartbeat-triage")
        assert len(tools) == 1
        assert tools[0].get("type") == "web_search_20250305"

    def test_heartbeat_sa_update_gets_file_tools_and_web_search(self) -> None:
        tools = resolve_tools("heartbeat-sa-update")
        tool_names = [t.get("name") for t in tools]
        tool_types = [t.get("type") for t in tools]
        assert "list_files" in tool_names
        assert "read_file" in tool_names
        assert "write_file" in tool_names
        assert "delete_file" in tool_names
        assert "web_search_20250305" in tool_types
        assert len(tools) == 5

    def test_seed_gets_file_tools_and_web_search(self) -> None:
        tools = resolve_tools("seed")
        tool_names = [t.get("name") for t in tools]
        tool_types = [t.get("type") for t in tools]
        assert "list_files" in tool_names
        assert "read_file" in tool_names
        assert "write_file" in tool_names
        assert "delete_file" in tool_names
        assert "web_search_20250305" in tool_types
        assert len(tools) == 5

    def test_values_seed_gets_no_tools(self) -> None:
        tools = resolve_tools("values-seed")
        assert tools == []

    def test_idea_evaluator_gets_no_tools(self) -> None:
        tools = resolve_tools("idea-evaluator")
        assert tools == []

    def test_idea_generator_gets_no_tools(self) -> None:
        tools = resolve_tools("idea-generator")
        assert tools == []

    def test_unknown_role_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown agent role"):
            resolve_tools("nonexistent-role")

    def test_returns_copy_not_reference(self) -> None:
        """Ensure we can't accidentally mutate the internal tool list."""
        tools1 = resolve_tools("generator")
        tools2 = resolve_tools("generator")
        assert tools1 is not tools2
        # Mutating one shouldn't affect the other
        tools1.append({"name": "extra"})
        assert len(tools2) == 4
