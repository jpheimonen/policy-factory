# Architecture

## Components Affected

### 1. AgentSession (`src/policy_factory/agent/session.py`) — Complete Rewrite

The entire session module is replaced. The custom streaming agentic loop (manual tool dispatch, streaming event handling, meditation filtering) is removed. In its place:

- **Session lifecycle**: Each `run()` call creates a `ClaudeSDKClient` with `ClaudeAgentOptions`, sends the prompt via `query()`, and iterates `receive_response()` to process messages. The SDK manages the full agentic loop internally — tool invocation, multi-turn conversation, and completion detection are all handled by the Claude Code CLI process.

- **Constructor changes**: The `client: AsyncAnthropic` parameter is removed entirely. There is no shared long-lived client — the SDK spawns a fresh CLI process per session. The `data_dir` parameter stays because it's needed for MCP tool server setup.

- **Message processing**: During `receive_response()`, the session inspects each message by type name (duck-typed, following the cc-runner `MessageHandler` pattern). For `AssistantMessage` messages, it iterates content blocks and emits `AgentTextChunk` events for text blocks. For `ResultMessage` (detected via `hasattr(message, "is_error")`), it extracts `is_error`, `total_cost_usd`, `num_turns`, and `session_id`.

- **AgentResult**: The dataclass gains a `session_id` field. The `full_output` field is populated by concatenating text from all `AssistantMessage` text blocks across the session. Cost is read directly from the SDK's `ResultMessage` rather than estimated from token counts.

- **MCP server creation**: Before each run, the session creates an MCP server containing the role's file tools (if any) using `create_sdk_mcp_server()`. The `data_dir` is passed to tool handlers via contextvars (set before server creation). The MCP server dict is passed to `ClaudeAgentOptions.mcp_servers`.

- **allowed_tools construction**: The session builds the `allowed_tools` list from the config. If the role has MCP file tools, the list includes the MCP server reference (using the `mcp__<server-name>` convention). If the role has web search, `"WebSearch"` is added to the list. Roles with no tools get an empty `allowed_tools` list.

- **Permission mode**: Set to `"bypassPermissions"`, which auto-approves all tool invocations without interactive prompts. This is the correct mode for automated agent runs — the agents operate unattended, and tool access is controlled entirely through the `allowed_tools` list and MCP server configuration rather than runtime approval. The SDK's `PermissionMode` type is `Literal["default", "acceptEdits", "plan", "bypassPermissions"]`.

- **Retry logic**: The retry wrapper (`run()`) preserves exponential backoff with the same constants (`MAX_RETRIES = 3`, `RETRY_BASE_DELAY = 2.0`). The transient error detection changes:
  - `CLIConnectionError` from the SDK — transient, retryable
  - `MessageParseError` from the SDK — not transient, fail immediately
  - String matching on error messages for API 5xx codes (500, 502, 503, 529), "overloaded", "rate limit" — transient
  - "prompt is too long" in error message — raises `ContextOverflowError`
  - Auth-related strings ("not found", "not installed", "auth") — raises `AgentError` immediately

- **Removed entirely**: The `_execute_tool()` method, the `_is_auth_error()` helper, the `MeditationFilter` import and usage, the `TOOL_FUNCTIONS` import, the `AsyncAnthropic` import, the manual message/tool-result construction loop, and the token-based cost estimation.

### 2. File Tools (`src/policy_factory/agent/tools.py`) — Converted to MCP Format

The tool implementations (the actual file operations) stay unchanged. The tool definition format changes entirely:

- **Sandbox validation preserved**: `validate_path()` and `SandboxViolationError` remain exactly as they are. Every MCP tool handler calls `validate_path()` before performing any file operation.

- **Tool implementations preserved**: `list_files()`, `read_file()`, `write_file()`, `delete_file()` keep their current signatures and logic. They are called from within the new MCP tool handler wrappers.

