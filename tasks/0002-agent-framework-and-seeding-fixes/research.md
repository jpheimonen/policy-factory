# Research

## Related Code

### Agent Framework (core rewrite target)

- `src/policy_factory/agent/session.py` — The main `AgentSession` class that wraps the nonexistent `claude_agent_sdk`. Contains retry logic with exponential backoff, transient error classification, meditation filtering, and streaming event emission. The `_run_once()` method (lines 171-243) is the core that needs complete rewrite. The public interface `run(prompt) -> AgentResult` should be preserved.

- `src/policy_factory/agent/config.py` — `AgentConfig` dataclass and `resolve_model()` function for per-agent model selection via environment variables. Defines `PermissionMode` type (no longer needed with Anthropic SDK). The role-to-model mapping and env var override pattern should be kept.

- `src/policy_factory/agent/errors.py` — Defines `AgentError` and `ContextOverflowError`. These should be preserved as-is.

- `src/policy_factory/agent/meditation_filter.py` — Stateful `MeditationFilter` class that detects the "10 to 1" countdown in streamed text and suppresses it from WebSocket broadcast. Works on chunk-by-chunk basis. Should work unchanged with new streaming approach.

- `src/policy_factory/agent/prompts.py` — `build_agent_prompt()` combines meditation preamble with agent-specific templates. Uses `load_prompt()` and `load_section()` from the prompts loader.

### Prompt System

- `src/policy_factory/prompts/loader.py` — `PromptLoader` class with `load()`, `load_section()`, and `load_sections()` methods. Uses simple `str.format()` for variable substitution. Module-level convenience functions expose the singleton.

- `src/policy_factory/prompts/sections/meditation.md` — The bias meditation preamble. 30 lines of self-reflection instructions.

- `src/policy_factory/prompts/generators/*.md` — 5 layer generator prompts (values, situational-awareness, strategic, tactical, policies). Each instructs the agent to read/write markdown files in the respective directory. These assume direct filesystem access via Claude Code — will need review for tool-based approach.

- `src/policy_factory/prompts/critics/*.md` — 6 critic archetype prompts (realist, liberal-institutionalist, nationalist-conservative, social-democratic, libertarian, green-ecological). These are analysis-only prompts that receive content as input and produce structured assessments.

- `src/policy_factory/prompts/heartbeat/*.md` — 3 heartbeat tier prompts (skim, triage, sa-update). Skim and triage use web search; sa-update modifies files.

- `src/policy_factory/prompts/seed/seed.md` — Initial SA population prompt. Uses web search to research 10 topics and creates files.

### Cascade and Critic System

- `src/policy_factory/cascade/orchestrator.py` — `trigger_cascade()` entry point and `_run_cascade_loop()` that drives layer-by-layer updates. Uses `GenerationRunnerFn`, `CriticRunnerFn`, `SynthesisRunnerFn` protocols. The `_default_generation_runner()` creates an `AgentSession` and calls `session.run(prompt)`. This is the main consumer of the agent framework.

- `src/policy_factory/cascade/critic_runner.py` — `run_critics()` launches all 6 critics in parallel via `asyncio.gather()`. Each critic uses `AgentSession.run()`. The `parse_critic_assessment()` function extracts structured data from critic output.

- `src/policy_factory/cascade/synthesis_runner.py` — Runs synthesis agent after critics complete.

- `src/policy_factory/cascade/content.py` — `gather_layer_content()` and `gather_cross_layer_context()` helpers that format layer data for prompts.

### Data Layer

- `src/policy_factory/data/layers.py` — Layer definitions (`LAYERS`, `LayerInfo`), item CRUD (`list_items`, `read_item`, `write_item`, `delete_item`), narrative summary operations (`read_narrative`, `write_narrative`), and cross-layer reference resolution. These functions read/write markdown files with YAML frontmatter.

- `src/policy_factory/data/markdown.py` — Low-level `read_markdown()` and `write_markdown()` for YAML frontmatter parsing.

- `src/policy_factory/data/init.py` — `initialize_data_directory()` called at startup. Creates git repo, layer directories, and writes pre-seeded values from `seed_values.py`.

- `src/policy_factory/data/seed_values.py` — `SEED_VALUES` list of 10 tuples containing hardcoded Finnish value descriptions. This is the content that needs replacement.

- `src/policy_factory/data/git.py` — Git operations: `init_data_repo()`, `commit_changes()`, `is_git_repo()`.

### Seeding and Heartbeat

- `src/policy_factory/server/routers/seed.py` — `POST /api/seed/` endpoint triggers SA seeding with 409 guard if already seeded. `GET /api/seed/status` checks seed state. The endpoint creates an `AgentSession` and runs the seed prompt.

- `src/policy_factory/heartbeat/orchestrator.py` — `run_heartbeat()` drives the 4-tier escalation. Each tier creates an `AgentSession` with appropriate model (Haiku for skim, Sonnet for triage, Opus for SA update). Uses markers like `NOTHING_NOTEWORTHY` and `NO_UPDATE_NEEDED` to parse agent output.

- `src/policy_factory/ideas/evaluator.py` — `evaluate_idea()` runs the evaluation pipeline. Uses `AgentSession` for scoring and synthesis.

### Event System

- `src/policy_factory/events.py` — `EventEmitter` with typed event dataclasses. `AgentTextChunk` is the key event for streaming text to WebSocket. The `emit()` method supports both sync and async handlers.

