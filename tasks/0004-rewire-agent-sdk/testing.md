# Testing Plan

## Unit Tests

### AgentSession (`tests/test_agent_session.py`) — Complete Rewrite

All existing tests in this file are replaced. The mocking target changes from `AsyncAnthropic` with streaming events to `ClaudeSDKClient` with message objects from `receive_response()`.

**Session lifecycle:**

- [ ] Verify that `run()` creates a `ClaudeSDKClient` with `ClaudeAgentOptions` containing the correct model from config
- [ ] Verify that `run()` passes the system prompt from config to `ClaudeAgentOptions` when one is configured
- [ ] Verify that `run()` sends the prompt string via `query()` on the client
- [ ] Verify that `run()` iterates `receive_response()` to completion
- [ ] Verify that the SDK client is used as an async context manager (entered and exited properly)

**AgentResult population:**

- [ ] Verify that a successful single-turn session (one `AssistantMessage` with text, then a `ResultMessage` with `is_error=False`) returns an `AgentResult` with `is_error=False` and the text content in `result_text`
- [ ] Verify that `total_cost_usd` is populated from the `ResultMessage`'s cost field
- [ ] Verify that `num_turns` is populated from the `ResultMessage`'s turn count
- [ ] Verify that `session_id` is populated from the `ResultMessage`'s session identifier
- [ ] Verify that `full_output` contains the concatenated text from all `AssistantMessage` text blocks across the session
- [ ] Verify that a `ResultMessage` with `is_error=True` produces an `AgentResult` with `is_error=True`

**Event emission:**

- [ ] Verify that for each `AssistantMessage` containing a text block, an `AgentTextChunk` event is emitted through the `EventEmitter` with the correct `cascade_id`, `agent_label`, and text content
- [ ] Verify that `AssistantMessage` blocks without text (e.g., tool_use blocks) do not emit `AgentTextChunk` events
- [ ] Verify that empty or whitespace-only text blocks do not emit events
- [ ] Verify that multiple `AssistantMessage` messages in a multi-turn session each emit their own `AgentTextChunk` event

**MCP server and tool provisioning:**

