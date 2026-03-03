# Architecture

## Components Affected

### AgentSession (complete rewrite of core method)

The `AgentSession` class retains its public interface — constructor accepting `AgentConfig`, `EventEmitter`, `context_id`, and `agent_label`; and the async `run(prompt)` method returning `AgentResult`. The internal implementation changes completely:

- Replace the single-shot Claude Code SDK call with an agentic conversation loop using the Anthropic Python SDK
- Each loop iteration: stream a message, emit text tokens to WebSocket as they arrive, detect tool_use blocks when the stream completes, execute the requested tools locally (for file operations) or pass through to the SDK (for web search), feed tool results back to the conversation, stream the next turn
- Continue looping until the model returns `stop_reason == "end_turn"` with no pending tool calls
- Preserve real-time token streaming for the cascade viewer typewriter effect — text deltas are emitted to the EventEmitter as `AgentTextChunk` events during streaming, not batched per turn
- The meditation filter continues to operate on streamed text chunks, suppressing the countdown content from broadcast while preserving it in the full output
- Retry logic and transient error classification remain, adapted to Anthropic SDK error types

### AgentConfig (minor modifications)

Remove fields that were specific to the Claude Code SDK (`permission_mode`, `max_turns`). Add a field to specify which tools the agent should have access to. The model resolution and environment variable override pattern remain unchanged.

### Agent Tools Module (new)

A new module providing file operation tools that agents can invoke:

- **list_files**: Given a layer directory path, return the list of markdown filenames (excluding README.md). Validates that the path is within the data directory sandbox.
- **read_file**: Given a file path within the data directory, return the file contents (raw markdown with frontmatter). Validates path is within sandbox.
- **write_file**: Given a file path and content, write the file. Validates path is within sandbox. Creates parent directories if needed.
- **delete_file**: Given a file path, delete the file if it exists. Validates path is within sandbox.

All file tools enforce that paths resolve to within the configured data directory — any attempt to access files outside the sandbox returns an error to the agent.

Web search is handled differently — it uses Anthropic's built-in server-side web search tool, which the SDK executes automatically. The agent session passes through web search tool definitions and handles results from the SDK.

### Tool Configuration by Agent Type

Different agent types receive different tool sets:

- **Generator agents** (values, SA, strategic, tactical, policies): list_files, read_file, write_file, delete_file — they need to read existing content and write updates
- **Critic agents**: list_files, read_file only — they analyze but do not modify
- **Synthesis agent**: no file tools — receives all context in the prompt, produces analysis output
- **Classifier agent**: no tools — pure prompt-based classification
- **Heartbeat skim/triage**: web_search only — they research external sources but don't touch files
- **Heartbeat SA update**: list_files, read_file, write_file, delete_file, plus web_search — needs both file access and web research
- **Seed agent (SA)**: list_files, read_file, write_file, plus web_search
- **Values seed agent** (new): no tools — uses Claude's training knowledge to generate axiomatic values, output returned for direct file writing
- **Idea evaluator/generator**: no tools — receives stack summary in prompt, produces analysis

### Values Seeding Flow (new)

A new values seeding capability replaces the hardcoded `seed_values.py` content:

- A dedicated endpoint triggers values seeding (can be called multiple times — no 409 guard)
- The values seed agent is a single-call analysis agent (no tools, no agentic loop) that uses Claude's knowledge to:
  - Identify core Finnish national values from constitutional principles, cross-party consensus areas, and policy discourse
  - Express each value as a normative/axiomatic statement (what Finland prioritizes and why) rather than descriptive facts
  - Identify tensions between values (where they conflict or trade off)
  - Produce structured output with each value's title, body text, and related tensions
- The endpoint parses the agent output and writes directly to `data/values/` — no human curation step
- The existing values files are deleted before writing new ones (clean slate on reseed)
- The README.md narrative summary is regenerated to reflect the new values
- After values are seeded, a cascade can be triggered from the values layer upward

### Situational Awareness Seeding (modifications)

The existing SA seed endpoint is modified:

- Remove the 409 "already seeded" guard — allow re-seeding at any time
- Add an optional `context` field to the request body — human-provided situational context that gets included in the agent prompt
- When context is provided, the agent incorporates it alongside its web research
- Existing SA files are cleared before seeding (clean slate)
- The SA seed agent uses web search to research current topics plus the file tools to write results
- After seeding, the endpoint triggers a cascade from SA upward (unchanged behavior)

### Data Initialization (modifications)

The `initialize_data_directory()` function changes:

- Still creates the git repo and layer directories on first run
- No longer writes pre-seeded values from `seed_values.py` — the values directory starts empty
- The README.md files for each layer are still created as placeholders
- The values seeding is now a separate explicit action, not automatic at boot

### Prompt Templates (minor adjustments)

Generator prompts that reference direct filesystem access need adjustment:

