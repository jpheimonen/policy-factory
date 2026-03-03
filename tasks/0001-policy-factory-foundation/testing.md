# Testing Plan

## Unit Tests

### Project Foundation

- [ ] The CLI entry point loads .env files from multiple locations (current directory, platform root, user config dir) and environment variables are available after loading
- [ ] The port auto-detection utility finds an available port and returns it
- [ ] The FastAPI app factory creates an app with all routers registered and the WebSocket endpoint accessible
- [ ] The SPA fallback route returns index.html for paths not matching API routes or static files
- [ ] Static files from the dist directory are served correctly at their expected paths

### Authentication — Store Layer

- [ ] Creating a user hashes the password with bcrypt and stores email, hashed password, role, and created_at
- [ ] Getting a user by email returns the correct user record when the user exists
- [ ] Getting a user by email returns None or raises when the user does not exist
- [ ] Listing users returns all users with their metadata (excluding hashed passwords from the response)
- [ ] Deleting a user removes them from the database
- [ ] Deleting a non-existent user is handled gracefully (no error, or appropriate error)

### Authentication — JWT and Auth Logic

- [ ] Login with correct email and password returns a valid JWT containing the user's email and role
- [ ] Login with incorrect password is rejected
- [ ] Login with non-existent email is rejected
- [ ] The JWT token contains an expiry time and can be decoded to extract user claims
- [ ] An expired JWT is rejected by the auth dependency
- [ ] A malformed JWT (invalid signature, corrupted payload) is rejected by the auth dependency
- [ ] The `get_current_user` dependency extracts the user from a valid Authorization header
- [ ] The `get_current_user` dependency returns 401 when no Authorization header is present
- [ ] The `require_admin` dependency allows admin users through
- [ ] The `require_admin` dependency rejects non-admin users with 403
- [ ] The first user to register is assigned the admin role automatically
- [ ] Registration after the first user requires an admin JWT (non-admin or unauthenticated registration is rejected)
- [ ] Token refresh returns a new valid JWT when given a still-valid token
- [ ] Token refresh rejects an expired token

### Authentication — WebSocket

- [ ] A WebSocket connection with a valid JWT query parameter is accepted
- [ ] A WebSocket connection with an invalid JWT query parameter is rejected
- [ ] A WebSocket connection with no JWT query parameter is rejected
- [ ] A WebSocket connection with an expired JWT is rejected

### Data Layer — Markdown File Utilities

- [ ] Reading a markdown file with YAML frontmatter returns the frontmatter as a dict and the body as a string
- [ ] Reading a markdown file without YAML frontmatter returns an empty frontmatter dict and the full content as body
- [ ] Reading a non-existent file returns an appropriate error
- [ ] Writing a markdown file serializes frontmatter as YAML and body as markdown content, producing a valid file
- [ ] Writing then reading a file round-trips correctly (frontmatter and body are preserved)
- [ ] Listing items in a layer directory returns all .md files except README.md, with frontmatter metadata for each
- [ ] Listing items in an empty layer directory returns an empty list
- [ ] Deleting an item removes the file from the directory
- [ ] Reading the narrative summary returns the contents of README.md in the layer directory
- [ ] Writing the narrative summary updates README.md in the layer directory
- [ ] Cross-layer reference resolution correctly finds items that reference a given item (forward references)
- [ ] Cross-layer reference resolution correctly finds items that a given item references (backward references)
- [ ] Cross-layer reference resolution returns empty lists when no references exist

### Data Layer — Git Operations

- [ ] Auto-initialization creates a new git repo in the data directory when none exists
- [ ] Auto-initialization creates all five layer subdirectories
- [ ] Auto-initialization writes pre-seeded values files in the values directory
- [ ] Auto-initialization does nothing if the data directory and git repo already exist
- [ ] Committing changes creates a git commit with the provided descriptive message
- [ ] Retrieving recent history for a layer directory returns commits that affected files in that directory, with timestamps and messages
- [ ] Retrieving history for a directory with no commits returns an empty list

### SQLite Store — Schema and Initialization

