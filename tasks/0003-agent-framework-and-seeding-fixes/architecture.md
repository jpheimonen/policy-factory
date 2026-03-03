# Architecture

## Components Affected

### AgentSession (src/policy_factory/agent/session.py)

The core agent execution wrapper needs significant changes:

- **Anthropic SDK integration**: Replace the nonexistent `claude_agent_sdk` with the official `anthropic` Python SDK using the async client
- **Custom agentic loop**: Implement a streaming conversation loop that handles tool calls iteratively until the model signals completion. This preserves real-time token streaming to WebSocket (typewriter effect)
- **Tool execution**: When the model requests tool use, execute the appropriate file operation or let server-side tools (web search) be handled automatically by the API
- **Preserve retry logic**: Keep the existing exponential backoff and transient error classification in `run()`
- **Preserve meditation filter**: Continue passing streamed text through `MeditationFilter` before emitting `AgentTextChunk` events
- **New constructor parameters**: Accept the shared Anthropic client and data directory path

### AgentConfig (src/policy_factory/agent/config.py)

Configuration needs updates for the new SDK:

- **Remove SDK-specific fields**: Drop `cwd`, `max_turns`, `permission_mode` which were Claude Code SDK concepts
- **Add tool configuration**: New field to specify which tools an agent can use (file tools, web search, or none)
- **Add new agent role**: Include `values-seed` role for the values seeding agent with appropriate model defaults
- **Preserve model resolution**: Keep `resolve_model()` function and env var overrides

### File Tools Module (new: src/policy_factory/agent/tools.py)

New module providing file operation tools for agents:

- **Four file tools**: list_files, read_file, write_file, delete_file
- **Sandbox validation**: All paths must resolve within the configured data directory; reject any path traversal attempts
- **Tool definitions**: Provide tool schemas in the format expected by Anthropic's API
- **Read-only subset**: Expose a read-only tool set (list_files, read_file only) for critic agents

### Seed Router (src/policy_factory/server/routers/seed.py)

Endpoint changes for flexible seeding:

- **Remove 409 guard**: SA seeding should be re-runnable; delete the check that rejects seeding when items exist
- **Clear before reseed**: When reseeding, delete existing items in the layer before running the agent
- **Add context parameter**: SA seed endpoint accepts optional human-provided context text to inform the agent's research
- **New values seed endpoint**: Add endpoint to trigger values layer seeding
- **Update status endpoint**: Report both values and SA seeding status with item counts

### Data Initialization (src/policy_factory/data/init.py)

Startup behavior changes:

- **Remove pre-seeded values**: Stop writing the hardcoded descriptive values from `seed_values.py` during initialization
- **Values directory starts empty**: The values layer is populated via explicit seeding, not startup initialization
- **Preserve other initialization**: Keep git repo creation, layer directory creation, and README placeholders

### Values Seed Prompt (new: src/policy_factory/prompts/seed/values.md)

New prompt template for values synthesis:

- **Axiomatic values focus**: Instruct the agent to produce normative statements about what Finland prioritizes, not descriptive facts
- **Tension identification**: Each value should identify which other values it can conflict with
- **No tools needed**: The values agent uses Claude's training knowledge, not web search or file tools
- **Output format**: Specify the expected markdown structure with YAML frontmatter

### Generator Prompt Templates (src/policy_factory/prompts/generators/*.md)

Minor updates to reference tools:

- **Tool-based file access**: Update language from "read all files in directory" to "use the list_files and read_file tools"
- **Preserve structure**: Keep the overall prompt strategy, meditation integration, and output format requirements

### Anthropic Client Management

Shared client initialization:

- **Lifespan initialization**: Create the `AsyncAnthropic` client during FastAPI startup
- **Shared across requests**: All agent sessions use the same client instance for connection pooling
- **Dependency injection**: Make client available via FastAPI dependency injection pattern
- **Graceful handling**: If API key is missing, log warning at startup but don't crash; fail when agent operation is attempted

## New Entities/Endpoints

### POST /api/seed/values

Trigger values layer seeding:

- **Authentication**: Requires authenticated user
- **Behavior**: Clears existing values, runs the values synthesis agent, writes results to data/values/, commits to git
- **Response**: Success status and count of values created
- **Re-runnable**: Can be called multiple times; each call replaces existing values

### Updated POST /api/seed/

SA seeding with enhancements:

- **Request body**: Optional `context` field containing human-provided situational context
- **Behavior**: Clears existing SA items, runs agent with context and web search, writes results, triggers cascade
- **No 409**: Removed the "already seeded" guard

### Updated GET /api/seed/status

Enhanced status reporting:

- **Response fields**: `values_seeded` (boolean), `values_count` (integer), `sa_seeded` (boolean), `sa_count` (integer)
- **Authentication**: Requires authenticated user (existing behavior preserved)

## Integration Points

### Agent Session → Anthropic API

The agent session communicates with Claude via streaming API calls:

1. Session sends messages with system prompt, conversation history, and available tools
2. API streams response tokens and tool use requests
3. Session emits text tokens as `AgentTextChunk` events (filtered through meditation filter)
4. When tool use is requested, session executes the tool and feeds result back
5. Loop continues until model signals end of turn without pending tool calls

### Agent Session → File Tools

File operations flow through the tools module:

1. Model requests tool use with tool name and parameters
2. Session looks up the tool function and validates the operation is allowed for this agent type
3. Tool function validates path is within sandbox
4. Tool executes filesystem operation using existing `layers.py` utilities where applicable
5. Result (success or error) is returned to the model as a tool result message

### Seed Endpoints → Agent Session

Seeding endpoints orchestrate agent runs:

1. Endpoint loads the appropriate prompt template with variable substitution
2. Creates `AgentConfig` with appropriate role and tool configuration
3. Creates `AgentSession` with shared client, event emitter, and context ID
4. Calls `session.run(prompt)` and awaits completion
5. Handles result: check for errors, commit changes to git, trigger cascade if applicable

### Event Emitter → WebSocket

Streaming text flows to connected clients:

1. Agent session emits `AgentTextChunk` events during response streaming
2. Meditation filter suppresses countdown content before emission
3. Event emitter broadcasts to all subscribed handlers
4. WebSocket handler forwards to connected clients for real-time display

### Data Initialization → Values Layer

Startup no longer pre-seeds values:

1. `initialize_data_directory()` creates git repo and layer directories
2. Values directory is created but left empty (only README.md placeholder)
3. Values are populated later via explicit `POST /api/seed/values` call

## Failure Modes

### Missing API Key

- **Symptom**: Agent operations fail with authentication error
- **Detection**: Check for `ANTHROPIC_API_KEY` environment variable at startup
- **Handling**: Log warning during startup; return clear error message when agent operation is attempted without valid key
- **Recovery**: Set the environment variable and restart

### Rate Limiting

- **Symptom**: API returns 429 or rate limit error
- **Detection**: Existing `_is_transient_error()` classification
- **Handling**: Exponential backoff retry (existing logic preserved)
- **Recovery**: Automatic after delay; persistent rate limiting requires waiting or quota increase

### Context Overflow

- **Symptom**: Prompt exceeds model's context window
- **Detection**: API returns context length error
- **Handling**: Raise `ContextOverflowError` without retry
- **Recovery**: Reduce prompt size (fewer layer items, shorter content)

### Tool Execution Failure

- **Symptom**: File tool returns error (path outside sandbox, file not found, permission denied)
- **Detection**: Tool returns error dict instead of success
- **Handling**: Pass error back to model as tool result; model can attempt recovery or report failure
- **Recovery**: Model may try alternative approach or explain the limitation

### Sandbox Escape Attempt

- **Symptom**: Agent attempts to access files outside data directory
- **Detection**: Path validation in tool functions
- **Handling**: Return error to model; do not execute the operation
- **Recovery**: Model receives error and should use valid paths

### Agent Produces Unparseable Output

- **Symptom**: Values seed agent returns output that can't be parsed into individual value documents
- **Detection**: Parsing logic fails to extract expected structure
- **Handling**: Return error response indicating parse failure
- **Recovery**: May require prompt refinement or manual retry

### Network Errors

- **Symptom**: Connection timeouts, DNS failures, SSL errors
- **Detection**: Exception during API call
- **Handling**: Classified as transient; retry with backoff
- **Recovery**: Automatic if network recovers

### Concurrent Seeding

- **Symptom**: Multiple seed operations run simultaneously
- **Detection**: Not explicitly guarded currently
- **Handling**: Last write wins for files; git commit may conflict
- **Mitigation**: UI should prevent concurrent seed triggers; backend could add locking if needed
