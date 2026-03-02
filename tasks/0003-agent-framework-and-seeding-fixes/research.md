# Research

## Related Code

### Agent Framework

- `src/policy_factory/agent/session.py` — Core `AgentSession` class that wraps the SDK. Contains `run()` method with retry logic and `_run_once()` with the SDK integration. Lines 171-243 contain the lazy import of `claude_agent_sdk` which is the nonexistent package. This file needs complete rewrite of `_run_once()`.

- `src/policy_factory/agent/config.py` — `AgentConfig` dataclass with `cwd`, `model`, `max_turns`, `system_prompt`, `permission_mode` fields. Contains `resolve_model()` function mapping agent roles to models via env vars. Has `_DEFAULT_MODELS` and `_ENV_VAR_MAP` dicts. The `permission_mode` field is Claude Code SDK specific and needs removal.

- `src/policy_factory/agent/meditation_filter.py` — `MeditationFilter` class that detects "10 to 1" countdown pattern and suppresses meditation content from WebSocket broadcast. Stateful filter with `detecting`/`meditating`/`streaming` states. Should be preserved; operates on streamed text chunks.

- `src/policy_factory/agent/prompts.py` — `build_agent_prompt()` function that combines meditation preamble with agent-specific templates. Uses `load_prompt()` and `load_section()` from prompts module.

- `src/policy_factory/agent/errors.py` — `AgentError` and `ContextOverflowError` exceptions. These should be preserved.

### Data Layer

- `src/policy_factory/data/seed_values.py` — `SEED_VALUES` list of 10 tuples containing descriptive facts about Finland (not axiomatic values). Each tuple is `(filename, title, body)`. This content is wrong and needs replacement.

- `src/policy_factory/data/init.py` — `initialize_data_directory()` function called at startup. Creates git repo, layer directories, and writes pre-seeded values via `_write_seed_values()`. Currently writes the descriptive values from `seed_values.py` on first run.

- `src/policy_factory/data/layers.py` — Layer CRUD utilities: `list_items()`, `read_item()`, `write_item()`, `delete_item()`, `read_narrative()`, `write_narrative()`. Also `LAYERS` list defining the five-layer hierarchy. These utilities should be reused.

- `src/policy_factory/data/markdown.py` — `read_markdown()` and `write_markdown()` functions for frontmatter parsing.

- `src/policy_factory/data/git.py` — `commit_changes()`, `init_data_repo()`, `is_git_repo()` functions.

### Seeding Endpoints

- `src/policy_factory/server/routers/seed.py` — Seed router with `POST /api/seed/` and `GET /api/seed/status` endpoints. Contains the 409 guard at lines 92-100 checking `_is_seeded()`. Also has the cascade trigger after seeding. Currently only handles SA seeding, not values.

### Event System

- `src/policy_factory/events.py` — `EventEmitter` class and `AgentTextChunk` event. The emitter uses async pub/sub pattern. `AgentTextChunk` has `cascade_id`, `agent_label`, `text` fields. Agent session emits these during streaming.

### Prompts

- `src/policy_factory/prompts/seed/seed.md` — SA seed prompt template. References `{current_date}` and `{values_content}` variables. Instructs agent to use web search and create files in `situational-awareness/` directory.

- `src/policy_factory/prompts/sections/meditation.md` — Meditation preamble prepended to all agent prompts via `build_agent_prompt()`.

- `src/policy_factory/prompts/generators/*.md` — Layer generator prompts (values, situational-awareness, strategic, tactical, policies).

### Tests

- `tests/test_agent_session.py` — 465-line test file mocking `claude_agent_sdk` via `sys.modules` patching. Contains `MockTextBlock`, `MockAssistantMessage`, `MockResultMessage` helper classes. All tests use `_create_mock_sdk()` helper. These tests need complete rewrite to mock Anthropic SDK instead.

- `tests/test_seed_api.py` — Tests for seed endpoints.

- `tests/test_meditation_filter.py` — Tests for meditation filtering. Should be preserved.

### Dependencies

- `pyproject.toml` — No Claude SDK or Anthropic SDK in dependencies. Only has FastAPI, uvicorn, bcrypt, pyjwt, pyyaml, apscheduler.

## Reuse Opportunities

### Fully Reusable (no changes needed)

- `MeditationFilter` class — Works on any text stream, not SDK-specific
- `AgentError` and `ContextOverflowError` exceptions — Generic error types
- `EventEmitter` and `AgentTextChunk` — Event system is SDK-agnostic
- `layers.py` utilities — `list_items()`, `read_item()`, `write_item()`, `delete_item()` work on filesystem
- `markdown.py` utilities — Frontmatter parsing/writing
- `git.py` utilities — Git operations
- Prompt templates — Content stays the same, may need minor wording tweaks
- `build_agent_prompt()` — Combines meditation + template, SDK-agnostic