- [ ] Database initialization creates all required tables (users, ideas, scores, critic results, cascade runs, feedback memos, heartbeat runs, agent runs)
- [ ] Database initialization sets WAL mode
- [ ] Database initialization is idempotent (running it twice does not error or duplicate tables)
- [ ] Migrations (ALTER TABLE operations) are applied cleanly on existing databases

### SQLite Store — Idea Mixin

- [ ] Creating an idea stores text, source (human/AI), optional target objective, submission timestamp, and sets status to pending
- [ ] Getting an idea by ID returns the correct record
- [ ] Listing ideas returns all ideas, ordered by submission timestamp by default
- [ ] Listing ideas with status filter returns only ideas matching the specified status
- [ ] Listing ideas with score sorting returns ideas ordered by their overall score
- [ ] Updating idea status transitions the status correctly (pending → evaluating → evaluated)
- [ ] Updating idea status to an invalid transition is handled gracefully

### SQLite Store — Score Mixin

- [ ] Storing 6-axis scores for an idea creates a score record linked to the idea
- [ ] Retrieving scores for an idea returns all 6 axis values
- [ ] Storing critic assessments creates one record per critic perspective, linked to the idea
- [ ] Retrieving critic assessments for an idea returns all 6 assessments
- [ ] Storing the synthesis assessment creates a record linked to the idea
- [ ] Scores, critic assessments, and synthesis can all be retrieved together for a single idea

### SQLite Store — Cascade Mixin

- [ ] Creating a cascade record stores trigger source, starting layer, and sets status to queued
- [ ] Acquiring the cascade lock succeeds when no lock is held and returns the cascade ID
- [ ] Acquiring the cascade lock fails when a lock is already held and the cascade is added to the queue
- [ ] Releasing the cascade lock makes the lock available for the next cascade
- [ ] Checking the lock status correctly reports whether a cascade is running
- [ ] Updating cascade progress changes the current layer and step
- [ ] Updating cascade status transitions correctly through valid states (queued → running → completed/paused/failed/cancelled)
- [ ] The cascade queue is ordered FIFO
- [ ] Retrieving the cascade queue returns all queued cascades in order
- [ ] Retrieving the current cascade status returns the running cascade's progress, or idle if none is running

### SQLite Store — Feedback Memo Mixin

- [ ] Creating a feedback memo stores source layer, target layer, content, referenced items, and sets status to pending
- [ ] Listing pending memos for a target layer returns only memos with pending status for that layer
- [ ] Updating memo status to accepted changes the status
- [ ] Updating memo status to dismissed changes the status
- [ ] Dismissed and accepted memos are excluded from the pending list

### SQLite Store — Heartbeat Mixin

- [ ] Recording a heartbeat run stores timestamp, highest tier reached, items flagged, and actions taken
- [ ] Retrieving recent heartbeat history returns runs in reverse chronological order
- [ ] The cascade_run_id field is set when a heartbeat triggers a cascade, and null otherwise

### SQLite Store — Agent Run Mixin

- [ ] Recording an agent run stores agent type, model, target layer, start/end times, success flag, and optional error message
- [ ] Retrieving agent runs for a cascade returns all runs associated with that cascade ID
- [ ] Retrieving recent agent runs returns runs in reverse chronological order

### Agent Framework — Session Wrapper

- [ ] The session wrapper accepts a model configuration and passes it to the Claude SDK client
- [ ] The session wrapper accepts a working directory and passes it to the Claude SDK client
- [ ] The prompt construction assembles meditation preamble + agent prompt template + dynamic context variables
- [ ] Template variables are correctly substituted into the prompt template
- [ ] The meditation filter detects the start of meditation content (countdown from 10) and suppresses it from streamed output
- [ ] The meditation filter detects the end of meditation content and begins streaming post-meditation content
- [ ] When meditation content cannot be detected (no countdown pattern), all content is streamed (conservative approach)
- [ ] The full unfiltered output (including meditation) is captured for logging regardless of filtering
- [ ] Transient errors (500, 502, 503, 529, overloaded, rate limit) trigger a retry
- [ ] Non-transient errors (auth failure, context overflow) are not retried
- [ ] Retry uses exponential backoff (delay increases with each attempt)
- [ ] After 3 failed retries, the error is propagated to the caller
- [ ] Agent output chunks are emitted as typed events through the EventEmitter