### Tests

- `tests/test_agent_session.py` — Comprehensive tests that mock `claude_agent_sdk` via `patch.dict(sys.modules, {...})`. Defines mock helpers (`MockTextBlock`, `MockAssistantMessage`, `MockResultMessage`) and tests retry logic, streaming, meditation filtering. These tests need complete rewrite for Anthropic SDK.

- `tests/conftest.py` — Shared fixtures including `store`, `data_dir`, `event_emitter`, `integration_client`. The `data_dir` fixture calls `initialize_data_directory()` which writes pre-seeded values.

- `tests/test_cascade_orchestrator.py`, `tests/test_critic_runner.py`, `tests/test_heartbeat_orchestrator.py` — Mock `AgentSession.run` at the method level using `patch.object`. These should continue working if `AgentSession.run()` interface is preserved.

## Reuse Opportunities

### Preserve and reuse as-is:
- `AgentConfig` dataclass structure and `resolve_model()` function — just remove `permission_mode` and `max_turns` fields
- `AgentError` and `ContextOverflowError` exception classes
- `MeditationFilter` class — works on text chunks, independent of SDK
- `AgentResult` dataclass — compatible return type
- `build_agent_prompt()` — no changes needed
- All prompt templates in `prompts/` — may need minor wording adjustments but structure is sound
- `EventEmitter` and all event dataclasses
- All data layer utilities (`layers.py`, `markdown.py`, `git.py`)
- `_is_transient_error()` function — Anthropic SDK uses similar error patterns

### Reuse with modifications:
- `AgentSession` class — keep constructor signature and `run()` interface, replace `_run_once()` implementation entirely
- `AgentConfig` — remove `permission_mode`, `max_turns`; add tool configuration fields

### Derive tools from existing code:
- `list_files` tool: mirror `list_items()` from `layers.py`
- `read_file` tool: mirror `read_item()` and `read_markdown()`
- `write_file` tool: mirror `write_item()` and `write_markdown()`
- `delete_file` tool: mirror `delete_item()`

## Patterns and Conventions

### Module organization
- Feature modules under `src/policy_factory/` with `__init__.py` exports
- Routers in `server/routers/` following FastAPI patterns
- Tests mirror source structure in `tests/`

### Async patterns
- All agent operations are async (`async def`, `await`)
- `asyncio.gather()` for parallel critic execution
- `asyncio.create_task()` for background cascade execution
- Event handlers can be sync or async (emitter handles both)

### Dependency injection
- Dependencies passed as arguments to orchestrators (not global state)
- `get_store()`, `get_event_emitter()`, `get_data_dir()` for router access
- FastAPI `Depends()` for request-scoped dependencies

### Error handling
- Transient vs non-transient error classification for retries
- `AgentError` with `agent_role` and `cascade_id` for diagnostics
- `ContextOverflowError` as non-retryable special case

### Event-driven architecture
- All significant actions emit typed events
- `AgentTextChunk` for streaming text (high frequency)
- Lifecycle events for cascade/heartbeat/idea progress

### Testing patterns
- Mock at `sys.modules` level for SDK replacement
- Mock at `AgentSession.run` method level for integration tests
- Fixtures in `conftest.py` for common setup
- `pytest.mark.asyncio` for async test methods

### Prompt construction
- Meditation preamble prepended to all agent prompts
- Templates use `{variable}` substitution via `str.format()`
- Sections and templates separated for reusability

## Risks and Concerns

### Breaking change in agent architecture
The current design assumes Claude Code sessions with native filesystem access. The prompts say things like "Read all files in values/" — with Anthropic SDK + tool use, the agent can only interact through explicitly provided tools. **Prompts may need adjustment** to work with a tool-calling model rather than a filesystem-native agent.

### Streaming granularity change
The current mock SDK returns `AssistantMessage` objects with content blocks during streaming. The Anthropic SDK's `messages.stream()` returns delta events. The `MeditationFilter` processes text chunks — need to verify it works with delta-based streaming where chunk boundaries may differ.

### No `anthropic` in dependencies
`pyproject.toml` does not include `anthropic` — it needs to be added. Currently no Claude/Anthropic SDK dependency at all.

### Test suite coupling to mock SDK
`test_agent_session.py` is tightly coupled to the `claude_agent_sdk` mock structure. The entire test file needs rewrite — cannot be incrementally migrated.

### Seed router 409 guard
`seed.py` returns 409 if SA layer already has items. This blocks re-seeding. Need to either remove the guard or add a "force" parameter.

### Values written at init time
`initialize_data_directory()` writes values from `seed_values.py` at first boot, before any agent can run. The new values seeding flow needs to either:
1. Skip automatic values writing (leave values empty for later seeding), or
2. Keep minimal placeholder values and add a "reseed values" endpoint

### Tool sandboxing needed
Agents should only access files within `data/` directory. Tools need to validate paths and reject attempts to read/write outside the sandbox.

### Web search tool is server-side
Anthropic's `web_search_20250305` is a server-side tool — the SDK handles execution. Custom file tools are client-side and need local execution. Mixed tool types in one agent session need careful handling.

### Concurrent agent sessions
Multiple critics run in parallel. The `AsyncAnthropic` client should be created once and reused (connection pooling). Need to ensure thread/task safety.

### Model string format
Current code uses model strings like `"claude-opus-4-0-20250514"`. Anthropic SDK may use different format. Need to verify model name compatibility.