- **New MCP tool wrappers**: Each file operation gets an async MCP tool handler decorated with `@tool` from `claude_agent_sdk`. The handler receives `args: dict`, extracts the `data_dir` from the tool context (contextvars), calls the existing implementation function, and returns the result in MCP content format.

- **Tool context**: A `_set_tool_context()` / `get_tool_context()` pair using `contextvars.ContextVar`, following the cc-runner pattern. The context holds `data_dir` (and potentially `emitter` for future use). This is set by `AgentSession` before creating the MCP server, ensuring each concurrent session gets its own isolated context.

- **MCP server factory**: A `create_tools_server()` function that accepts `data_dir` and a tool set identifier, sets the tool context, selects the appropriate tool objects, and returns the MCP server dict via `create_sdk_mcp_server()`. The server name should be `"policy-factory-tools"` to distinguish from cc-runner's server.

- **Removed**: The Anthropic API format tool definition dicts (`LIST_FILES_TOOL`, `READ_FILE_TOOL`, etc.), the `WEB_SEARCH_TOOL` server-side dict, the `FILE_TOOLS`/`READ_ONLY_TOOLS`/`FILE_TOOLS_WITH_WEB_SEARCH`/`WEB_SEARCH_ONLY` list constants, the `TOOL_FUNCTIONS` dispatch dict, and the `_error_result()`/`_success_result()` helpers (replaced by MCP content format helpers).

### 3. Agent Config (`src/policy_factory/agent/config.py`) — Tool Resolution Reworked

- **`AgentConfig` dataclass**: The `tools: list[dict]` field is replaced with a `role: str` field (or similar mechanism) that lets `AgentSession` determine which MCP tools and built-in tools to provision. The `model` and `system_prompt` fields stay.

- **`resolve_tools()` replaced**: The current function returns Anthropic API format tool dicts. It is replaced by a function (e.g., `resolve_allowed_tools()`) that returns the `allowed_tools` string list for `ClaudeAgentOptions`. This function encodes the same per-role logic:
  - Roles needing full file tools: generator, heartbeat-sa-update, seed — get MCP file tools
  - Roles needing read-only: critic — gets only the read MCP tools
  - Roles needing web search: heartbeat-skim, heartbeat-triage, heartbeat-sa-update, seed — get `"WebSearch"` in the allowed list
  - Roles needing no tools: synthesis, classifier, values-seed, idea-evaluator, idea-generator — get an empty list

- **New: tool set resolution for MCP server**: A companion function determines which MCP tool objects to include in the MCP server for a given role. This is distinct from `allowed_tools` — the MCP server must be created with the right set of tools, and then `allowed_tools` references that server.

- **`resolve_model()` unchanged**: Model resolution, defaults, and env var overrides stay exactly as they are.

### 4. Prompt Construction (`src/policy_factory/agent/prompts.py`) — Simplified

- `build_agent_prompt()` no longer loads the meditation section or prepends it. It simply calls `load_prompt(category, name, **variables)` and returns the result directly.
- The `_SECTION_SEPARATOR` constant is removed.
- The `load_section("meditation")` call is removed.
- The function signature stays identical — callers are not affected.

### 5. Meditation Filter (`src/policy_factory/agent/meditation_filter.py`) — Deleted

The entire module is deleted. The `MeditationFilter` class is no longer referenced anywhere. Claude Code has its own thinking/streaming mechanism; the countdown-based meditation filter is not needed.

### 6. Agent Package Init (`src/policy_factory/agent/__init__.py`) — Updated Exports

Exports are updated to reflect the new public API:
- **Removed**: `MeditationFilter`, `FILE_TOOLS`, `READ_ONLY_TOOLS`, `TOOL_FUNCTIONS` (these were Anthropic-format internals)
- **Kept**: `AgentConfig`, `AgentError`, `AgentResult`, `AgentSession`, `ContextOverflowError`, `build_agent_prompt`, `resolve_model`
- **Kept**: `validate_path`, `SandboxViolationError` (still public for testing)
- **Updated**: Whatever replaces `resolve_tools` in the new config approach