### Agent Framework — Prompt Loading

- [ ] Loading a prompt by category and name returns the content of the correct markdown file
- [ ] Loading a prompt with template variables substitutes them into the content
- [ ] Loading a non-existent prompt raises a clear error
- [ ] Loading a section by name returns the content of the section file
- [ ] Loading multiple sections concatenates them with appropriate separators
- [ ] All expected prompt files exist in the prompts directory (one per generator, one per critic, meditation preamble, synthesis, classifier, heartbeat tiers, seed, idea generation/evaluation)

### Cascade Orchestrator

- [ ] Triggering a cascade when no lock is held acquires the lock and starts the cascade
- [ ] Triggering a cascade when a lock is held adds the cascade to the queue
- [ ] A cascade starting from values processes all 5 layers in order (values → SA → strategic → tactical → policies)
- [ ] A cascade starting from situational-awareness processes 4 layers (SA → strategic → tactical → policies)
- [ ] A cascade starting from policies processes only 1 layer (policies only)
- [ ] Each layer in the cascade goes through generation → critics → synthesis in sequence
- [ ] After completing the topmost layer, the cascade lock is released
- [ ] After completing a cascade, the next queued cascade starts automatically if the queue is non-empty
- [ ] When an agent fails after 3 retries, the cascade pauses with error info recorded
- [ ] A paused cascade holds the lock (preventing other cascades from starting)
- [ ] Resuming a paused cascade retries the failed step
- [ ] Cancelling a paused cascade releases the lock and discards remaining steps
- [ ] Cancelling a queued cascade removes it from the queue
- [ ] Progress events are emitted at each step transition (layer change, step change, agent start/end)
- [ ] File changes made by generation agents are auto-committed to the data git repo after each layer

### Critic Runner

- [ ] Running critics launches all 6 critic agents
- [ ] All 6 critic agents receive the correct layer content
- [ ] Each critic agent uses its specific system prompt
- [ ] Critic results are stored in the database linked to the cascade run and layer
- [ ] The synthesis agent receives all 6 critic outputs
- [ ] The synthesis result is stored in the database linked to the cascade run and layer
- [ ] If one critic fails, the remaining critics still complete (partial failure handling)

### Idea Pipeline

- [ ] Submitting a human idea creates an idea record with source "human" and status "pending"
- [ ] Triggering AI idea generation creates idea records with source "AI"
- [ ] Evaluating an idea transitions its status from pending to evaluating, then to evaluated on completion
- [ ] Evaluation produces 6-axis scores stored in the database
- [ ] Evaluation runs all 6 critics against the idea
- [ ] Evaluation runs the synthesis agent and stores the result
- [ ] Multiple idea evaluations can run concurrently without interfering with each other
- [ ] Idea evaluation does not acquire the cascade lock

### Heartbeat System

- [ ] Tier 1 runs the news skim agent with the cheapest model
- [ ] Tier 1 returning "nothing noteworthy" logs the run and stops (Tier 2 is not triggered)
- [ ] Tier 1 flagging items triggers Tier 2
- [ ] Tier 2 returning no actionable items logs the run and stops (Tier 3 is not triggered)
- [ ] Tier 2 recommending updates triggers Tier 3
- [ ] Tier 3 running the SA update agent triggers Tier 4 after completion
- [ ] Tier 4 triggers a standard cascade from the SA layer
- [ ] Each heartbeat run is logged with the highest tier reached
- [ ] The heartbeat can be triggered manually via the API endpoint
- [ ] APScheduler fires the heartbeat on the configured schedule

### Input Classifier

- [ ] The classifier agent receives the user's free-text input
- [ ] The classifier returns a target layer and an explanation of why
- [ ] After classification, the target layer's generation agent is triggered with the user input as context
- [ ] After the generation agent completes, an upward cascade is triggered from the target layer

### Event System