- Change language from "Read all files in the directory" to "Use the list_files and read_file tools to examine existing content"
- Change language from "Create/update/remove files" to "Use write_file and delete_file tools to make changes"
- The meditation preamble and overall prompt structure remain unchanged
- Critic and synthesis prompts need no changes (they don't reference file operations)

### Values Prompt (new)

A new prompt template for the values seed agent:

- Instructs Claude to draw on its knowledge of Finnish constitutional law, cross-party political consensus, Nordic policy traditions, and EU membership context
- Requests axiomatic value statements (normative positions about what matters) rather than descriptive facts
- Asks for explicit identification of value tensions and trade-offs
- Specifies the output format expected (structured list of values with titles, bodies, and tensions)
- Does not include meditation preamble (single-call analysis, not an agentic session)

### Anthropic Client Management

A shared `AsyncAnthropic` client instance should be created once at application startup and reused across all agent sessions:

- Provides connection pooling for concurrent agent runs (especially the 6 parallel critics)
- Initialized during FastAPI lifespan startup alongside other dependencies
- Passed to `AgentSession` instances or accessed via dependency injection
- Configured with the `ANTHROPIC_API_KEY` environment variable

### Test Infrastructure (significant changes)

The agent session tests need complete rewrite:

- Mock the `AsyncAnthropic` client rather than `sys.modules["claude_agent_sdk"]`
- Test the agentic loop behavior: streaming, tool calls, multi-turn conversations
- Test tool execution and sandboxing
- Test meditation filtering with streaming deltas
- Test error handling and retry logic with Anthropic SDK error types

Integration tests that mock at the `AgentSession.run` level should continue working without changes, since the public interface is preserved.

### Dependencies

Add `anthropic` to `pyproject.toml` dependencies. Remove any vestigial references to `claude_agent_sdk` or `claude-agent-sdk`.

## New Entities/Endpoints

### Values Seed Endpoint

A new endpoint to trigger values layer seeding:

- Accepts POST requests with an empty body (no parameters needed for values seeding)
- Returns success status and any relevant metadata (number of values created)
- Can be called multiple times — always clears and regenerates values
- Requires authentication (same as existing seed endpoint)

### SA Seed Endpoint (modified)

The existing SA seed endpoint gains:

- Removal of the 409 conflict response for already-seeded state
- An optional request body field for human-provided situational context
- Behavior remains otherwise unchanged (triggers agent, writes files, starts cascade)

### Seed Status Endpoint (modified)

The existing status endpoint should report both values and SA seed state:

- Whether values layer has items
- Whether SA layer has items
- Count of items in each

## Integration Points

### AgentSession to Anthropic SDK

The agent session creates messages using the Anthropic SDK's streaming interface. It builds a conversation with:
- System prompt from the meditation preamble plus agent-specific content
- User message containing the constructed prompt
- Tool definitions based on the agent type's configured tool set

The session streams the response, extracts text deltas for event emission, and handles tool_use content blocks by executing tools and continuing the conversation.

### AgentSession to File Tools

When the agent requests a file tool, the session:
1. Validates the requested path is within the data directory sandbox
2. Executes the operation using the existing data layer utilities (which already implement the file operations)
3. Returns the result (file contents, success status, or error) as tool output
4. Continues the conversation with the tool result

### AgentSession to EventEmitter

Text content is emitted as `AgentTextChunk` events during streaming (same as before). The meditation filter sits between the raw stream and the event emission, suppressing countdown content. The full unfiltered output is accumulated separately for the `AgentResult.full_output` field.

### Values Seed to Data Layer

After the values agent returns its output:
1. Parse the structured value definitions from the output
2. Delete all existing files in `data/values/` except README.md
3. Write new markdown files for each value using the data layer's `write_markdown` function
4. Regenerate the README.md narrative summary
5. Commit changes to git

### SA Seed to Cascade

After SA seeding completes:
1. Commit the SA changes to git
2. Trigger a cascade starting from the SA layer
3. Return the cascade ID to the caller

### Startup to Dependencies

During FastAPI lifespan startup:
1. Create the `AsyncAnthropic` client (or lazy-initialize on first use)
2. Make it available to agent sessions via dependency injection or module-level accessor
3. Initialize data directory (creates structure but not values content)

## Failure Modes

### Anthropic API Errors

- **Rate limiting (429)**: Classified as transient, triggers retry with exponential backoff
- **Server errors (500, 502, 503, 529)**: Classified as transient, triggers retry
- **Authentication errors**: Classified as non-transient, fails immediately with clear error message
- **Context overflow**: Detected from error response, raises `ContextOverflowError`, no retry
- **Network errors**: Classified as transient if connection-related, retry with backoff

### Tool Execution Failures

- **Path outside sandbox**: Tool returns error message to agent, agent can adapt or fail gracefully
- **File not found on read**: Tool returns error, agent can handle (e.g., file doesn't exist yet)
- **Write permission error**: Tool returns error, likely causes agent to fail the task
- **Invalid tool arguments**: Tool returns error describing the problem

### Streaming Interruption

If the stream is interrupted mid-response:
- Partial text already emitted to WebSocket remains visible to users
- The current turn fails, retry logic may attempt again
- Full output accumulator contains partial content

### Agent Produces Invalid Output

- **Values seed output unparseable**: Log error, return failure status, values layer unchanged
- **Generator doesn't use tools**: Agent output captured but no file changes occur — cascade may continue with stale data
- **Critic output unparseable**: Individual critic marked as failed, others may succeed, synthesis proceeds with available results

### Concurrent Access

- **Multiple cascades**: The existing cascade lock prevents concurrent layer modifications
- **Parallel critics**: Read-only operations, safe to run concurrently
- **Parallel evaluations**: Read-only against layer data, safe to run concurrently
- **Seeding during cascade**: Should wait for cascade lock or fail — seeding modifies files

### Missing API Key

If `ANTHROPIC_API_KEY` is not set:
- Agent sessions fail immediately with clear error
- The application should log a warning at startup if the key is missing
- The health check endpoint remains operational (it doesn't require the API)
