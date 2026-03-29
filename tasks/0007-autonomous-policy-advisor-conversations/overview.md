# Autonomous Policy Advisor — Conversations + Philosophy Layer

Transform the policy factory from a generation tool into an autonomous policy advisor. This task adds three connected features:

1. **Conversational AI interface** for items and layers — discuss, debate, and refine policy content with an AI that holds its ground and can make autonomous edits
2. **Political philosophy layer** — new foundational layer (position 1, bottommost) that defines the system's reasoning axioms
3. **Values prompt fix** — address technocratic consensus bias in generated values

The AI becomes a co-author with its own intellectual backbone: it pushes back when it has strong logical or evidence basis, uses the philosophy layer as foundational grounding, and can "win" arguments against the human.

## Sub-tasks

| Step | Title | Done | Description |
|------|-------|------|-------------|
| [001](001.md) | Philosophy layer definition | [x] | Add philosophy to LAYERS list, update positions, add to orchestrator mappings, idea helpers, and create data directory |
| [002](002.md) | Philosophy layer prompts | [x] | Create generator prompt and seed prompt for philosophy layer |
| [003](003.md) | Philosophy layer UI | [x] | Add philosophy to layer constants, i18n strings, and theme colors |
| [004](004.md) | Values prompt fix | [x] | Update values generator prompt to enforce tension-pair format and fix technocratic consensus bias |
| [005](005.md) | Conversation database schema | [x] | Add conversations and messages tables to schema, create ConversationStoreMixin with CRUD operations |
| [006](006.md) | Conversation events | [x] | Define new event types for conversation lifecycle, streaming, file edits, and cascade pending |
| [007](007.md) | Conversation agent config | [x] | Add conversation role to agent config with full tool permissions |
| [008](008.md) | Cascade pending mechanism | [x] | Add pending cascade tracking that differs from normal queue — persists until user triggers or dismisses |
| [009](009.md) | Conversation runner | [x] | Create runner module that orchestrates conversation turns: prompt assembly, agent execution, file edit detection, git commit |
| [010](010.md) | Conversation system prompt | [x] | Create the conversation agent system prompt encoding tiered epistemic authority, hold-your-ground behavior, and anti-slop standards |
| [011](011.md) | Conversation API endpoints | [x] | Create REST router with endpoints for conversation CRUD and message sending |
| [012](012.md) | Conversation store (frontend) | [x] | Create Zustand store for conversation state, messages, streaming, and pending cascade flag |
| [013](013.md) | Conversation event dispatch | [ ] | Add conversation event handlers to useEventDispatch, routing to conversation store |
| [014](014.md) | Conversation sidebar component | [ ] | Create right-aligned sliding panel with message list, input, streaming support, and pending cascade banner |
| [015](015.md) | Item page sidebar integration | [ ] | Add conversation toggle to ItemDetailPage, adjust layout for sidebar, wire up live content refresh on file edits |
| [016](016.md) | Layer page sidebar integration | [ ] | Add conversation toggle to LayerDetailPage with same patterns as item page |
| [017](017.md) | Backend integration tests | [ ] | Test conversation API, runner with mocked agent, cascade integration, philosophy layer in cascade |
| [018](018.md) | E2E tests | [ ] | Browser tests for conversation sidebar, streaming, file edit feedback, pending cascade flow, philosophy layer UI |
