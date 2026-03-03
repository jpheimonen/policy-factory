# Implementation Summary

## Overview

Replaced the raw Anthropic Python SDK (`anthropic`) with `claude-agent-sdk==0.1.37` across the entire agent framework. The agent system no longer calls the Anthropic API directly with an `ANTHROPIC_API_KEY`; instead, it wraps the Claude Code CLI binary via `ClaudeSDKClient`, using the user's existing Claude subscription. All 8 caller modules, the session engine, tool system, config layer, and associated tests were updated in 6 sequential steps.

## Key Changes

- **Dependency swap**: Replaced `anthropic>=0.39.0` with `claude-agent-sdk==0.1.37` in `pyproject.toml`; removed all `ANTHROPIC_API_KEY` references
- **Removed Anthropic infrastructure**: Deleted `MeditationFilter` module, removed shared `AsyncAnthropic` client lifecycle from server deps/app lifespan, removed meditation preamble from prompt construction
- **MCP tool system**: Converted 4 file tools (`list_files`, `read_file`, `write_file`, `delete_file`) from Anthropic API format dicts to `@tool`-decorated MCP handlers served via `create_sdk_mcp_server()`; added contextvars-based tool context for per-task `data_dir` isolation
- **Role-based config**: Replaced `resolve_tools()` (which returned Anthropic API tool dicts) with `resolve_allowed_tools()` and `resolve_tool_set()` — maps each of the 11 agent roles to the correct combination of MCP server reference, `"WebSearch"`, or empty
- **Session rewrite**: Replaced the custom streaming agentic loop with `ClaudeSDKClient` lifecycle — `query()` + `receive_response()` message iteration; duck-typed message inspection for `AssistantMessage` (text event emission) and `ResultMessage` (result extraction including `session_id`, `total_cost_usd`)
- **Caller updates**: All 8 caller modules (`heartbeat/orchestrator`, `cascade/orchestrator`, `cascade/critic_runner`, `cascade/synthesis_runner`, `cascade/classifier`, `server/routers/seed`, `ideas/generator`, `ideas/evaluator`) — removed `get_anthropic_client()` imports/calls, removed `client=client` from `AgentSession`, switched to role-based `AgentConfig`
- **Test suite overhaul**: Rewrote session tests with SDK mocking, updated 4 caller test files to remove `get_anthropic_client` patches, added integration checks verifying zero `anthropic` imports or `ANTHROPIC_API_KEY` references in production code

## Files Modified

### Deleted
- `src/policy_factory/agent/meditation_filter.py` — Entire meditation filter module removed
- `tests/test_meditation_filter.py` — Associated tests removed

### Core Agent Framework
- `pyproject.toml` — `anthropic>=0.39.0` → `claude-agent-sdk==0.1.37`
- `src/policy_factory/agent/__init__.py` — Updated exports: removed `MeditationFilter`, `FILE_TOOLS`, `READ_ONLY_TOOLS`, `TOOL_FUNCTIONS`, `resolve_tools`; added new SDK-based exports
- `src/policy_factory/agent/tools.py` — Added MCP `@tool` handlers, tool context (contextvars), MCP server factory; removed Anthropic-format tool dicts and dispatch map
- `src/policy_factory/agent/config.py` — `AgentConfig.tools` → `AgentConfig.role`; replaced `resolve_tools()` with `resolve_allowed_tools()` and `resolve_tool_set()`
- `src/policy_factory/agent/session.py` — Complete rewrite: `ClaudeSDKClient` lifecycle replaces `AsyncAnthropic` streaming loop; `AgentResult` gains `session_id` field
- `src/policy_factory/agent/errors.py` — `ContextOverflowError` extended with optional `session_id`
- `src/policy_factory/agent/prompts.py` — Simplified `build_agent_prompt()` to remove meditation preamble

### Server Infrastructure
- `src/policy_factory/server/deps.py` — Removed `init_anthropic_client()`, `shutdown_anthropic_client()`, `get_anthropic_client()`, `AsyncAnthropic` references
- `src/policy_factory/server/app.py` — Removed Anthropic client init/shutdown from lifespan
- `src/policy_factory/main.py` — Removed `ANTHROPIC_API_KEY` reference