- [ ] Verify that when the config specifies a role with file tools, an MCP server is created and passed to `ClaudeAgentOptions.mcp_servers`
- [ ] Verify that when the config specifies a role with no tools, no MCP server is created (or an empty one is passed)
- [ ] Verify that the `allowed_tools` list in `ClaudeAgentOptions` includes the MCP server reference for roles that have file tools
- [ ] Verify that the `allowed_tools` list includes `"WebSearch"` for roles configured with web search
- [ ] Verify that roles with no tools produce an empty `allowed_tools` list
- [ ] Verify that the MCP server name is `"policy-factory-tools"` (not cc-runner's name)

**Constructor:**

- [ ] Verify that `AgentSession` accepts `config`, `emitter`, `context_id`, `agent_label`, and `data_dir` parameters
- [ ] Verify that `AgentSession` does NOT accept a `client` parameter (no Anthropic client)
- [ ] Verify that `context_id` and `agent_label` default to empty strings

**Transient error detection:**

- [ ] Verify that `CLIConnectionError` is classified as transient
- [ ] Verify that `MessageParseError` is NOT classified as transient
- [ ] Verify that an error containing "500" and "internal server error" is classified as transient
- [ ] Verify that an error containing "502" is classified as transient
- [ ] Verify that an error containing "503" is classified as transient
- [ ] Verify that an error containing "529" is classified as transient
- [ ] Verify that an error containing "overloaded" is classified as transient
- [ ] Verify that an error containing "rate limit" is classified as transient
- [ ] Verify that a generic unrecognised error is NOT classified as transient

**Retry logic:**

- [ ] Verify that a transient error on the first attempt triggers a retry and the second attempt succeeds
- [ ] Verify that retries use exponential backoff (delay doubles on each attempt)
- [ ] Verify that after `MAX_RETRIES` (3) failed attempts, an `AgentError` is raised with a descriptive message
- [ ] Verify that `AgentError` includes the `agent_role` and `cascade_id` from the session

**Context overflow:**

- [ ] Verify that an error containing "prompt is too long" raises `ContextOverflowError` immediately without retrying
- [ ] Verify that an error containing "context_length_exceeded" raises `ContextOverflowError`
- [ ] Verify that an error containing "too many tokens" raises `ContextOverflowError`

**Auth errors:**

- [ ] Verify that errors containing auth-related strings ("not found", "not installed", "auth") raise `AgentError` immediately without retrying

### File Tools — MCP Handlers (`tests/test_agent_tools.py`) — Partially Updated

**Sandbox validation (UNCHANGED — all existing tests stay):**

- [ ] Verify that a valid relative path resolves within the sandbox
- [ ] Verify that a valid nested path resolves within the sandbox
- [ ] Verify that a valid absolute path within the sandbox is accepted
- [ ] Verify that `../` traversal is rejected with `SandboxViolationError`
- [ ] Verify that double `../../` traversal is rejected
- [ ] Verify that traversal after a valid directory (`subdir/../../..`) is rejected
- [ ] Verify that deeply nested traversal is rejected
- [ ] Verify that absolute paths outside the sandbox are rejected
- [ ] Verify that symlinks escaping the sandbox are rejected
- [ ] Verify that symlinks within the sandbox are accepted
- [ ] Verify that paths with `.` segments resolve correctly

**Tool implementations (UNCHANGED — all existing tests stay):**

- [ ] `list_files`: returns `.md` files, excludes `README.md`, handles empty directories, handles directory-not-found, returns sorted results, excludes subdirectories
- [ ] `read_file`: returns file content, handles unicode, returns error for nonexistent files, returns error for paths outside sandbox, returns error for directories, handles empty files
- [ ] `write_file`: creates new files, overwrites existing files, creates parent directories, rejects paths outside sandbox, handles unicode content, handles empty content
- [ ] `delete_file`: removes existing files, is idempotent for nonexistent files, rejects paths outside sandbox, rejects directories, preserves parent directories

**MCP tool definitions (UPDATED — replaces old Anthropic format tests):**

- [ ] Verify that each MCP tool object (`list_files`, `read_file`, `write_file`, `delete_file`) has a `name`, `description`, and `input_schema` attribute
- [ ] Verify that each tool's `name` matches the expected string
- [ ] Verify that all tools have non-empty descriptions
- [ ] Verify that the `input_schema` for each tool specifies the correct parameter types (e.g., `read_file` takes a `path` parameter of type `str`)
- [ ] Verify that `write_file` takes both `path` and `content` parameters

**MCP tool handler wrappers (NEW):**

- [ ] Verify that the `list_files` MCP handler extracts `data_dir` from the tool context, calls the implementation, and returns results in MCP content format
- [ ] Verify that the `read_file` MCP handler reads the correct file via the implementation and returns content in MCP format
- [ ] Verify that the `write_file` MCP handler writes via the implementation and returns success in MCP format
- [ ] Verify that the `delete_file` MCP handler deletes via the implementation and returns success in MCP format
- [ ] Verify that sandbox violations in MCP handlers are caught and returned as error results in MCP format (not raised as exceptions)
- [ ] Verify that I/O errors in MCP handlers are caught and returned as error results

**Tool context (NEW):**

- [ ] Verify that `_set_tool_context()` stores a context dict retrievable by `get_tool_context()`
- [ ] Verify that `get_tool_context()` returns a default context (with `data_dir=None`) when no context has been set
- [ ] Verify that tool context is isolated per asyncio task — setting context in one task does not affect another concurrent task

**MCP server factory (NEW):**

- [ ] Verify that the server factory returns a dict with the key `"policy-factory-tools"`
- [ ] Verify that creating a server for a role with full file tools includes all four tool objects
- [ ] Verify that creating a server for a role with read-only tools includes only `list_files` and `read_file`
- [ ] Verify that creating a server for a role with no tools returns an appropriate result (empty server or no server)

**Tool sets (UPDATED):**

- [ ] Verify that the full file tool set contains `list_files`, `read_file`, `write_file`, `delete_file`
- [ ] Verify that the read-only tool set contains only `list_files` and `read_file`

### Agent Config (`tests/test_agent_config.py`) — Partially Updated

**Model resolution (UNCHANGED — all existing tests stay):**

- [ ] Verify default model for each of the 11 roles (generator=opus, critic=sonnet, heartbeat-skim=haiku, etc.)
- [ ] Verify that an unknown role raises `ValueError`
- [ ] Verify that environment variable overrides the default model
- [ ] Verify that empty environment variable string falls back to default
- [ ] Verify that all roles have default models defined
- [ ] Verify that all environment variable names are unique

**AgentConfig dataclass (UPDATED):**

- [ ] Verify that `AgentConfig` has `model` defaulting to `None`
- [ ] Verify that `AgentConfig` has `system_prompt` defaulting to `None`
- [ ] Verify that `AgentConfig` accepts a role or equivalent field for tool resolution
- [ ] Verify that custom values can be set for model and system prompt

**Tool resolution — `allowed_tools` (UPDATED — replaces old `resolve_tools` tests):**

- [ ] Verify that `generator` role resolves to allowed_tools containing MCP server reference and NOT `"WebSearch"`
- [ ] Verify that `critic` role resolves to allowed_tools containing MCP server reference (read-only tools) and NOT `"WebSearch"`
- [ ] Verify that `synthesis` role resolves to an empty allowed_tools list
- [ ] Verify that `classifier` role resolves to an empty allowed_tools list
- [ ] Verify that `heartbeat-skim` role resolves to allowed_tools containing `"WebSearch"` only (no MCP file tools)
- [ ] Verify that `heartbeat-triage` role resolves to allowed_tools containing `"WebSearch"` only
- [ ] Verify that `heartbeat-sa-update` role resolves to allowed_tools containing both MCP server reference and `"WebSearch"`
- [ ] Verify that `seed` role resolves to allowed_tools containing both MCP server reference and `"WebSearch"`
- [ ] Verify that `values-seed` role resolves to an empty allowed_tools list
- [ ] Verify that `idea-evaluator` role resolves to an empty allowed_tools list
- [ ] Verify that `idea-generator` role resolves to an empty allowed_tools list
- [ ] Verify that an unknown role raises `ValueError`
- [ ] Verify that the function returns a copy (mutation of the return value does not affect subsequent calls)

### Prompt Construction (`tests/test_agent_prompts.py`) — Updated

All meditation-related tests are removed and replaced with template-only tests.

- [ ] Verify that `build_agent_prompt()` returns the template content without any meditation preamble prefix
- [ ] Verify that `build_agent_prompt()` does not include the `\n\n---\n\n` section separator
- [ ] Verify that template variable substitution works (variables passed as kwargs are substituted into the template)
- [ ] Verify that a template with no variables returns the raw template content
- [ ] Verify that requesting a nonexistent template raises `FileNotFoundError`
- [ ] Verify that real prompt templates (e.g., generator, critic) load successfully and contain expected content markers (but NOT meditation content)

### Agent Errors (`tests/test_agent_errors.py`) — UNCHANGED

- [ ] All existing tests stay as-is (AgentError attributes, ContextOverflowError attributes)

### Meditation Filter — DELETED

- [ ] The test file `tests/test_meditation_filter.py` (if it exists) or the meditation tests within `test_agent_session.py` are removed entirely. No replacement tests needed.

## Integration Tests

### Caller Modules — Anthropic Client Removal

These tests verify that the caller modules work correctly after the Anthropic client dependency is removed. The existing test files already mock `AgentSession.run()` — the main change is removing `get_anthropic_client` patches.

**Heartbeat orchestrator (`tests/test_heartbeat_orchestrator.py`):**

- [ ] Verify that tier agents are invoked without any reference to `get_anthropic_client` — the mock should target `AgentSession.run()` directly, not the Anthropic client
- [ ] Verify that all existing behavioral tests (tier escalation, failure handling, agent run recording, cascade triggering, feedback memos) continue to pass with updated mocking
- [ ] Verify that `AgentSession` is constructed without a `client` parameter in the caller code

**Critic runner (`tests/test_critic_runner.py`):**

- [ ] Verify that critic agents are invoked without any reference to `get_anthropic_client`
- [ ] Verify that all existing behavioral tests (critic concurrency, partial failure, synthesis invocation, event emission, database recording) continue to pass with updated mocking

**Classifier (`tests/test_classifier.py`):**

- [ ] Verify that the classifier agent is invoked without any reference to `get_anthropic_client`
- [ ] Verify that all existing behavioral tests (classification parsing, fallback on failure, agent run recording) continue to pass with updated mocking

**Seed integration (`tests/test_integration_seeding.py`):**

- [ ] Verify that seeding agents are invoked without any reference to `get_anthropic_client`
- [ ] Verify that the seed endpoints no longer have a `RuntimeError` catch for missing Anthropic clients — errors from `AgentSession` are handled instead
- [ ] Verify that all existing behavioral tests (file creation, git commits, cascade triggering, context handling) continue to pass with updated mocking

### Server Lifecycle

- [ ] Verify that `create_app()` starts without calling `init_anthropic_client()`
- [ ] Verify that app shutdown does not call `shutdown_anthropic_client()`
- [ ] Verify that `deps.py` does not export or contain `get_anthropic_client`, `init_anthropic_client`, or `shutdown_anthropic_client`

### Dependency Removal

- [ ] Verify that `anthropic` does not appear in `pyproject.toml` dependencies
- [ ] Verify that `claude-agent-sdk==0.1.37` appears in `pyproject.toml` dependencies
- [ ] Verify that no Python source file in `src/` imports from `anthropic` (grep for `from anthropic` and `import anthropic`)
- [ ] Verify that no Python source file in `src/` references `ANTHROPIC_API_KEY` (grep for the string)
- [ ] Verify that no Python source file in `src/` references `get_anthropic_client` (grep for the function name)

### Package Exports

- [ ] Verify that `policy_factory.agent` exports `AgentConfig`, `AgentError`, `AgentResult`, `AgentSession`, `ContextOverflowError`, `build_agent_prompt`, `resolve_model`, `validate_path`, `SandboxViolationError`
- [ ] Verify that `policy_factory.agent` does NOT export `MeditationFilter`, `FILE_TOOLS`, `READ_ONLY_TOOLS`, `TOOL_FUNCTIONS`

## Browser/E2E Tests

**None** — this is a backend-only rewire with no UI changes.

## Manual Testing

**None** — all verification must be automated.
