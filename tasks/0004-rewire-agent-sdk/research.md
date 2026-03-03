# Research

Codebase investigation for rewiring the agent framework from the raw Anthropic Python SDK (`anthropic`) to `claude-agent-sdk` (Claude Code CLI wrapper).

## Related Code

### Current Agent Framework (Policy Factory)

**`src/policy_factory/agent/session.py`** — The main file to rewrite. Currently implements a custom streaming agentic loop using `AsyncAnthropic.messages.stream()`. Key structure:

- `AgentSession.__init__()` takes `config: AgentConfig`, `emitter: EventEmitter`, `context_id`, `agent_label`, `client: AsyncAnthropic`, `data_dir: Path`
- `AgentSession.run(prompt)` — retry wrapper with exponential backoff, calls `_run_once()`
- `AgentSession._run_once(prompt)` — implements the full agentic loop:
  - Lazy-imports `AsyncAnthropic`, builds API params (`model`, `max_tokens`, `messages`, `system`, `tools`)
  - Streams via `async with client.messages.stream(**api_params) as stream`
  - Handles `content_block_start`, `content_block_delta`, `content_block_stop`, `message_delta` events
  - Manual tool execution via `_execute_tool()` which dispatches to `TOOL_FUNCTIONS`
  - Uses `MeditationFilter` to suppress countdown content during streaming
  - Emits `AgentTextChunk` events through the `EventEmitter`
  - Continues loop until `stop_reason == "end_turn"` with no tool calls
- `AgentSession._execute_tool()` — dispatches tool calls to functions in `tools.py`, passing `self._data_dir` as first argument
- `AgentResult` dataclass — `is_error`, `result_text`, `total_cost_usd`, `num_turns`, `full_output`
- Module-level helpers: `_is_transient_error()`, `_is_context_overflow()`, `_is_auth_error()`
- Constants: `MAX_RETRIES = 3`, `RETRY_BASE_DELAY = 2.0`, `MAX_TOKENS = 8192`

**`src/policy_factory/agent/tools.py`** — File tools and tool definitions.

- **Sandbox validation**: `validate_path(data_dir, relative_path) -> Path` with `SandboxViolationError`. Handles absolute paths, relative paths, symlinks. This must be preserved.
- **Tool implementations** (all synchronous, take `data_dir: Path` as first arg):
  - `list_files(data_dir, path)` — lists `.md` files excluding `README.md`
  - `read_file(data_dir, path)` — reads file content as UTF-8
  - `write_file(data_dir, path, content)` — creates/overwrites file, auto-creates parent dirs
  - `delete_file(data_dir, path)` — idempotent file deletion
- **Tool definitions** (Anthropic API format dicts): `LIST_FILES_TOOL`, `READ_FILE_TOOL`, `WRITE_FILE_TOOL`, `DELETE_FILE_TOOL` — each with `name`, `description`, `input_schema` containing JSON Schema `properties` and `required`
- **Server-side tool**: `WEB_SEARCH_TOOL = {"type": "web_search_20250305", "name": "web_search"}`
- **Tool sets**: `FILE_TOOLS`, `READ_ONLY_TOOLS`, `FILE_TOOLS_WITH_WEB_SEARCH`, `WEB_SEARCH_ONLY`
- **Dispatch map**: `TOOL_FUNCTIONS = {"list_files": list_files, "read_file": read_file, ...}`
- Helper functions: `_error_result(message)`, `_success_result(data)`

**`src/policy_factory/agent/config.py`** — Agent configuration.

- `AgentRole` literal type with 11 roles: generator, critic, synthesis, heartbeat-skim, heartbeat-triage, heartbeat-sa-update, classifier, idea-evaluator, idea-generator, seed, values-seed
- `_DEFAULT_MODELS` — maps each role to a default Claude model name
- `_ENV_VAR_MAP` — maps each role to an env var name (e.g. `POLICY_FACTORY_MODEL_GENERATOR`)
- `resolve_model(role) -> str` — checks env var, falls back to default
- `_TOOLS_BY_ROLE` — maps each role to a list of tool dicts. Uses the tool sets from `tools.py`
- `resolve_tools(role) -> list[dict]` — returns a copy of the role's tool list
- `AgentConfig` dataclass: `model: str | None`, `system_prompt: str | None`, `tools: list[dict]`

**`src/policy_factory/agent/prompts.py`** — Prompt construction.