### Caller Modules (all 8)
- `src/policy_factory/heartbeat/orchestrator.py` — Removed Anthropic client; added role to config
- `src/policy_factory/cascade/orchestrator.py` — Removed Anthropic client; role `"generator"`
- `src/policy_factory/cascade/critic_runner.py` — Removed Anthropic client; role `"critic"`
- `src/policy_factory/cascade/synthesis_runner.py` — Removed inline Anthropic client import; role `"synthesis"`
- `src/policy_factory/cascade/classifier.py` — Removed Anthropic client; role `"classifier"`
- `src/policy_factory/server/routers/seed.py` — Removed Anthropic client + `resolve_tools`; roles `"values-seed"` and `"seed"`; removed `try/except RuntimeError` guards
- `src/policy_factory/ideas/generator.py` — Removed Anthropic client; role `"idea-generator"`
- `src/policy_factory/ideas/evaluator.py` — Removed Anthropic client; role `"idea-evaluator"`

### Config Files
- `Dockerfile` — Removed `ANTHROPIC_API_KEY` reference
- `Makefile` — Removed `ANTHROPIC_API_KEY` reference
- `env.example` — Removed `ANTHROPIC_API_KEY` reference

### Tests
- `tests/test_agent_tools.py` — Rewrote tool definition tests for MCP format; added MCP handler, tool context, and server factory tests
- `tests/test_agent_config.py` — Updated for role-based config; replaced `TestResolveTools` with `TestResolveAllowedTools` and `TestResolveToolSet`
- `tests/test_agent_session.py` — Complete rewrite with `ClaudeSDKClient` mocking replacing Anthropic streaming mocks
- `tests/test_agent_prompts.py` — Updated to verify no meditation preamble
- `tests/test_heartbeat_orchestrator.py` — Removed `get_anthropic_client` patches; added `session_id` to `MockAgentResult`
- `tests/test_critic_runner.py` — Removed `get_anthropic_client` patches; added `session_id` to `MockAgentResult`
- `tests/test_classifier.py` — Removed `get_anthropic_client` patches
- `tests/test_integration_seeding.py` — Removed `get_anthropic_client` patches from mock helpers
- `tests/test_sdk_migration_integration.py` — New file: integration checks for zero `anthropic` imports, zero `ANTHROPIC_API_KEY` references, correct package exports
- `tests/test_seed_api.py` — Updated for new config pattern

## How to Test

1. **Verify tests pass**: Run `make test` or `.venv/bin/python -m pytest tests/ -x -q` — all 1074 tests should pass (confirmed ✅)
2. **Check no Anthropic remnants**: Run the SDK migration integration test: `.venv/bin/python -m pytest tests/test_sdk_migration_integration.py -v`
3. **Verify dependency**: Check `pyproject.toml` lists `claude-agent-sdk==0.1.37` and NOT `anthropic`
4. **Verify server starts**: Run `make dev` and hit `GET /api/health/check` — should return `{"application": "policy-factory", "status": "ok"}`
5. **Functional agent test** (requires Claude CLI installed): Trigger any agent flow (e.g., seeding via the UI or API) and verify the agent runs through `ClaudeSDKClient` rather than the Anthropic API. Agent flows require the `claude` CLI binary to be available on PATH.
6. **UI test**: Navigate to `http://localhost:8772` (or whichever port the backend reports) and verify the application loads and is usable

## Service Status

**Status: Running**

- **Backend**: FastAPI server running on `http://127.0.0.1:8772`
- **Health check**: `GET /api/health/check` → `{"application": "policy-factory", "status": "ok"}` ✅
- **Frontend dev server**: Failed to start (Node.js 19.2.0 < required 20.19). The built frontend is served directly by the backend at the same URL.
- **Access the app**: `http://127.0.0.1:8772`

## Notes/Concerns

- **Claude CLI required at runtime**: Agent flows now require the `claude` CLI binary (from Claude Code) to be installed and available on PATH. Without it, agent operations will fail with a descriptive error at `session.run()` time. This is by design — the SDK wraps the CLI rather than calling the API directly.
- **No `ANTHROPIC_API_KEY` needed**: The application no longer needs or uses an Anthropic API key. Billing goes through the user's Claude subscription via the CLI.
- **Node.js version**: The Vite frontend dev server requires Node.js >= 20.19. The current environment has Node.js 19.2.0, so the frontend dev server (with hot reload) won't start. The pre-built frontend is served by the backend instead.
- **`meditation.md` still exists on disk**: The prompt template file `src/policy_factory/prompts/sections/meditation.md` still exists but is no longer loaded or referenced by any code. It's inert.
- **Test suite fully green**: All 1074 tests pass with no failures.
