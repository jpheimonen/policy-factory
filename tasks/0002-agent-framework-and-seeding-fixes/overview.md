# Task 0002: Agent Framework and Seeding Fixes

## Summary

Task 0001 built the complete Policy Factory application shell, but the agent framework is non-functional because it references a nonexistent `claude_agent_sdk` package. This task rewires the agent framework to use the official Anthropic Python SDK with tool use, implements proper file tools with sandbox validation, redesigns values seeding to produce axiomatic values instead of descriptive facts, and makes SA seeding re-runnable with support for human-provided context.

## Key Changes

1. **Agent Framework Rewrite**: Replace the nonexistent `claude_agent_sdk` with the official `anthropic` Python SDK using a custom agentic loop with `messages.stream()` for real-time token streaming
2. **File Tools Module**: New tools for agents to read, write, list, and delete markdown files within the sandboxed `data/` directory
3. **Values Seeding**: New endpoint and agent that uses Claude's knowledge to synthesize axiomatic Finnish policy values with identified tensions
4. **SA Seeding Fixes**: Remove the 409 "already seeded" guard, add optional context parameter, make re-runnable
5. **Data Initialization**: Remove automatic values writing at startup — values layer starts empty for explicit seeding

## Implementation Steps

| Step | Title | Description |
|------|-------|-------------|
| [001](./001.md) | Add Anthropic SDK dependency | Add `anthropic` to pyproject.toml and verify installation |
| [002](./002.md) | Create file tools module | Implement list_files, read_file, write_file, delete_file tools with sandbox validation |
| [003](./003.md) | Rewrite AgentSession core | Replace `_run_once()` with Anthropic SDK agentic loop using `messages.stream()` |
| [004](./004.md) | Update AgentConfig | Remove obsolete fields, add tool configuration for per-agent tool sets |
| [005](./005.md) | Update prompt templates | Adjust generator prompts to reference tool usage instead of direct file access |
| [006](./006.md) | Create values seed prompt | New prompt template for axiomatic values synthesis |
| [007](./007.md) | Implement values seed endpoint | New endpoint to trigger values seeding with direct file writing |
| [008](./008.md) | Fix SA seed endpoint | Remove 409 guard, add context parameter, clear before reseeding |
| [009](./009.md) | Update data initialization | Remove pre-seeded values writing, leave values directory empty |
| [010](./010.md) | Create shared Anthropic client | Initialize AsyncAnthropic during FastAPI lifespan startup |
| [011](./011.md) | Update seed status endpoint | Report both values and SA item counts |
| [012](./012.md) | Rewrite agent session tests | Replace claude_agent_sdk mocks with Anthropic SDK mocks |
| [013](./013.md) | Add file tools tests | Unit tests for all file tools and sandbox validation |
| [014](./014.md) | Add integration tests | Test seeding flows and cascade integration with mocked agent |
| [015](./015.md) | End-to-end verification | Verify app starts, basic flows work, streaming operates correctly |

## Dependencies

- `anthropic` Python SDK (to be added in step 001)
- Existing FastAPI application structure
- Existing data layer utilities (layers.py, markdown.py, git.py)
- Existing event system (EventEmitter, AgentTextChunk)

## Risks

- **Streaming granularity**: Anthropic SDK delta events may have different chunk boundaries than expected; meditation filter must handle this gracefully
- **Tool execution ordering**: Mixed server-side (web_search) and client-side (file ops) tools require careful handling in the agentic loop
- **Test suite coupling**: Existing tests are tightly coupled to the nonexistent SDK mock structure; complete rewrite required