### Partially Reusable (needs modification)

- `AgentSession.run()` — Retry logic and error classification can be preserved; `_run_once()` needs rewrite
- `AgentConfig` — Keep `model`, `system_prompt`; remove `cwd`, `max_turns`, `permission_mode` (SDK-specific); add tool configuration
- `resolve_model()` — Function works, but may need new roles for values seeding
- Seed router structure — Keep endpoint patterns, remove 409 guard, add values endpoint, add context parameter

### Not Reusable (needs replacement)

- `_run_once()` method — Entirely SDK-specific, needs full rewrite with Anthropic client
- Test mocks for claude_agent_sdk — Need new mocks for Anthropic SDK streaming

## Patterns and Conventions

### Module Organization
- `src/policy_factory/` is the main package
- Subpackages: `agent/`, `cascade/`, `data/`, `heartbeat/`, `ideas/`, `prompts/`, `server/`, `store/`
- Tests in `tests/` directory, named `test_*.py`

### Code Style
- Type hints throughout using `from __future__ import annotations`
- Dataclasses for structured data (`AgentConfig`, `AgentResult`, `LayerInfo`, `ItemSummary`)
- Docstrings on all public functions and classes
- Logging via `logging.getLogger(__name__)`

### Agent Patterns
- `AgentSession` wraps SDK interaction
- `AgentConfig` holds configuration
- `build_agent_prompt()` assembles prompts with meditation preamble
- `resolve_model()` maps roles to model names with env var overrides
- Events emitted via `EventEmitter.emit()` during streaming

### Data Layer Patterns
- Markdown files with YAML frontmatter
- `data/{layer-slug}/{filename}.md` structure
- `README.md` in each layer for narrative summary
- Git commits after modifications
- `last_modified` and `last_modified_by` stamped automatically

### API Patterns
- FastAPI routers in `server/routers/`
- Dependency injection via `Depends(get_current_user)`, `Depends(get_data_dir)`, etc.
- Pydantic models for request/response schemas
- Auth via JWT tokens

### Testing Patterns
- pytest with pytest-asyncio for async tests
- Mocking via `unittest.mock` (patch, MagicMock, AsyncMock)
- `sys.modules` patching for lazy imports
- Fixtures in `conftest.py`

## Risks and Concerns

### SDK Coupling
The `AgentSession._run_once()` method is tightly coupled to the nonexistent `claude_agent_sdk` API. The test suite creates elaborate mocks (`MockTextBlock`, `MockAssistantMessage`, `MockResultMessage`) that match the expected SDK interface. Complete rewrite required for both implementation and tests.

### Lazy Import Pattern
The SDK is lazily imported inside `_run_once()` to avoid import errors when agents aren't running. This pattern should be preserved for the Anthropic SDK to avoid startup failures if API key isn't configured.

### Streaming Granularity
The current code expects SDK to stream `AssistantMessage` objects with `content` blocks containing `text`. Anthropic SDK streaming uses different event types (`content_block_delta`, `text_delta`). The meditation filter expects text chunks — need to verify it handles Anthropic's streaming granularity.

### Permission Mode
`AgentConfig.permission_mode = "bypassPermissions"` is Claude Code SDK specific. With Anthropic SDK, there's no permission system — agents use explicit tools. This concept needs removal.

### Tool Configuration Per Agent
Current code hardcodes `allowed_tools=["WebSearch", "WebFetch"]` in `_run_once()`. Different agents need different tools:
- Generators need file write tools
- Critics need read-only tools
- Heartbeat needs web search
- Values seeder needs no tools (uses Claude's knowledge)

No existing infrastructure for per-agent tool configuration.

### Values Content Problem
`SEED_VALUES` contains descriptive facts ("Finland joined NATO in 2023") not axiomatic values ("National survival takes precedence"). This is a content problem, not just a code problem. Need new prompt to generate proper values.

### 409 Guard Rigidity
The seed endpoint's 409 guard prevents re-seeding entirely. This made sense for one-time init but blocks iterative refinement. Removing the guard is straightforward but need to handle the "clear before reseed" logic.

### Missing Values Seed Endpoint
There's no endpoint to seed the values layer — only SA seeding exists. Need new endpoint and prompt for values.

### Test Coverage
55 test files exist. Agent session tests heavily mock the SDK. Need to verify other tests (cascade, heartbeat, ideas) don't have hidden SDK dependencies.

### No Anthropic Dependency
`pyproject.toml` has no `anthropic` package. Need to add it and verify compatibility with existing Python version constraint (>=3.10).
