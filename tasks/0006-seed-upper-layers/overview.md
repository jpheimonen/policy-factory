# Seed Upper Layers (Strategic, Tactical, Policies)

Add seed agents for the three upper policy layers — Strategic Objectives, Tactical Objectives, and Policies — so an admin can bootstrap the full policy stack without running a cascade. Each seed agent reads content from all layers below, uses FILE_TOOLS to write items directly, and operates independently (no cascade trigger). Also switches all Claude SDK agent roles from a hardcoded model string to the CLI default model, and refactors the seed status API from hardcoded field pairs to a list-based structure covering all 5 layers.

## Sub-tasks

| Step | Title | Done | Description |
|------|-------|------|-------------|
| [001](001.md) | Agent config and store changes | [x] | Add 3 new seed roles to all 6 config dictionaries and AgentType literal. Change existing Claude SDK roles to use model=None. Update agent run store to accept nullable model. |
| [002](002.md) | Extract shared context gathering | [x] | Make the orchestrator's context gathering and layers_below functions accessible to the seed router. Add prerequisite validation helper. Tests for context gathering and prerequisite logic. |
| [003](003.md) | Seed status API refactor | [x] | Change GET /api/seed/status from hardcoded field pairs to a list-based response covering all 5 layers. Update existing tests for the new response shape. |
| [004](004.md) | Seed prompt templates | [x] | Create strategic.md, tactical.md, and policies.md in the seed prompts directory. Each receives layers-below content as template variables and instructs the agent to write items via file tools. |
| [005](005.md) | Upper-layer seed endpoints | [ ] | Add POST endpoints for strategic-objectives, tactical-objectives, and policies seeding. Each validates prerequisites, clears existing items, gathers context, runs the seed agent, and commits to git. Includes integration tests. |
| [006](006.md) | Admin page seed card redesign | [ ] | Redesign the seed status card as a vertical layer list showing all 5 layers with status indicators, item counts, and per-layer seed buttons. Disable upper-layer buttons when prerequisites are empty. Add i18n keys. Update TypeScript types for new API shape. |
| [007](007.md) | E2E tests | [ ] | Add Playwright tests for the redesigned seed card: 5-layer display, disabled button ordering, loading states, Full Cascade button presence. |