- [ ] The EventEmitter can have multiple handlers subscribed
- [ ] Emitting an event calls all subscribed handlers
- [ ] Async handlers are properly awaited
- [ ] Unsubscribing a handler prevents it from receiving further events
- [ ] Each event type serializes to a dict with the correct event_type field
- [ ] Event serialization handles datetime fields correctly (ISO format)

### WebSocket — Connection Manager

- [ ] The connection manager tracks connected clients
- [ ] Connecting a client adds it to the tracked set
- [ ] Disconnecting a client removes it from the tracked set
- [ ] Broadcasting a message sends it to all connected clients
- [ ] Broadcasting to no connected clients does not error
- [ ] A disconnected client is cleaned up gracefully (no errors from sending to a closed connection)

### REST API — Layer Endpoints

- [ ] GET `/api/layers/` returns all 5 layers with item counts, last updated timestamps, and narrative previews
- [ ] GET `/api/layers/:slug/items` returns all items for a valid layer slug with frontmatter metadata
- [ ] GET `/api/layers/:slug/items` returns 404 for an invalid layer slug
- [ ] GET `/api/layers/:slug/items/:filename` returns the full item (frontmatter + body) for a valid filename
- [ ] GET `/api/layers/:slug/items/:filename` returns 404 for a non-existent filename
- [ ] PUT `/api/layers/:slug/items/:filename` updates the item file and returns the updated item
- [ ] POST `/api/layers/:slug/items` creates a new item file and returns 201
- [ ] POST `/api/layers/:slug/items` rejects a request with a filename that already exists
- [ ] DELETE `/api/layers/:slug/items/:filename` removes the file and returns 204
- [ ] GET `/api/layers/:slug/summary` returns the README.md content for the layer
- [ ] GET `/api/layers/:slug/items/:filename/references` returns cross-layer references
- [ ] All layer endpoints return 401 without a valid JWT

### REST API — Auth Endpoints

- [ ] POST `/api/auth/register` creates the first user as admin and returns a JWT
- [ ] POST `/api/auth/register` without auth after the first user exists returns 403
- [ ] POST `/api/auth/register` with admin auth after the first user exists creates a regular user
- [ ] POST `/api/auth/login` with valid credentials returns a JWT
- [ ] POST `/api/auth/login` with invalid credentials returns 401
- [ ] POST `/api/auth/refresh` with a valid token returns a new JWT
- [ ] POST `/api/auth/refresh` with an expired token returns 401

### REST API — User Endpoints

- [ ] GET `/api/users/` returns the user list when called by an admin
- [ ] GET `/api/users/` returns 403 when called by a non-admin
- [ ] POST `/api/users/` creates a new user when called by an admin
- [ ] POST `/api/users/` returns 403 when called by a non-admin
- [ ] DELETE `/api/users/:id` deletes the user when called by an admin
- [ ] DELETE `/api/users/:id` returns 403 when called by a non-admin
- [ ] An admin cannot delete themselves

### REST API — Cascade Endpoints

- [ ] POST `/api/cascade/trigger` starts a cascade when no lock is held
- [ ] POST `/api/cascade/trigger` queues a cascade when a lock is held and returns the queue position
- [ ] GET `/api/cascade/status` returns the current cascade's progress when one is running
- [ ] GET `/api/cascade/status` returns idle status when no cascade is running
- [ ] GET `/api/cascade/status` includes the queue depth and queued cascade info
- [ ] POST `/api/cascade/resume` resumes a paused cascade
- [ ] POST `/api/cascade/resume` returns an error when no cascade is paused
- [ ] POST `/api/cascade/cancel` cancels a paused cascade and releases the lock
- [ ] POST `/api/cascade/cancel` removes a queued cascade from the queue
- [ ] All cascade endpoints return 401 without a valid JWT

### REST API — Idea Endpoints

