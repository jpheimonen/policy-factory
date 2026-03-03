"""Integration checks for the claude-agent-sdk migration.

Verifies the task-wide outcomes of rewiring from the raw Anthropic
Python SDK to ``claude-agent-sdk``:

- No ``anthropic`` imports remain in production code.
- No ``ANTHROPIC_API_KEY`` references remain in production code.
- No ``get_anthropic_client`` references remain in production code.
- No caller modules call ``resolve_tools()``.
- Package exports are correct (removed old, added new).
"""

from __future__ import annotations

from pathlib import Path

import policy_factory.agent as agent_pkg

# Root of the production source tree
_SRC_ROOT = Path(__file__).resolve().parent.parent / "src" / "policy_factory"


def _all_py_files() -> list[Path]:
    """Return all .py files under the production source tree."""
    return sorted(_SRC_ROOT.rglob("*.py"))


class TestNoAnthropicImports:
    """Verify that no production code imports from the ``anthropic`` package."""

    def test_no_import_anthropic(self) -> None:
        """No .py file under src/policy_factory/ contains 'import anthropic'."""
        for py_file in _all_py_files():
            content = py_file.read_text(encoding="utf-8")
            for i, line in enumerate(content.splitlines(), 1):
                stripped = line.strip()
                # Skip comments
                if stripped.startswith("#"):
                    continue
                assert "import anthropic" not in stripped, (
                    f"{py_file.relative_to(_SRC_ROOT)}:{i} still imports anthropic: {stripped!r}"
                )

    def test_no_from_anthropic(self) -> None:
        """No .py file under src/policy_factory/ contains 'from anthropic'."""
        for py_file in _all_py_files():
            content = py_file.read_text(encoding="utf-8")
            for i, line in enumerate(content.splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                assert "from anthropic" not in stripped, (
                    f"{py_file.relative_to(_SRC_ROOT)}:{i}"
                    f" still imports from anthropic: {stripped!r}"
                )


class TestNoAnthropicAPIKeyReferences:
    """Verify that no production code references ANTHROPIC_API_KEY."""

    def test_no_anthropic_api_key(self) -> None:
        """No .py file under src/policy_factory/ contains 'ANTHROPIC_API_KEY'."""
        for py_file in _all_py_files():
            content = py_file.read_text(encoding="utf-8")
            for i, line in enumerate(content.splitlines(), 1):
                assert "ANTHROPIC_API_KEY" not in line, (
                    f"{py_file.relative_to(_SRC_ROOT)}:{i}"
                    f" still references ANTHROPIC_API_KEY: {line.strip()!r}"
                )


class TestNoGetAnthropicClient:
    """Verify that get_anthropic_client has been fully removed."""

    def test_no_get_anthropic_client(self) -> None:
        """No .py file under src/policy_factory/ contains 'get_anthropic_client'."""
        for py_file in _all_py_files():
            content = py_file.read_text(encoding="utf-8")
            for i, line in enumerate(content.splitlines(), 1):
                assert "get_anthropic_client" not in line, (
                    f"{py_file.relative_to(_SRC_ROOT)}:{i}"
                    f" still references get_anthropic_client: {line.strip()!r}"
                )


class TestNoResolveToolsCalls:
    """Verify that caller modules no longer call resolve_tools()."""

    # Caller modules that should NOT reference resolve_tools
    CALLER_PATHS = [
        "heartbeat/orchestrator.py",
        "cascade/orchestrator.py",
        "cascade/critic_runner.py",
        "cascade/synthesis_runner.py",
        "cascade/classifier.py",
        "server/routers/seed.py",
        "ideas/generator.py",
        "ideas/evaluator.py",
    ]

    def test_no_resolve_tools_in_callers(self) -> None:
        """No caller module calls resolve_tools()."""
        for rel_path in self.CALLER_PATHS:
            py_file = _SRC_ROOT / rel_path
            if not py_file.exists():
                continue
            content = py_file.read_text(encoding="utf-8")
            assert "resolve_tools(" not in content, (
                f"{rel_path} still calls resolve_tools()"
            )


class TestPackageExports:
    """Verify that the agent package exports are correct."""

    def test_does_not_export_meditation_filter(self) -> None:
        """policy_factory.agent does not export MeditationFilter."""
        assert not hasattr(agent_pkg, "MeditationFilter"), (
            "MeditationFilter should not be exported from policy_factory.agent"
        )

    def test_does_not_export_file_tools(self) -> None:
        """policy_factory.agent does not export FILE_TOOLS."""
        assert not hasattr(agent_pkg, "FILE_TOOLS"), (
            "FILE_TOOLS should not be exported from policy_factory.agent"
        )

    def test_does_not_export_read_only_tools(self) -> None:
        """policy_factory.agent does not export READ_ONLY_TOOLS."""
        assert not hasattr(agent_pkg, "READ_ONLY_TOOLS"), (
            "READ_ONLY_TOOLS should not be exported from policy_factory.agent"
        )

    def test_does_not_export_tool_functions(self) -> None:
        """policy_factory.agent does not export TOOL_FUNCTIONS."""
        assert not hasattr(agent_pkg, "TOOL_FUNCTIONS"), (
            "TOOL_FUNCTIONS should not be exported from policy_factory.agent"
        )

    def test_exports_core_names(self) -> None:
        """policy_factory.agent exports the expected core names."""
        expected_names = [
            "AgentConfig",
            "AgentError",
            "AgentResult",
            "AgentSession",
            "ContextOverflowError",
            "build_agent_prompt",
            "resolve_model",
            "validate_path",
            "SandboxViolationError",
        ]
        for name in expected_names:
            assert hasattr(agent_pkg, name), (
                f"policy_factory.agent should export {name!r}"
            )

    def test_exports_new_resolution_functions(self) -> None:
        """policy_factory.agent exports the new tool/role resolution functions."""
        new_names = [
            "resolve_allowed_tools",
            "resolve_tool_set",
        ]
        for name in new_names:
            assert hasattr(agent_pkg, name), (
                f"policy_factory.agent should export {name!r}"
            )