- `build_agent_prompt(category, name, **variables) -> str` — loads meditation section via `load_section("meditation")`, loads agent template via `load_prompt(category, name, **variables)`, concatenates with `"\n\n---\n\n"` separator
- Uses `policy_factory.prompts.load_prompt` and `policy_factory.prompts.load_section`

**`src/policy_factory/agent/meditation_filter.py`** — To be deleted.

- `MeditationFilter` class with stateful `process(chunk) -> bool` method
- Three states: detecting → meditating → streaming
- Detects countdown pattern (10...1) in streamed output, suppresses meditation content
- 135 lines, completely removed in this task

**`src/policy_factory/agent/errors.py`** — Stays unchanged.

- `AgentError(message, agent_role, cascade_id)` — general agent error
- `ContextOverflowError(message)` — context window exceeded

**`src/policy_factory/agent/__init__.py`** — Public API.

- Exports: `AgentConfig`, `AgentError`, `AgentResult`, `AgentSession`, `ContextOverflowError`, `FILE_TOOLS`, `MeditationFilter`, `READ_ONLY_TOOLS`, `SandboxViolationError`, `TOOL_FUNCTIONS`, `build_agent_prompt`, `delete_file`, `list_files`, `read_file`, `resolve_model`, `resolve_tools`, `validate_path`, `write_file`
- Must be updated to remove `MeditationFilter`, `FILE_TOOLS`, `READ_ONLY_TOOLS`, `TOOL_FUNCTIONS` exports (these become internal MCP details)

### Server Lifecycle (Anthropic Client)

**`src/policy_factory/server/deps.py`** — Dependency injection.

- `_anthropic_client: AsyncAnthropic | None` — global instance
- `_anthropic_client_initialized: bool` — tracks whether init was attempted
- `init_anthropic_client() -> AsyncAnthropic | None` — reads `ANTHROPIC_API_KEY` env var, creates `AsyncAnthropic(api_key=...)`. Logs warning if key missing. Must be removed.
- `shutdown_anthropic_client()` — calls `await _anthropic_client.close()`. Must be removed.
- `get_anthropic_client() -> AsyncAnthropic` — raises `RuntimeError` if not initialized or key missing. Used by all 8 caller modules. Must be removed.

**`src/policy_factory/server/app.py`** — FastAPI lifespan.

- Line 21-26: imports `init_anthropic_client`, `init_deps`, `init_scheduler`, `shutdown_anthropic_client`, `shutdown_scheduler`
- Line 83: `init_anthropic_client()` during startup
- Line 121: `await shutdown_anthropic_client()` during shutdown
- Both calls must be removed. The `init_deps` and `init_scheduler` calls stay.

### Caller Modules (All 8)

All callers follow the identical pattern:

```python
from policy_factory.agent.config import AgentConfig, resolve_model
from policy_factory.agent.session import AgentSession
from policy_factory.server.deps import get_anthropic_client

model = resolve_model("some-role")
client = get_anthropic_client()
config = AgentConfig(model=model)  # some also pass tools=resolve_tools(role)
session = AgentSession(
    config=config,
    emitter=emitter,
    context_id=some_id,
    agent_label="Some Label",
    client=client,
    data_dir=data_dir,
)
result = await session.run(prompt)
```

Files and their specific patterns:

1. **`src/policy_factory/heartbeat/orchestrator.py`** — `_run_tier_agent()` helper at line 149. Uses `get_anthropic_client()` at line 204. Passes `AgentConfig(model=model)` (no tools — heartbeat roles have tools assigned via `resolve_tools` but this caller doesn't use them currently; web search is handled server-side).

2. **`src/policy_factory/cascade/orchestrator.py`** — `get_anthropic_client()` at line 258. Passes `AgentConfig(model=model, system_prompt=..., tools=resolve_tools(role))`.

3. **`src/policy_factory/cascade/critic_runner.py`** — `get_anthropic_client()` at line 235. Passes `AgentConfig(model=model, tools=resolve_tools("critic"))`.

4. **`src/policy_factory/cascade/synthesis_runner.py`** — `get_anthropic_client()` at line 300. Imports `get_anthropic_client` inline. Passes `AgentConfig(model=model)`.

5. **`src/policy_factory/cascade/classifier.py`** — `get_anthropic_client()` at line 184. Passes `AgentConfig(model=model)`.

6. **`src/policy_factory/server/routers/seed.py`** — Two endpoints (values-seed at line 258, SA-seed at line 470). Both catch `RuntimeError` from `get_anthropic_client()` and return 503. Passes `AgentConfig(model=model, tools=resolve_tools(role))`.

7. **`src/policy_factory/ideas/generator.py`** — `get_anthropic_client()` at line 89. Passes `AgentConfig(model=model)`.

8. **`src/policy_factory/ideas/evaluator.py`** — `get_anthropic_client()` at line 211. Imports inline. Passes `AgentConfig(model=model)`.

### Reference Implementation (cc-runner)

**`cc-runner/src/cc_runner/session/cc_session.py`** — The reference `ClaudeCodeSession`.

Key SDK imports:
```python
from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, HookMatcher
from claude_agent_sdk._errors import CLIConnectionError, MessageParseError
from claude_agent_sdk.types import (
    HookContext, HookEvent, PermissionMode,
    PermissionResultAllow, PermissionResultDeny,
    PostToolUseHookInput, StopHookInput, SyncHookJSONOutput,
    ToolPermissionContext,
)
```

Core session pattern:
```python
options = ClaudeAgentOptions(
    cwd=str(config.cwd),
    permission_mode=permission_mode,       # e.g. "acceptEdits"
    max_turns=config.max_turns,
    allowed_tools=allowed_tools,           # list of tool name strings
    system_prompt=system_prompt,
    mcp_servers=mcp_servers,               # dict from create_sdk_mcp_server()
    model=config.model,
    stderr=self._handle_stderr,            # stderr callback
    max_buffer_size=50 * 1024 * 1024,      # 50MB buffer
)

async with ClaudeSDKClient(options=options) as client:
    await client.query(prompt)
    async for message in client.receive_response():
        # Process messages...
        if hasattr(message, "is_error"):
            result = {
                "is_error": message.is_error,
                "result": getattr(message, "result", None),
                "total_cost_usd": getattr(message, "total_cost_usd", None),
                "num_turns": getattr(message, "num_turns", None),
                "session_id": getattr(message, "session_id", None),
            }
```

Retry logic:
- `MAX_RETRIES = 3`, `RETRY_BASE_DELAY = 2.0` (same constants as current policy-factory)
- `_is_transient_error()` checks `CLIConnectionError` (retryable), `MessageParseError` (not retryable), exit codes, API status codes (500, 502, 503, 529), "overloaded"/"rate limit" strings
- On retry, rebuilds options with `options.resume = self._last_session_id`
- Auth errors ("not found", "not installed", "auth", "login", "token") raise `AuthError` immediately
- Context overflow ("prompt is too long") raises `ContextOverflowError` immediately

**`cc-runner/src/cc_runner/tools/server.py`** — MCP server creation.

```python
from claude_agent_sdk import create_sdk_mcp_server

def create_custom_tools_server(...) -> dict[str, Any]:
    _set_tool_context(emitter, run_id, ...)  # Set contextvars

    filtered_tools = [tool_obj for name, tool_obj in _ALL_TOOLS.items() if name in allowed]

    server = create_sdk_mcp_server(
        name="mp-sw-factory-tools",
        version="1.0.0",
        tools=filtered_tools,
    )
    return {"mp-sw-factory-tools": server}
```

The return dict maps server name → MCP server config. This dict is passed directly to `ClaudeAgentOptions(mcp_servers=...)`.

**`cc-runner/src/cc_runner/tools/common.py`** — Tool context via contextvars.

```python
import contextvars

_tool_context_var: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar("tool_context")

def _set_tool_context(emitter, run_id, ..., cwd=None, ...):
    ctx = {"emitter": emitter, "run_id": run_id, "cwd": cwd, ...}
    _tool_context_var.set(ctx)

def get_tool_context() -> dict[str, Any]:
    try:
        return _tool_context_var.get()
    except LookupError:
        ctx = _default_tool_context()
        _tool_context_var.set(ctx)
        return ctx
```

**`cc-runner/src/cc_runner/tools/communication.py`** — `@tool` decorator example.

```python
from claude_agent_sdk import tool

@tool(
    "ask_user",
    "Ask the user a question and wait for their response...",
    {"question": str, "options": list},
)
async def ask_user_tool(args: dict[str, Any]) -> dict[str, Any]:
    context = get_tool_context()
    # ... handler logic
    return {"content": [{"type": "text", "text": json.dumps(result)}]}
```

The `@tool` decorator takes: `(name: str, description: str, input_schema: dict[str, type])`. The handler receives `args: dict[str, Any]` and returns MCP-format content.

**`cc-runner/src/cc_runner/session/message_handler.py`** — Event emission from SDK messages.

```python
class MessageHandler:
    async def emit_events(self, message):
        msg_type = type(message).__name__
        if msg_type == "AssistantMessage" and hasattr(message, "content"):
            for block in message.content:
                if hasattr(block, "name"):  # tool_use block
                    await emitter.emit(ToolCalled(...))
                elif hasattr(block, "text"):  # text block
                    await emitter.emit(AgentMessage(text=str(block.text), ...))
        if msg_type == "UserMessage" and hasattr(message, "content"):
            for block in message.content:
                if type(block).__name__ == "ToolResultBlock":
                    await emitter.emit(ToolResult(...))
```

The pattern uses duck typing (`hasattr`) and type name checking (`type().__name__`) rather than `isinstance`, because the SDK message types are from the claude-agent-sdk package.

### Prompt Templates

**`src/policy_factory/prompts/`** — 24 template files across subdirectories. Content stays unchanged.

- `sections/meditation.md` — will no longer be loaded by `build_agent_prompt()`
- `load_prompt(category, name, **variables)` — loads `{category}/{name}.md`, substitutes `{variable}` placeholders
- `load_section(name)` — loads `sections/{name}.md`

### Test Files

**`tests/test_agent_session.py`** (1065 lines) — Most complex test file. Must be completely rewritten.

- Custom mock classes: `MockTextBlock`, `MockToolUseBlock`, `MockTextDelta`, `MockInputJsonDelta`, `MockMessageDelta`, `MockUsage`, `MockFinalMessage`, `MockStreamEvent`
- `MockStreamContextManager` — simulates `async with client.messages.stream()` with async event iteration
- `create_mock_anthropic_client()` — configures the full mock hierarchy
- Tests cover: single-turn, multi-turn with tools, text chunk events, meditation filtering, tool execution, retry logic, context overflow, config passing
- All mocking targets `AsyncAnthropic` — must change to `ClaudeSDKClient`

**`tests/test_agent_tools.py`** (519 lines) — Partially reusable.

- `TestPathValidation` — 7 tests for sandbox validation. **Stays unchanged.**
- `TestListFiles`, `TestReadFile`, `TestWriteFile`, `TestDeleteFile` — tool implementation tests. **Stays unchanged** (tool logic doesn't change, only the wrapper).
- `TestToolDefinitions` — verifies Anthropic API format structure (`input_schema.properties`, `required`). **Must be updated** for `@tool` decorator format.
- `TestToolSets` — checks `FILE_TOOLS`, `READ_ONLY_TOOLS`, etc. **Must be updated** for new MCP tool sets.

**`tests/test_agent_config.py`** (203 lines) — Partially reusable.

- `TestResolveModel` — 5 tests for model resolution. **Stays unchanged.**
- `TestAgentConfig` — basic dataclass tests. **May need minor updates** depending on how `AgentConfig` changes.
- `TestResolveTools` — verifies returned tool lists match expected sets and checks format. **Must be updated** since `resolve_tools` return type changes.

**`tests/test_agent_prompts.py`** (113 lines) — Must be updated.

- Tests meditation preamble prepending and separator. Must change to test template-only loading (no meditation prefix).

**`tests/test_agent_errors.py`** (54 lines) — **Stays unchanged.**

**Other test files with Anthropic mocking** (found via grep):

- `tests/test_heartbeat_orchestrator.py` — patches `get_anthropic_client`
- `tests/test_critic_runner.py` — patches `get_anthropic_client`
- `tests/test_integration_seeding.py` — patches `get_anthropic_client`
- `tests/test_classifier.py` — patches `get_anthropic_client`

All four patch `policy_factory.server.deps.get_anthropic_client` to return a mock. After the rewire, these patches must be removed since callers no longer take an Anthropic client.

## Reuse Opportunities

### Sandbox validation — 100% reuse

`validate_path()` and `SandboxViolationError` from `tools.py` are pure path validation with no SDK dependency. They move directly into the MCP tool handlers unchanged.

### Tool implementations — 100% reuse

`list_files()`, `read_file()`, `write_file()`, `delete_file()` are plain Python functions. The implementations stay identical — only the call site changes from `_execute_tool()` dispatch to `@tool`-decorated async wrappers that call these functions.

### Error classes — 100% reuse

`AgentError` and `ContextOverflowError` stay unchanged. The `ContextOverflowError` detection logic changes from checking Anthropic error types to checking SDK result messages (cc-runner checks for `"prompt is too long"` in `result.result`).

### Model resolution — 100% reuse

`resolve_model()`, `_DEFAULT_MODELS`, `_ENV_VAR_MAP` are pure config lookups with no SDK dependency.

### Prompt loading — reuse with simplification

`load_prompt()` and `load_section()` from `policy_factory.prompts` are fully reusable. Only `build_agent_prompt()` changes: remove meditation loading, just call `load_prompt(category, name, **variables)`.

### Retry and transient error logic — pattern reuse

The retry structure (exponential backoff, max retries, transient detection) is the same in both codebases. The transient error check must change from Anthropic exception types (`RateLimitError`, `OverloadedError`, `AuthenticationError`) to SDK error types (`CLIConnectionError` is retryable, `MessageParseError` is not).

### Event emission — adapted reuse

`AgentTextChunk` event stays. The emission point changes from intercepting `text_delta` streaming events to processing `AssistantMessage.content` text blocks in the `receive_response()` loop, following the cc-runner `MessageHandler` pattern.

### cc-runner patterns — direct adoption

The following cc-runner patterns can be adopted directly:

1. **`@tool` decorator usage** — `communication.py`, `glob.py` show the exact pattern: `@tool(name, description, schema_dict)` with `async def handler(args) -> dict`
2. **`create_sdk_mcp_server()`** — creates the MCP server from tool objects
3. **Tool context via contextvars** — `_set_tool_context()` / `get_tool_context()` for passing `data_dir` to MCP tool handlers
4. **`MessageHandler`** — duck-typed message processing with `type().__name__` checks
5. **Retry with `--resume`** — on transient error, rebuild options with `options.resume = session_id`

## Patterns and Conventions

### Tool schema format difference

Current (Anthropic API format):
```python
{
    "name": "read_file",
    "description": "Read file content...",
    "input_schema": {
        "type": "object",
        "properties": {"path": {"type": "string", "description": "..."}},
        "required": ["path"],
    },
}
```

New (`@tool` decorator format):
```python
@tool("read_file", "Read file content...", {"path": str})
async def read_file_tool(args: dict[str, Any]) -> dict[str, Any]:
    ...
```

The `@tool` decorator uses simplified Python types (`str`, `int`, `list`, `dict`, `bool`) instead of JSON Schema. The SDK converts these internally.

### Result format difference

Current tool result (returned from `_execute_tool`):
```python
{"success": True, "data": "file content"}
# or
{"error": "error message"}
```

New MCP tool result (returned from `@tool` handler):
```python
{"content": [{"type": "text", "text": json.dumps(result)}]}
```

The cc-runner wraps results in MCP content format via `make_result()` in `common.py`.

### AgentSession constructor pattern

Current:
```python
session = AgentSession(
    config=config,          # AgentConfig(model, system_prompt, tools)
    emitter=emitter,        # EventEmitter
    context_id=run_id,      # str
    agent_label=label,      # str
    client=client,          # AsyncAnthropic
    data_dir=data_dir,      # Path
)
result = await session.run(prompt)
```

New (modeled on cc-runner but simplified for policy-factory's single-shot agents):
```python
session = AgentSession(
    config=config,          # AgentConfig(model, system_prompt, allowed_tools)
    emitter=emitter,        # EventEmitter
    context_id=run_id,      # str
    agent_label=label,      # str
    data_dir=data_dir,      # Path
)
result = await session.run(prompt)
# No `client` parameter — ClaudeSDKClient is created internally per run
```

### allowed_tools pattern

cc-runner builds `allowed_tools` as a list of strings that the SDK uses to restrict which tools Claude can access:

```python
allowed_tools = ["mcp__policy-factory-tools"]  # MCP server tools
# For roles needing web search:
allowed_tools = ["mcp__policy-factory-tools", "WebSearch"]
```

The `mcp__` prefix followed by the server name grants access to all tools from that MCP server. Individual tool names can also be listed.

### Event types

Policy Factory events used by the current agent session:
- `AgentTextChunk(cascade_id, agent_label, text)` — emitted per text delta during streaming

cc-runner events used by its message handler:
- `AgentMessage(run_id, text, timestamp)` — emitted per text block from AssistantMessage
- `ToolCalled(run_id, tool_name, activity, input_data, tool_use_id, timestamp)`
- `ToolResult(run_id, tool_name, success, preview, output_data, tool_use_id, timestamp)`

Policy Factory should adapt its existing `AgentTextChunk` event to emit from `AssistantMessage` text blocks, consistent with the cc-runner approach.

### Config flow per role

The current `resolve_tools()` returns Anthropic-format tool dicts. The new approach doesn't pass tool dicts to `AgentConfig` — instead, tools are provisioned via the MCP server. The config needs to specify:

1. Which MCP tools the role can access (determined by whether tools=FILE_TOOLS, READ_ONLY_TOOLS, or empty)
2. Whether the role gets WebSearch (heartbeat-skim, heartbeat-triage, heartbeat-sa-update, seed)
3. The `allowed_tools` list for `ClaudeAgentOptions`

## Risks and Concerns

### `claude` CLI availability

The `claude-agent-sdk` requires the `claude` CLI binary to be installed and authenticated. Unlike the Anthropic API which just needs an API key, this requires:
- `claude` binary in PATH
- Active Claude subscription
- Authentication state on the host

In a container deployment, this means the `claude` binary must be baked into the image and authentication must be configured at startup. The cc-runner handles this gracefully with `AuthError` detection and diagnostic output.

### No streaming token-by-token

The current implementation streams text deltas (`text_delta` events) token by token. The claude-agent-sdk delivers complete `AssistantMessage` objects with full text blocks after each turn. This means `AgentTextChunk` events will be emitted per-turn (one chunk per assistant response) rather than token-by-token. This is a behavioral change but is inherent to the SDK architecture and matches cc-runner's approach.

### Tool execution is handled by the SDK

In the current implementation, `AgentSession._execute_tool()` manually dispatches tool calls. With the SDK, tool execution is handled by the Claude Code process itself — MCP tools are invoked by the CLI, not by our Python code's agentic loop. Our MCP tool handlers run in-process but are called by the SDK's MCP server infrastructure, not by our loop.

This means:
- The agentic loop disappears (no more `while True` with tool_use block detection)
- Tool results are not manually fed back as user messages
- The `TOOL_FUNCTIONS` dispatch dict and `_execute_tool()` are removed
- Tool handlers must be async (the `@tool` decorator requires async functions)
- The current synchronous tool implementations (`list_files`, etc.) will be called from within async `@tool` handlers

### MCP server name choice

cc-runner uses `"mp-sw-factory-tools"` as its MCP server name. Policy Factory should use a different name (e.g. `"policy-factory-tools"`) to avoid confusion and potential conflicts if both systems ever coexist.

### Test rewrite scope

The test rewrite is substantial:
- `test_agent_session.py` (1065 lines) — complete rewrite, all Anthropic mocking replaced
- `test_agent_tools.py` — tool definition tests updated, sandbox/implementation tests stay
- `test_agent_config.py` — `resolve_tools` tests updated
- `test_agent_prompts.py` — meditation tests removed
- 4 caller test files — `get_anthropic_client` patches removed

The mock pattern changes from mocking `AsyncAnthropic` with its stream events to mocking `ClaudeSDKClient` with `AssistantMessage`/`UserMessage`/`ResultMessage` objects from `receive_response()`.

### Error type mapping

Current error detection relies on Anthropic SDK exception types (`RateLimitError`, `OverloadedError`, `AuthenticationError`). The new approach must use:
- `CLIConnectionError` — CLI process died (transient, retryable)
- `MessageParseError` — SDK couldn't parse message (not transient)
- String matching on error messages for API errors (same as cc-runner)
- Exit code checking for signal kills
- `"prompt is too long"` string for context overflow

### resolve_tools return type change

`resolve_tools()` currently returns `list[dict[str, Any]]` (Anthropic API format tool definitions). After the rewire, it either:
- Returns a list of allowed tool name strings (for `allowed_tools`)
- Returns the set of MCP tool objects for the role
- Is replaced by a function that returns `allowed_tools` list

The callers that pass `tools=resolve_tools(role)` to `AgentConfig` need to be updated regardless.

### Web search provisioning change

Currently, web search is a server-side Anthropic tool (`{"type": "web_search_20250305"}`). After the rewire, it becomes a Claude Code built-in tool enabled via `allowed_tools=["WebSearch"]`. No MCP tool needed — it's handled entirely by the Claude Code CLI.

### data_dir passing via contextvars

The MCP tool handlers need access to `data_dir` for sandbox validation. Following cc-runner's `_set_tool_context()` pattern, this is set as a contextvar before creating the MCP server. Each tool handler calls `get_tool_context()["data_dir"]` instead of receiving `data_dir` as a function parameter.

### No MAX_TOKENS equivalent

The current implementation passes `max_tokens=8192` to the Anthropic API. The Claude Code CLI manages its own token limits. There is no `max_tokens` parameter in `ClaudeAgentOptions`. There is `max_turns` which limits the number of agentic turns.