- [ ] POST `/api/ideas/` creates a new idea with source "human" and returns the created idea
- [ ] GET `/api/ideas/` returns all ideas with default ordering
- [ ] GET `/api/ideas/` with status filter returns only matching ideas
- [ ] GET `/api/ideas/` with score sorting returns ideas ordered by score
- [ ] GET `/api/ideas/:id` returns the idea with its scores, critic results, and synthesis
- [ ] GET `/api/ideas/:id` returns 404 for a non-existent idea
- [ ] POST `/api/ideas/generate` triggers AI idea generation (async, returns immediately with acknowledgment)
- [ ] All idea endpoints return 401 without a valid JWT

### REST API — Heartbeat Endpoints

- [ ] POST `/api/heartbeat/trigger` triggers a manual heartbeat run (async, returns immediately)
- [ ] GET `/api/heartbeat/log` returns recent heartbeat runs in reverse chronological order
- [ ] All heartbeat endpoints return 401 without a valid JWT

### REST API — Activity Endpoints

- [ ] GET `/api/activity/` returns events in chronological order
- [ ] GET `/api/activity/` with type filter returns only matching event types
- [ ] GET `/api/activity/` with layer filter returns only events related to that layer
- [ ] GET `/api/activity/` supports pagination
- [ ] All activity endpoints return 401 without a valid JWT

### REST API — History Endpoints

- [ ] GET `/api/history/:slug` returns recent git commits for the layer directory
- [ ] GET `/api/history/:slug` returns 404 for an invalid layer slug
- [ ] All history endpoints return 401 without a valid JWT

### REST API — Health and Seed Endpoints

- [ ] GET `/api/health/check` returns a successful response with tool availability info
- [ ] POST `/api/seed/run` triggers SA population (async, returns immediately)
- [ ] POST `/api/seed/run` returns 401 without a valid JWT

### Frontend — Theme System

- [ ] The dark theme object and light theme object share the same token structure (same keys, different values)
- [ ] System preference detection correctly identifies dark/light preference
- [ ] User theme override persists to localStorage and is restored on reload
- [ ] Toggling the theme updates all themed components immediately (no stale colors)
- [ ] Each layer has a distinct, visually distinguishable identity color in both themes

### Frontend — i18n

- [ ] No component contains hardcoded display strings (every visible string uses a translation key)
- [ ] All translation keys used in components exist in the English translation file
- [ ] Adding a new locale file makes the app render in that locale without component code changes

### Frontend — Auth Store

- [ ] Login action stores the JWT and user info in the store
- [ ] Login action persists the JWT to localStorage
- [ ] Logout action clears the JWT from the store and localStorage
- [ ] On app load, the auth store restores the JWT from localStorage if present
- [ ] Token refresh updates the stored JWT
- [ ] The auth store exposes the current user's role (admin/user)

### Frontend — Layer Store

- [ ] Fetching layers populates the store with all 5 layers and their metadata
- [ ] Fetching items for a layer populates the store with item data
- [ ] The store updates when new layer data is fetched (replaces stale data)

### Frontend — Cascade Store

- [ ] The store initializes with idle status
- [ ] Receiving a cascade_started WebSocket event transitions status to running
- [ ] Receiving progress events updates the current layer and step
- [ ] Receiving a cascade_completed event transitions status back to idle
- [ ] Receiving a cascade_failed event transitions status to paused with error info
- [ ] Receiving a cascade_queued event increments the queue depth
- [ ] Agent text chunk events are accumulated for the live streaming display

### Frontend — Idea Store

- [ ] Submitting an idea adds it to the store optimistically (before server confirmation)
- [ ] Fetching ideas populates the store with the idea list
- [ ] Evaluation progress events update the idea's status in real-time
- [ ] Filtering by status returns only matching ideas
- [ ] Sorting by score orders ideas correctly

### Frontend — WebSocket Hook

- [ ] The hook connects to `/ws?token=<JWT>` on mount
- [ ] The hook disconnects on unmount
- [ ] The hook auto-reconnects with exponential backoff on unexpected disconnect
- [ ] The hook deduplicates events by ID
- [ ] The hook replays missed events from the REST endpoint on reconnect
- [ ] The hook dispatches incoming events to the correct zustand stores

---

## Integration Tests

### Auth Flow End-to-End

