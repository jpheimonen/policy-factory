# Testing Plan

## Unit Tests

### File Tools Module

- [ ] Path validation accepts paths within the data directory
- [ ] Path validation rejects paths containing `../` that escape the sandbox
- [ ] Path validation rejects absolute paths outside the data directory
- [ ] Path validation rejects symlinks that resolve outside the sandbox
- [ ] list_files returns markdown filenames in a directory, excluding README.md
- [ ] list_files returns empty list for empty directory
- [ ] list_files returns error for paths outside sandbox
- [ ] list_files returns error when path is not a directory
- [ ] read_file returns file content for existing file
- [ ] read_file returns error for nonexistent file
- [ ] read_file returns error for paths outside sandbox
- [ ] write_file creates new file with content
- [ ] write_file overwrites existing file
- [ ] write_file creates parent directories if they don't exist
- [ ] write_file returns error for paths outside sandbox
- [ ] delete_file removes existing file
- [ ] delete_file succeeds silently for nonexistent file (idempotent)
- [ ] delete_file returns error for paths outside sandbox
- [ ] Tool definition structures contain required fields (name, description, input_schema)
- [ ] Read-only tool set contains only list_files and read_file

### AgentSession

- [ ] Single-turn conversation (no tool calls) returns expected text
- [ ] Multi-turn conversation with tool calls executes tools and continues until completion
- [ ] Text deltas are emitted as AgentTextChunk events during streaming
- [ ] Meditation filter suppresses countdown content from emitted events
- [ ] Full output captures all text including meditation content
- [ ] Rate limit errors trigger retry with exponential backoff
- [ ] Server errors (500, 502, 503, 529) trigger retry
- [ ] Authentication errors fail immediately without retry
- [ ] Context overflow errors raise ContextOverflowError without retry
- [ ] Max retries exceeded raises AgentError
- [ ] Conversation loop terminates when model signals end_turn without pending tool calls
- [ ] Tool results are passed back to the model correctly
- [ ] Unknown tool names return error result to model

### AgentConfig

- [ ] resolve_model returns default model for each known agent role
- [ ] resolve_model respects environment variable overrides
- [ ] resolve_model raises error for unknown roles
- [ ] New values-seed role has appropriate default model
- [ ] Tool configuration returns file tools for generator role
- [ ] Tool configuration returns read-only tools for critic role
- [ ] Tool configuration returns web search for heartbeat-skim and heartbeat-triage roles
- [ ] Tool configuration returns file tools plus web search for heartbeat-sa-update and seed roles
- [ ] Tool configuration returns empty list for values-seed role (no tools needed)
- [ ] AgentConfig initializes with role and resolves model and tools automatically

### Meditation Filter (existing tests preserved)

- [ ] Existing meditation filter tests continue to pass unchanged

### Transient Error Classification

- [ ] 500 internal server error is classified as transient
- [ ] 502, 503, 529 errors are classified as transient
- [ ] "overloaded" message is classified as transient
- [ ] "rate limit" message is classified as transient
- [ ] Authentication errors are not classified as transient
- [ ] Context overflow errors are not classified as transient
- [ ] Generic errors are not classified as transient

## Integration Tests

### Values Seeding Flow

- [ ] POST /api/seed/values requires authentication
- [ ] Values seeding creates markdown files in data/values directory
- [ ] Values seeding clears existing values before writing new ones (re-runnable)
- [ ] Values seeding returns count of values created
- [ ] Values seeding commits changes to git
- [ ] Values seeding with agent error returns appropriate error response

### SA Seeding Flow

- [ ] POST /api/seed/ no longer returns 409 when SA layer has items
- [ ] SA seeding clears existing SA items before writing new ones
- [ ] SA seeding accepts optional context in request body
- [ ] SA seeding incorporates provided context into agent prompt
- [ ] SA seeding works without context (backward compatible)
- [ ] SA seeding triggers cascade after successful completion
- [ ] SA seeding returns count of items created and cascade ID
- [ ] SA seeding requires authentication

### Seed Status Endpoint

- [ ] GET /api/seed/status returns values_seeded boolean and values_count
- [ ] GET /api/seed/status returns sa_seeded boolean and sa_count
- [ ] Status correctly reflects empty layers after initialization
- [ ] Status correctly reflects populated layers after seeding

### Data Initialization

- [ ] initialize_data_directory creates git repository
- [ ] initialize_data_directory creates all five layer directories
- [ ] initialize_data_directory creates README.md placeholders in each layer
- [ ] initialize_data_directory does NOT write pre-seeded values
- [ ] Values directory is empty after initialization (only README.md)
- [ ] Initialization is idempotent (safe to call multiple times)

### Cascade Integration

- [ ] Cascade runs successfully after SA seeding
- [ ] Generator agents can use file tools to write layer content
- [ ] Critic agents receive read-only tools and cannot write files
- [ ] Streaming text appears during cascade execution

### Anthropic Client Management

- [ ] Shared client is created during FastAPI startup
- [ ] Missing API key logs warning but does not crash startup
- [ ] Agent operations with missing API key return clear error
- [ ] Multiple concurrent agent sessions share the same client

## Browser/E2E Tests

### Admin Panel

- [ ] Seed status displays correctly showing values and SA counts
- [ ] Triggering values seeding shows progress and completes
- [ ] Triggering SA seeding with context field shows progress and completes
- [ ] Re-seeding values replaces existing values
- [ ] Re-seeding SA replaces existing SA items

### Cascade Viewer

- [ ] Streaming text appears in real-time during agent execution
- [ ] Meditation countdown content is not visible in streamed output
- [ ] Multiple agent phases (generation, critics, synthesis) display correctly

### Layer Views

- [ ] Values layer shows items after seeding
- [ ] SA layer shows items after seeding
- [ ] Items display correct titles from frontmatter

## Manual Testing

**None** - all verification must be automated.
