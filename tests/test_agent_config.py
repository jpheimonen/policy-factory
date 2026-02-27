"""Tests for agent configuration and model resolution."""

from pathlib import Path

import pytest

from policy_factory.agent.config import (
    _DEFAULT_MODELS,
    _ENV_VAR_MAP,
    AgentConfig,
    resolve_model,
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

    def test_default_cwd_is_data_dir(self) -> None:
        config = AgentConfig()
        assert config.cwd.name == "data"

    def test_default_permission_mode_is_bypass(self) -> None:
        config = AgentConfig()
        assert config.permission_mode == "bypassPermissions"

    def test_model_defaults_to_none(self) -> None:
        config = AgentConfig()
        assert config.model is None

    def test_max_turns_defaults_to_none(self) -> None:
        config = AgentConfig()
        assert config.max_turns is None

    def test_system_prompt_defaults_to_none(self) -> None:
        config = AgentConfig()
        assert config.system_prompt is None

    def test_custom_cwd(self, tmp_path: Path) -> None:
        config = AgentConfig(cwd=tmp_path)
        assert config.cwd == tmp_path

    def test_custom_model(self) -> None:
        config = AgentConfig(model="claude-opus-4-0-20250514")
        assert config.model == "claude-opus-4-0-20250514"

    def test_custom_max_turns(self) -> None:
        config = AgentConfig(max_turns=5)
        assert config.max_turns == 5

    def test_custom_system_prompt(self) -> None:
        config = AgentConfig(system_prompt="Be helpful.")
        assert config.system_prompt == "Be helpful."

    def test_custom_permission_mode(self) -> None:
        config = AgentConfig(permission_mode="acceptEdits")
        assert config.permission_mode == "acceptEdits"