- [ ] Register the first user, verify they are admin, log in with their credentials, and access a protected endpoint with the JWT
- [ ] As admin, create a second user, log in as that user, and verify they are non-admin
- [ ] As a non-admin user, verify that admin-only endpoints (user creation, user deletion) return 403
- [ ] Verify that all protected endpoints return 401 when called without a JWT

### Data Layer Round-Trip

- [ ] Write a layer item via the API, then read it back and verify frontmatter and body match
- [ ] Update a layer item via the API, then verify the updated content is returned on subsequent read
- [ ] Delete a layer item via the API, then verify it no longer appears in the item listing
- [ ] Verify that writing an item and then listing items includes the new item with correct metadata
- [ ] Verify that writing an item triggers a git commit in the data repo with a descriptive message
- [ ] Verify cross-layer references: create items in two different layers that reference each other, then verify the reference endpoint returns bidirectional references

### First-Run Initialization

- [ ] Start the server with no data directory and verify: data directory is created, git repo is initialized, all 5 layer subdirectories exist, pre-seeded values files exist in the values directory
- [ ] Start the server with an existing data directory and verify it is not overwritten

### Cascade Orchestrator End-to-End (with mocked agents)

- [ ] Trigger a cascade from the values layer and verify it processes all layers in order up to policies, running generation + critics + synthesis at each layer
- [ ] Trigger a cascade from the policies layer and verify it only processes the policies layer
- [ ] Trigger two cascades simultaneously and verify the second one queues behind the first
- [ ] Simulate an agent failure and verify the cascade pauses with correct error state
- [ ] Resume a paused cascade and verify it continues from the failed step
- [ ] Cancel a paused cascade and verify the lock is released and the queue starts
- [ ] Verify that cascade progress events are emitted at each step and received by a WebSocket client

### Critic System End-to-End (with mocked agents)

- [ ] Run the critic system against a layer and verify all 6 critic assessments are stored
- [ ] Verify the synthesis agent receives all 6 critic outputs and its result is stored
- [ ] Verify that critics run in parallel (not sequentially) by checking timing

### Idea Pipeline End-to-End (with mocked agents)

- [ ] Submit an idea via the API, trigger its evaluation, and verify scores, critic results, and synthesis are stored
- [ ] Verify that idea evaluation does not acquire the cascade lock
- [ ] Trigger AI idea generation and verify new ideas are created in the database
- [ ] Run two idea evaluations concurrently and verify both complete successfully

### Heartbeat Tier Escalation (with mocked agents)

- [ ] Simulate Tier 1 returning "nothing noteworthy" and verify Tier 2 is not triggered, run is logged
- [ ] Simulate Tier 1 flagging items and Tier 2 returning no actionable items — verify Tier 3 is not triggered, run is logged with highest tier = 2
- [ ] Simulate Tiers 1-2 escalating and Tier 3 updating SA — verify Tier 4 triggers a cascade and the run is logged with highest tier = 4

### Input Classification End-to-End (with mocked agents)

- [ ] Submit free-text input via the cascade trigger endpoint, verify the classifier determines a target layer, and verify a cascade is triggered from that layer

### WebSocket Event Flow

- [ ] Connect a WebSocket client with a valid JWT, trigger a cascade, and verify the client receives cascade lifecycle events (started, progress, completed)
- [ ] Connect a WebSocket client, disconnect it mid-cascade, reconnect, and verify missed events are replayed without duplicates
- [ ] Connect a WebSocket client with an invalid JWT and verify the connection is rejected

### Event Persistence and Activity Feed

- [ ] Trigger a cascade, then fetch the activity endpoint and verify cascade events appear in the response
- [ ] Submit an idea and trigger evaluation, then verify idea events appear in the activity feed
- [ ] Verify activity endpoint filtering by event type returns only matching events
- [ ] Verify activity endpoint filtering by layer returns only events for that layer

### Frontend-Backend Integration

- [ ] The frontend login page submits credentials, receives a JWT, stores it, and redirects to the home page
- [ ] The home page fetches and displays all 5 layers with correct metadata
- [ ] Navigating to a layer detail view shows items fetched from the API
- [ ] The input panel sends text to the cascade trigger endpoint and the cascade viewer shows progress via WebSocket

