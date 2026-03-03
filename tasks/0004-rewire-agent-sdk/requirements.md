# Requirements

## Problem Statement

The agent framework implemented in Task 0003 uses the wrong SDK. It calls the Anthropic API directly via the `anthropic` Python package, which requires an `ANTHROPIC_API_KEY` environment variable and a separately paid API account. Every agent operation (heartbeat, cascade, seed, idea generation) fails immediately with:

> "Anthropic API key not configured. Set the ANTHROPIC_API_KEY environment variable to enable agent operations."

The intended architecture — visible in the cc-runner reference project at `/home/jp/projects/modernpath/cc-runner` — uses `claude-agent-sdk`, a package that wraps the Claude Code CLI binary (`claude`). This uses the user's existing Claude Code subscription with no API key needed. The entire agent session layer needs to be rewired to use this SDK instead.

## Success Criteria

- [ ] The `anthropic` package dependency is removed from `pyproject.toml` and replaced with `claude-agent-sdk==0.1.37`
- [ ] `AgentSession.run()` uses `ClaudeSDKClient` with `ClaudeAgentOptions` instead of `AsyncAnthropic.messages.stream()`
- [ ] No code references `ANTHROPIC_API_KEY`, `AsyncAnthropic`, `get_anthropic_client()`, or any direct Anthropic API call
- [ ] The `init_anthropic_client()` / `shutdown_anthropic_client()` lifecycle in `server/deps.py` and `server/app.py` is removed
- [ ] File tools (`list_files`, `read_file`, `write_file`, `delete_file`) are converted to MCP tools using the `@tool` decorator from `claude_agent_sdk` and served via `create_sdk_mcp_server()`
- [ ] Sandbox path validation (`validate_path` / `SandboxViolationError`) is preserved inside the MCP tool handlers
- [ ] Agents are restricted to MCP tools only (plus `WebSearch` for roles that need it) — no access to Claude Code's built-in Read/Write/Edit/Bash tools
- [ ] Web search capability for heartbeat-skim, heartbeat-triage, heartbeat-sa-update, and seed agents is provided via Claude Code's built-in `WebSearch` tool in the `allowed_tools` list
- [ ] The `MeditationFilter` class and the meditation preamble in prompt construction are removed entirely
- [ ] `build_agent_prompt()` loads the agent template with variable substitution only — no meditation prefix, no separator
- [ ] All 8 caller modules (heartbeat orchestrator, cascade orchestrator, critic runner, synthesis runner, classifier, seed router, idea generator, idea evaluator) work without any reference to an Anthropic client
- [ ] `AgentTextChunk` events are emitted from `AssistantMessage` text blocks during `receive_response()` iteration, following the cc-runner `MessageHandler` pattern
- [ ] `AgentResult` captures cost, num_turns, session_id, and is_error from the SDK's `ResultMessage`
- [ ] Transient error retry logic is preserved, adapted to SDK error types (`CLIConnectionError`, `MessageParseError`, signal kills, API 5xx)
- [ ] All existing tests are updated to mock `ClaudeSDKClient` instead of `AsyncAnthropic`, and all tests pass
- [ ] The application starts without errors and agent operations can be invoked (assuming `claude` CLI is installed and authenticated)

## Constraints

- Must use `claude-agent-sdk==0.1.37` — this is the same version pinned in cc-runner and known to work
- The `claude` CLI binary must be installed and authenticated on the host — this is a runtime prerequisite, not something the application manages
- The cc-runner project at `/home/jp/projects/modernpath/cc-runner` is the reference implementation for all SDK usage patterns — follow its conventions for `ClaudeSDKClient`, `ClaudeAgentOptions`, `@tool` decorator, `create_sdk_mcp_server()`, message handling, and error handling
- Agent role-to-model mapping (`config.py`) and per-role environment variable overrides must be preserved unchanged
- The `AgentConfig` dataclass interface may change internally but all callers must continue to work with the same construction pattern (pass role, get config)
- Prompt template content (the actual markdown files in `src/policy_factory/prompts/`) must not be modified — only the prompt assembly logic changes

## Non-Goals

- **No new agent capabilities** — this is a rewire, not a feature addition. The agents do the same things they did before, just via the correct SDK.
- **No prompt template changes** — the content of prompt markdown files stays identical. Only the assembly wrapper (`build_agent_prompt`) changes.
- **No new tools** — we are converting existing file tools to MCP format, not adding new tools.
- **No Ralph Wiggum / stop hooks** — the cc-runner uses Stop hooks for its pipeline looping. Policy Factory agents are single-shot (run prompt to completion). No hook infrastructure needed.
- **No session resume** — agents run single prompts to completion. The SDK's `resume` capability is not needed for this use case.
- **No HITL / AskUserQuestion** — agents operate autonomously within their prompts. No human-in-the-loop tool integration.
- **No Codex agent support** — only the Claude Code agent path is needed.
- **No changes to the event system** — `EventEmitter`, `BaseEvent`, and all event dataclasses remain unchanged. Only the emission points in `AgentSession` change.
- **No changes to the store layer** — `create_agent_run()`, `complete_agent_run()`, and all persistence logic remains unchanged.