### 7. Server Dependency Injection (`src/policy_factory/server/deps.py`) — Anthropic Code Removed

All Anthropic client infrastructure is removed:
- The `_anthropic_client` global variable
- The `_anthropic_client_initialized` flag
- The `init_anthropic_client()` function
- The `shutdown_anthropic_client()` function
- The `get_anthropic_client()` function
- The `AsyncAnthropic` type import

Everything else in deps.py stays unchanged — store, ws_manager, event_emitter, broadcast_handler, data_dir, scheduler, cascade controllers, auth dependencies.

### 8. FastAPI Lifespan (`src/policy_factory/server/app.py`) — Lifecycle Calls Removed

- The `init_anthropic_client()` call during startup is removed.
- The `await shutdown_anthropic_client()` call during shutdown is removed.
- The imports of these two functions are removed.
- All other lifespan logic stays: data directory init, broadcast handler, deps init, scheduler init/shutdown.

### 9. Caller Modules (All 8) — Simplified

All 8 caller modules undergo the same transformation:

- **Removed**: The `get_anthropic_client()` import and call. No more dependency on `server.deps` for an Anthropic client.
- **Removed**: The `client=client` parameter when constructing `AgentSession`.
- **Updated**: `AgentConfig` construction changes to pass the role (for tool resolution) instead of explicit `tools=resolve_tools(role)` dicts.
- **Seed router special case**: The two endpoints in `seed.py` currently catch `RuntimeError` from `get_anthropic_client()` and return HTTP 503. This error guard is removed since there is no more shared client to fail. If the `claude` CLI is unavailable, the error will surface as an `AgentError` from the session run, which is already handled by the existing error handling in each caller.

The callers affected:
1. `src/policy_factory/heartbeat/orchestrator.py`
2. `src/policy_factory/cascade/orchestrator.py`
3. `src/policy_factory/cascade/critic_runner.py`
4. `src/policy_factory/cascade/synthesis_runner.py`
5. `src/policy_factory/cascade/classifier.py`
6. `src/policy_factory/server/routers/seed.py`
7. `src/policy_factory/ideas/generator.py`
8. `src/policy_factory/ideas/evaluator.py`

### 10. Dependencies (`pyproject.toml`)

- **Removed**: `anthropic>=0.39.0`
- **Added**: `claude-agent-sdk==0.1.37`

## New Entities/Endpoints

No new API endpoints or database entities. This is a rewire of the internal agent execution layer.

**New internal components:**

- **Tool context module** (within `src/policy_factory/agent/tools.py` or a new `tool_context.py`): The contextvars-based tool context for passing `data_dir` to MCP tool handlers. Contains `_set_tool_context()` and `get_tool_context()` following the cc-runner pattern.

- **MCP tool handler functions**: Four async handler functions decorated with `@tool`, one per file operation. These are thin wrappers around the existing synchronous tool implementations.

- **MCP server factory function**: Creates the in-process MCP server with role-appropriate tools, following cc-runner's `create_custom_tools_server()` pattern.

- **`session_id` on AgentResult**: New field to capture the SDK session identifier from the `ResultMessage`.

## Integration Points

### AgentSession ↔ ClaudeSDKClient

Each `AgentSession.run()` call creates a fresh `ClaudeSDKClient` via async context manager. The session passes prompt, model, system prompt, MCP server config, and allowed tools. The SDK spawns a `claude` CLI subprocess that runs the agentic loop. Our code only observes the message stream, it does not drive the loop.

### AgentSession ↔ MCP Tool Server

Before each run, `AgentSession` creates an MCP server by calling the tools module's server factory. The factory sets the tool context (data_dir via contextvars), selects the right tools for the role, and returns the MCP server config dict. This dict is passed to `ClaudeAgentOptions.mcp_servers`. The Claude Code CLI process then calls these tools over the MCP protocol as needed during its agentic loop.