---

## Browser/E2E Tests (for UI changes)

### Authentication Flow

- [ ] Visiting the app for the first time shows the registration page
- [ ] Registering the first user creates an admin account and redirects to the home page
- [ ] Logging out and visiting any protected page redirects to the login page
- [ ] Logging in with valid credentials redirects to the home page
- [ ] Logging in with invalid credentials shows an error message

### Stack Overview (Home Page)

- [ ] The home page displays all 5 layer cards in a vertical stack from bottom to top
- [ ] Each layer card shows the layer name, item count, last updated timestamp, and narrative summary preview
- [ ] Clicking a layer card navigates to that layer's detail view
- [ ] The input panel is visible and accepts text input
- [ ] Submitting text in the input panel triggers a cascade (visible in the UI as cascade status change)

### Layer Detail View

- [ ] The layer detail page shows the narrative summary at the top
- [ ] The layer detail page shows all items as cards with key metadata
- [ ] Clicking an item card navigates to the item detail view
- [ ] The refresh button triggers a layer regeneration (cascade viewer becomes active)
- [ ] Feedback memos are displayed with accept and dismiss buttons
- [ ] Accepting a feedback memo removes it from the list
- [ ] Dismissing a feedback memo removes it from the list

### Item Detail and Editing

- [ ] The item detail page renders frontmatter fields and markdown body
- [ ] Cross-layer references are displayed as clickable links
- [ ] Clicking a cross-layer reference navigates to the referenced item
- [ ] Entering edit mode allows modifying frontmatter fields and the markdown body
- [ ] Saving edits updates the item and returns to the view mode with updated content
- [ ] Attribution (last modified by, timestamp) is displayed correctly

### Idea Inbox

- [ ] The idea submission form accepts text and creates a new idea
- [ ] Newly submitted ideas appear in the idea list with "pending" status
- [ ] The "generate ideas" button triggers AI idea generation
- [ ] Evaluated ideas display a 6-axis radar chart
- [ ] Expanding an evaluated idea shows critic assessments and synthesis
- [ ] Ideas can be sorted by overall score
- [ ] Ideas can be filtered by status (pending, evaluating, evaluated)

### Live Cascade Viewer

- [ ] When a cascade is running, the viewer shows which layer is being processed
- [ ] The viewer shows which step is active (generation, critics, synthesis)
- [ ] Agent reasoning text streams in real-time as the cascade runs
- [ ] The cascade progress indicator advances as layers are completed
- [ ] When a cascade is paused due to error, the error message is displayed with resume and cancel buttons
- [ ] Clicking resume on a paused cascade resumes it
- [ ] Clicking cancel on a paused cascade cancels it and the viewer returns to idle state
- [ ] The cascade queue is visible when cascades are queued

### Activity Feed

- [ ] The activity feed shows events in chronological order
- [ ] Filtering by event type narrows the displayed events
- [ ] Filtering by layer narrows the displayed events
- [ ] New events appear in the feed in real-time (via WebSocket)

### Admin Panel

- [ ] The admin panel is accessible to admin users
- [ ] The admin panel is not visible in navigation for non-admin users
- [ ] The admin panel shows a list of all users
- [ ] The admin can create a new user with email and password
- [ ] The admin can delete a user (with confirmation dialog)
- [ ] The admin cannot delete themselves

### Theme Switching

- [ ] The app respects the system's dark/light preference on initial load
- [ ] The user can toggle between dark and light modes via a UI control
- [ ] The theme preference persists across page reloads
- [ ] All pages render correctly in both dark and light themes (no invisible text, broken borders, or unreadable content)

### Version History

- [ ] The version history page shows recent changes for a layer
- [ ] Each entry shows a date, change description, and trigger source

### Responsive Behavior

- [ ] The stack overview page is usable at viewport widths down to 768px
- [ ] The layer detail view is usable at viewport widths down to 768px
- [ ] Navigation is accessible at all supported viewport sizes

---

## Manual Testing

**None** — all verification must be automated.
