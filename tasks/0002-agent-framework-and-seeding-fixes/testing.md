# Testing Plan

## Unit Tests

### AgentSession Core Behavior

- [ ] Verify that a successful single-turn agent run (no tool calls) returns an AgentResult with the expected text content
- [ ] Verify that multi-turn conversations work correctly when the agent makes tool calls — the session should execute tools and continue until the agent stops
- [ ] Verify that text content is emitted as AgentTextChunk events during streaming, not batched at the end of each turn
- [ ] Verify that the meditation filter suppresses countdown content (numbers 10 through 1 with reflections) from streamed events while preserving it in the full_output field
- [ ] Verify that AgentResult captures the complete unfiltered output including meditation content
- [ ] Verify that AgentResult.is_error is True when the agent session encounters a terminal failure
- [ ] Verify that the session terminates the loop when the model returns end_turn with no pending tool calls

### Retry and Error Handling

- [ ] Verify that rate limit errors (429) trigger retry with exponential backoff
- [ ] Verify that server errors (500, 502, 503, 529) trigger retry with exponential backoff
- [ ] Verify that authentication errors do not trigger retry and fail immediately
- [ ] Verify that context overflow errors raise ContextOverflowError and do not retry
- [ ] Verify that after MAX_RETRIES attempts, the session raises AgentError with appropriate context
- [ ] Verify that the delay between retries follows exponential backoff (base delay doubled each attempt)
- [ ] Verify that non-transient errors (generic exceptions that don't match transient patterns) are not retried

### File Tools

- [ ] Verify that list_files returns markdown filenames from a layer directory, excluding README.md
- [ ] Verify that list_files returns an empty list for an empty directory
- [ ] Verify that list_files rejects paths outside the data directory sandbox and returns an error
- [ ] Verify that read_file returns the full content of a markdown file including frontmatter
- [ ] Verify that read_file returns an appropriate error when the file does not exist
- [ ] Verify that read_file rejects paths outside the data directory sandbox
- [ ] Verify that write_file creates a new file with the provided content
- [ ] Verify that write_file overwrites an existing file with the provided content
- [ ] Verify that write_file creates parent directories if they don't exist (within sandbox)
- [ ] Verify that write_file rejects paths outside the data directory sandbox
- [ ] Verify that delete_file removes an existing file
- [ ] Verify that delete_file succeeds silently when the file doesn't exist (idempotent)
- [ ] Verify that delete_file rejects paths outside the data directory sandbox
- [ ] Verify that path traversal attempts (using ../) are blocked by all file tools

### Tool Configuration

- [ ] Verify that generator agent configs include list_files, read_file, write_file, and delete_file tools
- [ ] Verify that critic agent configs include only list_files and read_file tools (no write or delete)
- [ ] Verify that synthesis and classifier agent configs include no tools
- [ ] Verify that heartbeat skim/triage agent configs include only web_search
- [ ] Verify that heartbeat SA update agent configs include file tools plus web_search
- [ ] Verify that SA seed agent configs include file tools plus web_search
- [ ] Verify that values seed agent configs include no tools

### AgentConfig

- [ ] Verify that resolve_model returns the default model for each agent role
- [ ] Verify that resolve_model respects environment variable overrides for each role
- [ ] Verify that resolve_model raises an error for unknown agent roles

### Meditation Filter

- [ ] Verify that the filter suppresses text during the countdown phase (numbers 10 down to 1)
- [ ] Verify that the filter starts streaming text after the countdown completes
- [ ] Verify that the filter handles partial chunks that split number boundaries correctly
- [ ] Verify that the filter passes through all text when no meditation pattern is detected within the threshold
- [ ] Verify that the filter can be reset for reuse

## Integration Tests

### Agent Session with Mocked SDK

- [ ] Verify end-to-end flow: session receives prompt, calls mocked Anthropic API, streams response, emits events, returns AgentResult
- [ ] Verify that tool calls in the response trigger tool execution and continuation of the conversation
- [ ] Verify that the session correctly handles mixed server-side tools (web_search) and client-side tools (file operations)
- [ ] Verify that file tool operations actually read/write files in the data directory during a session

### Values Seeding Flow

- [ ] Verify that calling the values seed endpoint triggers an agent call and returns success
- [ ] Verify that values seeding clears existing values files before writing new ones
- [ ] Verify that values seeding writes markdown files with correct frontmatter structure
- [ ] Verify that values seeding regenerates the README.md narrative summary
- [ ] Verify that values seeding commits changes to git
- [ ] Verify that values seeding can be called multiple times without error (no 409)
- [ ] Verify that values seeding requires authentication

### SA Seeding Flow

- [ ] Verify that calling the SA seed endpoint no longer returns 409 when SA layer already has items
- [ ] Verify that SA seeding clears existing SA files before writing new ones
- [ ] Verify that SA seeding accepts and incorporates optional context from the request body
- [ ] Verify that SA seeding triggers a cascade after completion
- [ ] Verify that SA seeding requires authentication

### Seed Status

- [ ] Verify that the status endpoint returns values layer item count
- [ ] Verify that the status endpoint returns SA layer item count
- [ ] Verify that the status endpoint correctly reflects empty layers after initialization

### Data Initialization

- [ ] Verify that initialize_data_directory creates the git repo on first run
- [ ] Verify that initialize_data_directory creates all five layer directories
- [ ] Verify that initialize_data_directory creates README.md placeholders in each layer
- [ ] Verify that initialize_data_directory does NOT write pre-seeded values (values directory starts empty)
- [ ] Verify that initialize_data_directory is idempotent (safe to call multiple times)

### Cascade Integration

- [ ] Verify that cascades work correctly with the new AgentSession implementation (mock at session.run level)
- [ ] Verify that critics run in parallel and all complete (or fail gracefully)
- [ ] Verify that generators can read and write layer files via tools

### Heartbeat Integration

- [ ] Verify that heartbeat tier 1 (skim) works with web_search tool only
- [ ] Verify that heartbeat tier 3 (SA update) works with both file tools and web_search
- [ ] Verify that heartbeat escalation logic continues to function correctly

## Browser/E2E Tests

### Values Seeding

- [ ] Navigate to admin panel, trigger values seeding, verify success feedback is shown
- [ ] After values seeding, navigate to values layer view and verify values are displayed
- [ ] Trigger values seeding again, verify it succeeds and values are replaced

### SA Seeding

- [ ] Navigate to admin panel, trigger SA seeding, verify success feedback is shown
- [ ] Trigger SA seeding with context provided, verify it succeeds
- [ ] After SA seeding, verify cascade is triggered (cascade status indicator updates)

### Cascade Viewer

- [ ] Trigger a cascade and verify that streaming text appears in real-time (typewriter effect preserved)
- [ ] Verify that meditation content is not visible in the streamed text
- [ ] Verify that agent labels update as different agents run

### Status Display

- [ ] Verify that seed status shows values and SA item counts
- [ ] Verify that seed status updates after seeding operations complete

## Manual Testing

**None** - all verification must be automated.
