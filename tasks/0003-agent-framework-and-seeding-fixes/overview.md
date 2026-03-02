# Agent Framework and Seeding Fixes

Task 0001 built the complete Policy Factory application shell, but the agent framework is non-functional because it references a nonexistent `claude_agent_sdk` package. This task rewires the agent framework to use the official Anthropic Python SDK with tool use, implements proper file tools with sandbox validation, redesigns values seeding to produce axiomatic values instead of descriptive facts, and makes SA seeding re-runnable with support for human-provided context.

## Sub-tasks

| Step | Title | Done | Description |
|------|-------|------|-------------|
| [001](001.md) | Add Anthropic SDK dependency | [x] | Add the anthropic package to pyproject.toml and verify installation |
| [002](002.md) | Create file tools module | [x] | Implement list_files, read_file, write_file, delete_file tools with sandbox validation |
| [003](003.md) | Rewrite AgentSession core | [x] | Replace _run_once() with Anthropic SDK streaming agentic loop |
| [004](004.md) | Update AgentConfig for tool configuration | [x] | Remove obsolete fields, add per-agent tool sets, add values-seed role |
| [005](005.md) | Update generator prompt templates | [x] | Adjust prompts to reference tool usage instead of direct file access |
| [006](006.md) | Create values seed prompt | [x] | New prompt template for axiomatic values synthesis using Claude's knowledge |
| [007](007.md) | Implement values seed endpoint | [x] | New POST /api/seed/values endpoint with direct file writing |
| [008](008.md) | Fix SA seed endpoint | [x] | Remove 409 guard, add context parameter, clear before reseeding |
| [009](009.md) | Update data initialization | [x] | Remove pre-seeded values writing, leave values directory empty |
| [010](010.md) | Create shared Anthropic client | [x] | Initialize AsyncAnthropic during FastAPI lifespan startup |
| [011](011.md) | Update seed status endpoint | [x] | Report both values and SA item counts |
| [012](012.md) | Rewrite agent session tests | [x] | Replace claude_agent_sdk mocks with Anthropic SDK mocks |
| [013](013.md) | Add file tools tests | [x] | Unit tests for all file tools and sandbox validation |
| [014](014.md) | Add seeding integration tests | [ ] | Test seeding flows and cascade integration with mocked agent |
| [015](015.md) | End-to-end verification | [ ] | Verify app starts, basic flows work, streaming operates correctly |
