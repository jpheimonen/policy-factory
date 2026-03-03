# Requirements

## Problem Statement

Task 0001 built the complete Policy Factory application shell, but the agent framework is non-functional because it references a nonexistent `claude_agent_sdk` package. This means nothing agent-powered works: cascades, critics, heartbeat, idea generation, or seeding. Additionally, the values layer contains descriptive facts about Finland rather than axiomatic value statements, and the situational awareness seeding process is too rigid (one-shot only, no human context input).

The system needs to be made operational by: (1) rewiring the agent framework to use the real Anthropic Python SDK with tool use, (2) redesigning the values layer seeding to produce genuine axiomatic values with identified tensions, and (3) making SA seeding re-runnable with support for human-provided context.

## Success Criteria

### Agent Framework

- [ ] `AgentSession` uses the official `anthropic` Python SDK instead of the nonexistent `claude_agent_sdk`
- [ ] Agents can read, write, list, and delete markdown files in the `data/` directory through tool use
- [ ] Agents can perform web searches using Anthropic's built-in web search server tool
- [ ] Real-time token streaming to WebSocket is preserved (typewriter effect in cascade viewer)
- [ ] The meditation filter continues to suppress countdown content from streamed output
- [ ] All existing agent callers (cascade orchestrator, critic runner, heartbeat, seed, idea pipeline) work without modification to their interfaces
- [ ] Per-agent tool configuration: generator agents get file tools, critic agents get read-only tools, heartbeat gets web search, etc.
- [ ] Retry logic with exponential backoff for transient API errors is preserved
- [ ] Context overflow and authentication errors are detected and handled appropriately

### Values Layer Seeding

- [ ] A "research values" operation that uses Claude to synthesize axiomatic values from its knowledge of Finnish policy
- [ ] Values are normative statements about what Finland should prioritize, not descriptive facts about current state
- [ ] Each candidate value includes reasoning and identified tensions with other values
- [ ] The seeding flow is re-runnable, not one-shot (removes the current 409 guard)
- [ ] Candidate values are written directly to `data/values/` (no human curation UI required for MVP)
- [ ] The existing descriptive values in `seed_values.py` are replaced with this agent-driven approach

### Situational Awareness Seeding

- [ ] SA seeding accepts optional human-provided context text describing the current situation
- [ ] The seed agent uses web search plus any provided context to create/update SA layer files
- [ ] SA seeding is re-runnable (removes the 409 "already seeded" guard)
- [ ] The flow triggers a cascade after successful seeding (existing behavior preserved)

### Operational

- [ ] The `anthropic` package is added to project dependencies
- [ ] `make dev` starts the application successfully
- [ ] `make build` produces a working production build
- [ ] Basic end-to-end flow works: start app, authenticate, trigger an agent operation, see streaming output

## Constraints

- **Anthropic SDK**: Must use the official `anthropic` Python SDK, not subprocess calls to CLI or unofficial packages
- **Streaming required**: The live streaming of agent reasoning to WebSocket must be preserved — this is core UX for the cascade viewer. This means using `messages.stream()` with a custom agentic loop, not the `tool_runner` beta which only yields complete messages
- **Async throughout**: The application is async FastAPI; the agent framework must use `AsyncAnthropic` client
- **Sandboxed file access**: File tools must be restricted to the `data/` directory — agents cannot read or write outside this boundary
- **No values web search**: The values research agent uses Claude's existing knowledge, not web search — Finnish policy values are well within training data
- **Backward compatible interfaces**: `AgentSession.run(prompt) -> AgentResult` interface must remain stable so existing callers don't need changes

## Non-Goals

- **Human curation UI for values**: For this task, the values agent writes directly to disk. A curation/review UI is a future enhancement.
- **Human curation UI for SA**: Similarly, SA seeding writes directly. Review UI is future work.
- **Prompt template rewrites**: Prompts may need minor tweaks to reference tools instead of direct file access, but major prompt overhauls are out of scope.
- **New frontend pages**: No new pages required. Existing admin panel and cascade viewer should work with the fixed backend.
- **Model configuration UI**: Per-agent model selection remains configured via environment variables, not UI.
- **Streaming within tool execution**: We stream Claude's reasoning text, but tool execution itself (file reads/writes) happens silently. We don't stream "reading file X..." progress.