### MCP Tool Handlers ↔ Tool Context

Tool handlers (the `@tool`-decorated functions) retrieve `data_dir` from the contextvar-based tool context. This is set once before the MCP server is created and remains isolated per asyncio task, preventing concurrent sessions from interfering with each other.

### MCP Tool Handlers ↔ Existing Tool Implementations

The MCP tool handlers are async wrappers that call the existing synchronous tool implementations (`list_files`, `read_file`, `write_file`, `delete_file`). The sync functions are unchanged — the wrappers handle argument extraction from the MCP args dict, call the function, and format the result into MCP content blocks.

### Callers ↔ AgentSession

Callers construct an `AgentConfig` and `AgentSession`, then call `session.run(prompt)`. The construction pattern simplifies — no more `client` parameter, and tool specification changes from explicit tool dicts to role-based resolution. The return type (`AgentResult`) stays the same (with the addition of `session_id`).

### AgentSession ↔ EventEmitter

Event emission changes from token-by-token `AgentTextChunk` events to per-turn text block events. The `AgentTextChunk` dataclass itself doesn't change, but events are emitted once per `AssistantMessage` text block rather than once per streaming token delta. Subscribers (WebSocket broadcast, etc.) see coarser-grained but complete text deliveries.

### Config ↔ Tool Resolution

The config module maps agent roles to two things: (1) which MCP tool objects to include in the MCP server, and (2) which tool names to include in `allowed_tools`. Web search is not an MCP tool — it's added to `allowed_tools` as the string `"WebSearch"` for roles that need it. The MCP server only contains file operation tools.

## Failure Modes

### Claude CLI not installed or not in PATH

The `claude` binary must be available. If missing, `ClaudeSDKClient` will fail to spawn the subprocess. This surfaces as a `CLIConnectionError` (or similar) which the session's error handling translates to an `AgentError`. Unlike the current Anthropic client which validates at startup, this error only manifests at first agent invocation. The startup no longer has an "agent readiness" check — the app starts successfully regardless of CLI availability.

### Claude CLI not authenticated

If the CLI is installed but the user hasn't authenticated their Claude subscription, the CLI will emit an auth error. The session detects auth-related strings in the error message and raises `AgentError` immediately without retrying. This replaces the current `ANTHROPIC_API_KEY` check.

### CLI process crash / signal kill

The Claude Code CLI subprocess can crash or be killed by signal (OOM, etc.). This manifests as `CLIConnectionError` with exit code information. The session treats this as transient and retries with exponential backoff.

### Context overflow

When the prompt exceeds the context window, the SDK reports "prompt is too long" in the result. The session detects this string and raises `ContextOverflowError`, same as the current behavior. This is not retried.

### MCP tool handler errors

If a file tool handler raises an exception (sandbox violation, I/O error, etc.), the MCP protocol delivers the error back to the Claude Code process, which can then decide how to proceed (report the error, try a different approach, etc.). Sandbox violations from `validate_path()` are caught within the handler and returned as error results in MCP format — they do not crash the session.

### Concurrent session context isolation

Multiple agent sessions can run concurrently (e.g., heartbeat + cascade). Each session sets its own tool context in a `contextvars.ContextVar`, which is isolated per asyncio task. This prevents one session's `data_dir` from leaking into another's tool handlers. This follows the cc-runner pattern which handles the same concurrency concern.

### Rate limiting and API overload

The underlying Claude API can return rate limit or overload errors. These propagate through the CLI as error messages that the session's transient error detection recognizes. The session retries with exponential backoff, same as the current behavior but with string-based detection instead of exception-type detection.

### Network failures

Dropped connections or network timeouts during the CLI subprocess's API calls are handled by the CLI process itself. If the CLI exits abnormally, the SDK reports it as a `CLIConnectionError`, which triggers the retry logic.
