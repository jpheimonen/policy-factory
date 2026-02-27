# Architecture

## Components Affected

### Backend — Project Structure

The backend is a Python package at `src/policy_factory/` following the cc-runner layout. It serves both the REST API and static frontend assets from a single process. The entry point is a CLI command (defined in pyproject.toml) that loads environment variables from .env files, initializes the database and data directory, starts APScheduler, and launches uvicorn.

The package is organized into these subpackages:

- `server/` — FastAPI app factory, routers, WebSocket manager, dependency injection, auth middleware
- `store/` — SQLite storage with mixin composition (auth mixin, idea mixin, cascade mixin, heartbeat mixin, agent run mixin, feedback memo mixin)
- `session/` — Claude Code SDK wrapper with per-agent model selection, streaming, retry logic
- `agents/` — Agent orchestration: cascade runner, critic runner, idea evaluator, heartbeat tiers, input classifier, seed runner
- `prompts/` — Markdown prompt templates organized by category, loaded via PromptLoader
- `data/` — Utilities for reading/writing the markdown+YAML layer files and managing the data git repo
- `static/dist/` — Built frontend assets (populated by the frontend build step)

### Backend — Authentication System

A new auth system (not present in cc-runner). JWT-based with bcrypt password hashing. Two roles: admin and user.

- The auth store mixin manages users in SQLite (email, hashed password, role, created_at)
- On first startup when no users exist, the registration endpoint is open. The first user to register is automatically assigned the admin role. After that, registration is closed — only admins can create accounts.
- Login returns a JWT access token. All API routes except `/api/auth/login` and `/api/auth/register` require a valid JWT in the Authorization header.
- WebSocket connections authenticate by passing the JWT as a query parameter on the connection URL. The server validates the token during the WebSocket handshake and rejects invalid connections.
- A FastAPI dependency (`get_current_user`) extracts and validates the JWT from each request, returning the user record. An `require_admin` dependency extends this to verify admin role.

### Backend — Data Layer (Markdown + Git)

A `data/` directory at the project root (separate git repo, gitignored by the main app repo). Contains five layer subdirectories, each holding markdown files with YAML frontmatter.

The five layer directories in hierarchical order (bottom to top):
1. `data/values/` — Foundational national values and interests
2. `data/situational-awareness/` — Current state of the world relevant to Finland
3. `data/strategic-objectives/` — Long-term strategic goals derived from values + situation
4. `data/tactical-objectives/` — Concrete medium-term objectives supporting strategies
5. `data/policies/` — Specific policy actions and recommendations

Each directory also contains a `README.md` — an AI-generated narrative summary of that layer.

The data utilities module provides:
- Reading a single item: parse the markdown file, extract YAML frontmatter into a dict, return frontmatter + body
- Listing all items in a layer: scan the directory for .md files (excluding README.md), return summary metadata from frontmatter
- Writing an item: serialize frontmatter + body back into a markdown file
- Deleting an item: remove the file
- Reading/writing the narrative summary (README.md)
- Cross-layer reference resolution: given an item, find all items whose frontmatter references it, and all items it references
- Git operations: auto-initialize the data repo on first run if absent, commit changes with descriptive messages, retrieve recent commit history per directory

On first startup, if the data directory doesn't exist, the system creates it, initializes a git repo inside it, creates the five subdirectories, and writes pre-seeded values files for Finland (national security, economic prosperity, EU solidarity, Arctic sovereignty, democratic institutions, social welfare, technological competitiveness, cultural identity, environmental sustainability, etc.).

### Backend — SQLite Store

Following cc-runner's raw sqlite3 pattern with WAL mode and mixin composition. The store is composed of a base class plus domain-specific mixins:

**Auth mixin** — user CRUD: create user (with hashed password), get user by email, list users, delete user. Tracks email, hashed password, role (admin/user), created_at.

**Idea mixin** — idea queue management: create idea (with source: human or AI, plus optional target objective), get idea by ID, list ideas (with filtering by status and sorting by score), update idea status (pending → evaluating → evaluated → archived). Stores idea text, source, target objective reference, submission timestamp, evaluation status.

**Score mixin** — evaluation results: store 6-axis scores for an idea (strategic fit, feasibility, cost, risk, public acceptance, international impact — each a numeric value), store critic assessments per idea (one row per critic perspective), store synthesis assessment. Linked to idea by foreign key.

**Cascade mixin** — cascade state tracking: create cascade record (trigger source, starting layer), update progress (current layer, current step within layer — generation/critics/synthesis), update status (running/paused/completed/failed/cancelled), manage the cascade queue (ordered list of pending cascade requests), manage the single-writer lock (acquire/release/check). Stores trigger source, starting layer, current progress, status, error message if failed, timestamps.

**Feedback memo mixin** — bidirectional feedback: create memo (source layer, target layer, content, referenced items), update status (pending/accepted/dismissed), list pending memos for a given target layer. Memos are transient — they're consumed during the next generation of the target layer.

**Heartbeat mixin** — run logging: record each heartbeat run (timestamp, highest tier reached, items flagged at each tier, actions taken), retrieve recent heartbeat history.

**Agent run mixin** — execution history: record each agent invocation (agent type, model used, target layer, start time, end time, success/failure, error message, token usage if available). Used for activity feed and diagnostics.

### Backend — Agent Framework

A simplified version of cc-runner's session wrapper. The agent session wraps claude-agent-sdk to run Claude Code sessions against the `data/` directory.

Key behaviors:
- **Per-agent model selection**: Each agent type (layer generator, critic, synthesis, heartbeat tier, input classifier, idea evaluator) has a configurable model. Configured via environment variables or a config file. Defaults: Opus for generation, Sonnet for synthesis and classification, Haiku for heartbeat tier 1, Sonnet for critics.
- **Working directory**: All agents run with `data/` as their working directory so they can read and write layer files directly using Claude Code's native file tools.
- **Streaming**: Agent output is streamed via the EventEmitter. Each text chunk from the agent becomes an event that gets broadcast over WebSocket to all connected clients.
- **Meditation filtering**: The agent prompt instructs the AI to begin with a meditation preamble (counting down 10→1 with bias self-reflection). The streaming output filter detects the meditation section and suppresses it from the WebSocket broadcast. Only post-meditation content is streamed to clients. The meditation content is still captured in the agent run log for auditability.
- **Retry logic**: On transient errors (API 500/502/503/529, overloaded, rate limits), retry up to 3 times with exponential backoff. On non-transient errors, fail immediately.
- **Prompt construction**: Each agent's prompt is assembled from: (1) the meditation preamble section, (2) the agent-specific prompt template loaded from `prompts/`, (3) dynamic context injected via template variables (e.g., pending feedback memos, the specific layer being generated, relevant cross-layer data).

The prompt directory is organized by agent category:
- `prompts/meditation/` — the shared bias meditation preamble
- `prompts/generators/` — one prompt per layer (values, situational-awareness, strategic, tactical, policies)
- `prompts/critics/` — one prompt per critic archetype (realist, liberal-institutionalist, nationalist-conservative, social-democratic, libertarian, green-ecological)
- `prompts/synthesis/` — the critic synthesis prompt
- `prompts/heartbeat/` — one prompt per heartbeat tier (skim, triage, sa-update)
- `prompts/classifier/` — the input classification prompt
- `prompts/ideas/` — idea generation and evaluation prompts
- `prompts/seed/` — initial situational awareness seeding prompt

### Backend — Cascade Orchestrator

The cascade orchestrator manages the end-to-end flow of updating layers and running critics. It enforces the single-writer lock and manages the cascade queue.

**Cascade flow for a triggered update at layer N:**

1. Acquire the cascade lock. If already held, add this request to the queue and return immediately (the queued cascade's status is visible to all clients via WebSocket).
2. Run the primary generation agent for layer N. The agent reads all items from layers below N, reads any pending feedback memos targeting layer N, and creates/updates/removes files in layer N's directory. It also regenerates layer N's README.md.
3. Auto-commit changes to the data git repo.
4. Run all 6 critic agents in parallel against layer N's updated content. Each critic runs with a cheaper/faster model.
5. Run the synthesis agent to integrate critic outputs into a balanced assessment.
6. Store critic and synthesis results (associated with the layer and cascade run).
7. Record any feedback memos the generation agent produced for layers below N.
8. If there are layers above N, advance to layer N+1 and repeat from step 2.
9. After the topmost layer is processed, release the cascade lock. If the queue has pending cascades, start the next one.

**Error handling within a cascade:**
- If an agent fails, retry up to 3 times.
- If all retries fail, pause the cascade: record the error and the current position (which layer, which step). Broadcast the failure to all clients. The cascade lock remains held (preventing other cascades from running on inconsistent data).
- A user can resume a paused cascade via the API. The cascade resumes from the failed step.
- A user can cancel a paused cascade, which releases the lock and discards the remaining steps.

**Cascade progress broadcasting:**
Throughout the cascade, progress events are emitted: which layer is being processed, which step (generation / critics / synthesis), which specific agent is running (e.g., "Realist critic"). These events flow through the EventEmitter → WebSocket → all connected clients.

### Backend — Critic Runner

A sub-component of the cascade orchestrator. Takes a layer's content and runs all 6 critics in parallel.

Each critic agent:
- Receives the full content of the layer being critiqued (all items + narrative summary)
- Has a system prompt defining its ideological worldview
- Produces structured output: for each item in the layer, states agreement or disagreement, provides reasoning, and optionally suggests alternatives
- Runs with a cheaper/faster model (configurable, default Sonnet)

After all 6 critics complete, the synthesis agent runs:
- Receives all 6 critic outputs
- Integrates them into a unified assessment
- Explicitly identifies unresolved tensions between perspectives (e.g., "The Realist and Liberal-institutionalist perspectives fundamentally disagree on X")
- Produces the final balanced assessment for that layer

### Backend — Idea Pipeline

Handles idea submission, generation, and evaluation. Operates independently from the cascade — idea evaluations are read-only against layer data and don't need the cascade lock.

**Idea sources:**
- Human submission via the API (user types an idea in the UI)
- AI generation on demand (user clicks "generate ideas" in the UI, targeting a specific objective or the whole framework)
- AI generation via the heartbeat (Tier 4 triggers idea generation after a cascade completes)

**Evaluation flow per idea:**
1. Read the full layer stack (all five layers) as context
2. Score the idea on 6 axes (strategic fit, feasibility, cost, risk, public acceptance, international impact) — each axis gets a numeric score
3. Run all 6 critics against the idea (in parallel, using cheaper models)
4. Run the synthesis agent to produce an overall assessment
5. Store all scores, critic outputs, and synthesis in SQLite, linked to the idea

Multiple idea evaluations can run concurrently since they only read layer data.

### Backend — Tiered Heartbeat

Scheduled via APScheduler running in-process. Also triggerable manually via API endpoint.

**Tier 1 — News Skim:**
- Runs on the configured schedule (e.g., every 4 hours)
- Uses a cheap/fast model (Haiku)
- The agent reads yle.fi using Claude Code's native web search/fetch capability
- Compares current news against the existing situational awareness layer content
- Outputs either "nothing noteworthy" or a list of flagged items worth deeper analysis
- If nothing noteworthy: log the run, stop. Cost: minimal (one cheap model call).

**Tier 2 — Triage Analysis:**
- Only runs when Tier 1 flags items
- Uses a mid-tier model (Sonnet)
- For each flagged item, the agent uses web search to find international sources and context
- Determines whether each item warrants an update to the situational awareness layer
- If no items warrant updates: log the run, stop.

**Tier 3 — SA Update:**
- Only runs when Tier 2 recommends updates
- Full Claude Code agent (Opus or Sonnet) runs against the `data/` directory
- Reads and updates situational awareness markdown files
- Regenerates the situational awareness README.md
- Auto-commits changes to the data git repo

**Tier 4 — Full Cascade:**
- Only runs after Tier 3 updates the situational awareness layer
- Triggers a standard upward cascade from the situational awareness layer (strategic → tactical → policies) with full critic passes at each level
- Also triggers AI idea generation after the cascade completes

Each heartbeat run is logged in SQLite: timestamp, highest tier reached, items flagged, actions taken.

### Backend — Input Classifier

When a user submits free-text input via the input panel, a lightweight AI agent classifies which layer it most affects. The agent receives the input text and brief descriptions of each layer, then returns: the target layer, a brief explanation of why, and optionally any transformations needed to express the input as layer-appropriate content.

After classification, the system updates the target layer (by running that layer's generation agent with the user input as additional context) and triggers the upward cascade from that layer.

### Backend — Event System

Following cc-runner's EventEmitter pattern with typed dataclass events. Events flow from agent execution → EventEmitter → WebSocket broadcast to all authenticated clients.

Event categories:
- **Cascade lifecycle**: cascade started, cascade completed, cascade failed, cascade paused, cascade resumed, cascade cancelled, cascade queued
- **Layer processing**: layer generation started/completed, critic started/completed (per critic), synthesis started/completed
- **Agent streaming**: agent text chunks (the actual reasoning text being streamed, with meditation content filtered out)
- **Heartbeat**: heartbeat started, tier completed (with tier number and outcome), heartbeat completed
- **Ideas**: idea submitted, idea evaluation started/completed, idea generation started/completed
- **System**: user login, user created, cascade lock acquired/released

### Backend — REST API Routers

Organized as separate FastAPI APIRouter modules, each with a URL prefix. All routers except auth require JWT authentication.

- **Auth router** (`/api/auth/`) — login, register (first-user-only after initial), token refresh
- **Users router** (`/api/users/`) — admin-only: list users, create user, delete user
- **Layers router** (`/api/layers/`) — CRUD for layer items across all 5 layers, narrative summaries, cross-layer reference resolution, layer listing with summary metadata
- **History router** (`/api/history/`) — git history per layer (recent changes, timestamps, change summaries)
- **Cascade router** (`/api/cascade/`) — trigger cascade (from user input, from specific layer, full refresh), get status, cancel, resume paused
- **Ideas router** (`/api/ideas/`) — submit idea, list ideas (with filtering/sorting), get idea detail with scores and critic results, trigger AI idea generation
- **Heartbeat router** (`/api/heartbeat/`) — trigger manual heartbeat, get recent heartbeat log
- **Activity router** (`/api/activity/`) — chronological event stream with filtering by type and layer
- **Health router** (`/api/health/`) — basic health check, tool availability
- **Seed router** (`/api/seed/`) — trigger initial situational awareness population

### Backend — WebSocket

Adapted from cc-runner's ConnectionManager pattern, extended with JWT authentication.

On connection: the client passes a JWT token as a query parameter. The server validates the token during the handshake. Invalid tokens result in connection rejection. Valid connections are tracked by the manager.

Broadcasting: all events from the EventEmitter that should be client-visible are serialized and broadcast to all authenticated connections. The server does not currently need to send events to specific users — all authenticated users see all activity (this is a small trusted group).

### Frontend — App Shell and Routing

The app wraps all content in: ThemeProvider (dual themes) → i18n Provider → AuthProvider → GlobalStyles → BrowserRouter → Routes.

Routes are split into public (login, register) and protected (everything else). A protected route wrapper checks the auth store for a valid token and redirects to login if absent.

Page-level routes:
- `/login` — login page
- `/register` — registration page (only shown when no users exist yet)
- `/` — stack overview (home page, redirects to login if not authenticated)
- `/layers/:layerSlug` — layer detail view (e.g., `/layers/values`, `/layers/situational-awareness`)
- `/layers/:layerSlug/:itemSlug` — item detail/editing view
- `/ideas` — idea inbox
- `/cascade` — live cascade viewer
- `/activity` — activity feed
- `/history/:layerSlug` — version history for a layer
- `/admin` — admin panel (admin users only)

### Frontend — Design System

Built with styled-components and a comprehensive token system. Two theme objects (dark and light) share the same token structure but with different values. Theme selection follows system preference via `prefers-color-scheme` media query, overridable by the user (stored in localStorage).

Design language: Linear/Notion-inspired. Inter font family. Subtle borders rather than heavy shadows. Muted color palette with distinct accent colors assigned to each of the 5 layers (so users can visually identify which layer content belongs to at a glance). Generous whitespace. Smooth transitions on interactive elements.

Each layer has a consistent identity color used in: layer cards on the stack overview, the header/accent in layer detail views, badges on items, and the cascade progress indicator.

### Frontend — i18n

All user-visible strings are externalized through an i18n system from day one. Components never contain hardcoded display text — they reference translation keys. English is the only language initially, but the architecture supports adding new locales by adding translation files without modifying component code.

The translation file structure uses a flat key namespace organized by page/feature (e.g., `stackOverview.title`, `cascade.status.running`, `critics.realist.name`).

### Frontend — State Management

Zustand stores for each domain:

- **Auth store** — JWT token, current user info, login/logout actions, token refresh. Persisted to localStorage.
- **Layer store** — Layer data fetched from the API. Items, narrative summaries, feedback memos per layer. Refresh actions.
- **Cascade store** — Current cascade status (running/paused/idle), progress (current layer, current step), queue depth, error info. Updated primarily from WebSocket events.
- **Idea store** — Idea list with filters, submission action, evaluation results. Updated from API calls + WebSocket events for real-time evaluation progress.
- **Activity store** — Event stream, filter state. Updated from WebSocket events.
- **Theme store** — Current theme preference (system/dark/light). Persisted to localStorage.

### Frontend — WebSocket Integration

A custom hook adapted from cc-runner's useWebSocket pattern. Connects to `/ws?token=<JWT>` on mount. Auto-reconnects with exponential backoff on disconnect. Deduplicates events by ID. On reconnect, replays missed events from a REST endpoint.

Incoming WebSocket events are dispatched to the appropriate zustand stores based on event type:
- Cascade events → cascade store
- Agent chunk events → cascade store (for the live text stream)
- Idea events → idea store
- Activity events → activity store

### Frontend — Pages

**Stack Overview (Home):**
Five layers displayed as a vertical stack from bottom (values) to top (policies). Each layer card shows: layer name with identity color, item count, last updated timestamp, narrative summary preview (first ~2 lines of README.md), pending feedback memo count (if any). Clicking a layer navigates to its detail view. A prominent input panel (always visible, likely as a floating element or sidebar) allows users to submit free-text input at any time. Current cascade status shown in the header area if a cascade is running.

**Layer Detail View:**
Header with layer name, identity color, and a refresh button (triggers layer regeneration). The narrative summary (README.md content) rendered at the top. Incoming feedback memos from layers above displayed as dismissable cards with accept/dismiss actions. All items shown as cards with key metadata extracted from frontmatter (title, status, references, last modified). Aggregated critic assessment summary if available. Clicking an item card navigates to the item detail view.

**Item Detail + Editing:**
Full item view: frontmatter fields rendered as labeled fields, markdown body rendered to HTML. Cross-layer references shown as clickable links that navigate to the referenced item. Edit mode: inline editing for frontmatter fields and a markdown editor for the body. Saving triggers a write to the markdown file via the API, an auto-commit to the data git repo, and potentially a cascade if the item is in a lower layer. Attribution shown (who or what last modified the item, with timestamp).

**Idea Inbox:**
A form to submit new ideas (text input). A button to trigger AI idea generation (optionally scoped to a specific objective). List of ideas with status badges (pending, evaluating, evaluated). Evaluated ideas display a 6-axis radar chart (recharts) showing scores. Expanding an idea shows the full critic assessments and synthesis. Sorting by overall score, recency, or individual axis. Filtering by status.

**Live Cascade Viewer:**
Real-time display of the currently running cascade. A visual progress indicator showing which layer is being processed and which step (generation → critics → synthesis). The actual agent reasoning text streams in real-time (meditation content filtered out). Shows which specific agent is active (e.g., "Green/Ecological critic analyzing Tactical Objectives"). The cascade queue is visible if other cascades are waiting. If the cascade is paused due to error, the error is displayed with a resume button and a cancel button.

**Activity Feed:**
A chronological stream of system events. Each event shows: timestamp, event type with icon, description, and relevant context (which layer, which agent, etc.). Filterable by event type (cascade, heartbeat, idea, user action) and by layer.

**Admin Panel:**
Only accessible to admin users (non-admin users don't see the nav link). User list showing email, role, and creation date. Form to create a new user (email + password). Delete user action with confirmation. No self-deletion (admin cannot delete themselves).

**Version History:**
Per-layer view showing recent git commits affecting that layer's directory. Each entry shows: date, commit message (which describes what changed), and what triggered the change (agent name, user action, heartbeat). Simple chronological list — no diff viewer or rollback actions.

### Frontend — Build and Serving

In development: Vite dev server proxies `/api/*` and `/ws` to the backend on the dynamically selected port (via `VITE_BACKEND_PORT` environment variable).

In production: `bun run build` outputs the compiled frontend to `src/policy_factory/static/dist/`. The FastAPI server serves these files as static assets, with a catch-all SPA fallback route that returns `index.html` for any path not matched by API routes or static files.

### Dockerfile

Single-stage or multi-stage Docker build. The container runs the Python CLI entry point which starts uvicorn. The image includes: Python runtime, the policy_factory package (with built frontend assets baked in), and the `claude` CLI (needed for claude-agent-sdk to function). The `data/` directory is mounted as a Docker volume so layer data persists across container restarts. The SQLite database file location is configurable via environment variable (defaults to `~/.policy-factory/store.db`), also typically mounted as a volume.

### Makefile

Adapted from cc-runner. Key targets:
- `make dev` — finds an available port, launches both backend (uvicorn) and frontend (vite dev server) concurrently, kills both on exit
- `make build` — installs frontend dependencies and builds the production frontend into the static directory
- `make run` — builds frontend then starts the production server
- `make docker-build` — builds the Docker image
- `make docker-run` — runs the Docker container with appropriate volume mounts

---

## New Entities/Endpoints

### Data Entities (Markdown Files)

**Layer Item** — a markdown file with YAML frontmatter in one of the five layer directories. Frontmatter contains structured metadata: title, status, creation date, last modified date, last modified by (user email or agent name), and cross-layer references (a list of filenames in other layers that this item relates to). The markdown body contains the rich content of the item.

**Layer Narrative Summary** — the README.md in each layer directory. AI-generated prose that summarizes the current state of that layer in a coherent narrative form. Regenerated each time the layer is updated.

### Data Entities (SQLite)

**User** — email, hashed password, role (admin/user), created_at.

**Idea** — text content, source (human/AI), optional target objective reference, submission timestamp, evaluation status (pending/evaluating/evaluated/archived), submitted_by (user email or "system").

**Idea Score** — linked to an idea. Six numeric scores (strategic fit, feasibility, cost, risk, public acceptance, international impact). Overall assessment text from the synthesis agent.

**Idea Critic Result** — linked to an idea, one per critic perspective. The critic's archetype name, their structured assessment (agreement/disagreement per point, reasoning, alternatives).

**Cascade Run** — trigger source (user input, layer refresh, heartbeat, seed), starting layer, current layer, current step (generation/critics/synthesis), status (queued/running/paused/completed/failed/cancelled), error message, timestamps (started_at, completed_at).

**Feedback Memo** — source layer, target layer, content, referenced item filenames, status (pending/accepted/dismissed), created_at, created_by (agent run ID).

**Heartbeat Run** — timestamp, highest tier reached (1-4), tier 1 result (noteworthy/nothing), items flagged (as text), actions taken (as text), cascade_run_id if a cascade was triggered.

**Agent Run** — agent type, model used, target layer, cascade_run_id (if part of a cascade), started_at, completed_at, success (boolean), error message, tokens_used (if available from SDK).

### API Endpoints

**Auth:**
- POST `/api/auth/register` — register a new user (first-user-only after initial, then admin-only)
- POST `/api/auth/login` — authenticate with email+password, returns JWT
- POST `/api/auth/refresh` — refresh an expiring JWT

**Users (admin-only):**
- GET `/api/users/` — list all users
- POST `/api/users/` — create a new user
- DELETE `/api/users/:id` — delete a user

**Layers:**
- GET `/api/layers/` — list all 5 layers with metadata (item count, last updated, narrative preview)
- GET `/api/layers/:slug/items` — list all items in a layer with summary metadata
- GET `/api/layers/:slug/items/:filename` — get a single item (frontmatter + body)
- PUT `/api/layers/:slug/items/:filename` — update an item (frontmatter + body)
- POST `/api/layers/:slug/items` — create a new item
- DELETE `/api/layers/:slug/items/:filename` — delete an item
- GET `/api/layers/:slug/summary` — get the narrative summary (README.md)
- GET `/api/layers/:slug/items/:filename/references` — get cross-layer references for an item

**History:**
- GET `/api/history/:slug` — recent git history for a layer directory

**Cascade:**
- POST `/api/cascade/trigger` — trigger a cascade (body specifies: from user input, from specific layer, or full refresh)
- GET `/api/cascade/status` — current cascade status, progress, and queue
- POST `/api/cascade/resume` — resume a paused cascade
- POST `/api/cascade/cancel` — cancel a paused or queued cascade

**Ideas:**
- GET `/api/ideas/` — list ideas with optional filtering (status, sort by score/recency)
- POST `/api/ideas/` — submit a new idea (human-submitted)
- GET `/api/ideas/:id` — get idea detail with scores and critic results
- POST `/api/ideas/generate` — trigger AI idea generation (optionally scoped)

**Heartbeat:**
- POST `/api/heartbeat/trigger` — trigger a manual heartbeat run
- GET `/api/heartbeat/log` — recent heartbeat run history

**Activity:**
- GET `/api/activity/` — chronological event stream with filtering (type, layer, pagination)

**Seed:**
- POST `/api/seed/run` — trigger initial situational awareness population

**Health:**
- GET `/api/health/check` — basic health check and tool availability

---

## Integration Points

### Agent → File System → API

Agents (running via claude-agent-sdk) operate directly on markdown files in the `data/` directory. They read files to understand context and write files to create/update layer items. After an agent run completes, the backend auto-commits any file changes to the data git repo. The REST API layer reads these same files when serving layer data to the frontend — there is no separate "database sync" step; the markdown files are the source of truth for layer content.

### Agent → EventEmitter → WebSocket → Frontend

When an agent runs, the session wrapper captures output chunks and emits them as typed events through the EventEmitter. A WebSocket broadcast handler (subscribed to the emitter) serializes these events and sends them to all connected clients. The frontend's WebSocket hook receives these events and dispatches them to the appropriate zustand stores, which trigger React re-renders.

The meditation preamble is filtered at the streaming layer — the session wrapper detects the meditation section in the agent output and suppresses those chunks from being emitted as events. The full output (including meditation) is saved to the agent run log in SQLite.

### Cascade Orchestrator → Agent Framework → Store

The cascade orchestrator drives the sequence of agent invocations for a cascade. It reads cascade state from SQLite, runs agents via the agent framework, updates cascade progress in SQLite after each step, and emits progress events. The orchestrator also writes critic results and feedback memos to SQLite.

### Heartbeat → Cascade Orchestrator

The heartbeat system runs independently on a schedule. When Tier 3 updates situational awareness files, it signals the cascade orchestrator to start a cascade from the situational awareness layer. This uses the same cascade trigger mechanism as a user-initiated cascade — the heartbeat is just another trigger source.

### Frontend → REST API → Backend

All frontend data fetching goes through the REST API. The auth token is included in every request header. Layer data, ideas, cascade status, and activity are all fetched via REST endpoints. Mutations (submitting ideas, triggering cascades, creating users) are POST/PUT/DELETE requests.

### Frontend → WebSocket → Backend (real-time)

The WebSocket connection provides real-time updates that supplement REST fetches. When a cascade starts, progresses, or completes, the frontend learns about it immediately via WebSocket rather than polling. The cascade viewer page relies primarily on WebSocket events for its live-streaming display.

### Auth Flow

Login: frontend sends email+password to `/api/auth/login`, receives JWT. The token is stored in the auth zustand store (persisted to localStorage). All subsequent API requests include the token in the Authorization header. The WebSocket connection passes the token as a query parameter. When the token approaches expiry, the frontend calls the refresh endpoint.

### Data Git Repo → Layer Content → Cross-Layer References

Layer items reference items in other layers via frontmatter fields (listing filenames from other layer directories). The cross-layer reference resolution endpoint traverses these references bidirectionally: given an item, it finds both "items I reference" and "items that reference me." This enables the UI to show relationship links between layers.

---

## Failure Modes

### Agent Failures During Cascade

**What happens:** A Claude Code agent fails (API error, timeout, context overflow, quota exhaustion).

**How it's handled:** The session wrapper retries up to 3 times with exponential backoff for transient errors (API 500/502/503/529, overloaded, rate limits). Non-transient errors (auth failure, context overflow) are not retried. If all retries fail, the cascade is paused: the error and the current position (layer + step) are recorded in SQLite, a failure event is broadcast to all clients, and the cascade lock is held. The user sees the error in the cascade viewer and can choose to resume (retry the failed step) or cancel (release the lock and discard remaining steps).

### Cascade Lock Contention

**What happens:** A user triggers a cascade while another cascade is already running.

**How it's handled:** The new cascade request is added to a queue in SQLite. Its status is set to "queued." All connected clients are notified of the queue via WebSocket. When the running cascade completes (or is cancelled), the next queued cascade starts automatically. The queue is FIFO. Users can see the queue depth and their position in the cascade viewer.

### Concurrent Idea Evaluations

**What happens:** Multiple idea evaluations run simultaneously while a cascade is also running.

**How it's handled:** Idea evaluations are read-only against layer data — they don't modify files or need the cascade lock. They can run concurrently with each other and with a running cascade. However, if a cascade completes and changes layer data while an idea evaluation is in progress, the evaluation is based on slightly stale data. This is acceptable — the evaluation results are still valid against the layer state at the time the evaluation started.

### Data Git Repo Conflicts

**What happens:** Two processes try to commit to the data git repo simultaneously.

**How it's handled:** This shouldn't happen because the cascade lock serializes all write operations to the data directory. Idea evaluations don't write to the data directory. The only write paths are: cascade agent runs (serialized by lock), manual item edits via the API (which should also check the cascade lock before writing), and heartbeat-triggered updates (which go through the cascade orchestrator). If a conflict somehow occurs, the git commit will fail, the agent run will fail, and the cascade will pause for human intervention.

### WebSocket Connection Loss

**What happens:** A client loses its WebSocket connection during a cascade.

**How it's handled:** The frontend's useWebSocket hook auto-reconnects with exponential backoff (up to 8 attempts). On successful reconnect, it replays missed events from a REST endpoint that returns recent cascade events. Event deduplication by ID prevents double-rendering. If reconnection fails after max attempts, the UI shows a "disconnected" indicator. The user can still use the REST API to check cascade status and fetch updated layer data.

### JWT Token Expiry

**What happens:** A user's JWT expires while they're using the app.

**How it's handled:** API requests with expired tokens return 401. The frontend intercepts 401 responses and attempts a token refresh. If the refresh succeeds, the original request is retried with the new token. If the refresh fails (e.g., the refresh token is also expired), the user is redirected to the login page. The WebSocket connection also fails on token expiry — the server closes connections with expired tokens, and the auto-reconnect logic triggers a token refresh before reconnecting.

### Heartbeat Failures

**What happens:** A scheduled heartbeat fails (yle.fi unreachable, agent error, API quota).

**How it's handled:** The heartbeat is a best-effort system. If any tier fails, the failure is logged in the heartbeat run table and the heartbeat stops at that tier. No cascade is triggered. The next scheduled heartbeat will try again. Persistent failures will show up in the heartbeat log and the activity feed, alerting users that the system isn't keeping up with current events.

### First-Run Initialization Failures

**What happens:** The data directory initialization or pre-seeded values creation fails on first startup.

**How it's handled:** The initialization happens during the FastAPI lifespan startup. If it fails (e.g., disk full, permission denied), the server logs the error and starts anyway — the data directory will be absent or incomplete. The frontend will show empty layers. The user can retry initialization via the seed endpoint or manually create the data directory. The system should be resilient to a partially initialized data directory (missing subdirectories, missing README.md files).

### SQLite Database Corruption

**What happens:** The SQLite database file becomes corrupted (unlikely with WAL mode, but possible on sudden power loss or disk failure).

**How it's handled:** SQLite with WAL mode is highly resilient to corruption. The database is not the source of truth for layer content (that's the markdown files in the data git repo). If the database is lost, the system loses: user accounts, idea evaluations, cascade history, and heartbeat logs. Layer content is preserved in the data git repo. The database can be recreated from scratch (re-register users, re-evaluate ideas). This is an acceptable risk for a small-group tool.

### Meditation Filtering Edge Cases

**What happens:** The meditation preamble detection logic fails to correctly identify the boundary between meditation content and analysis content.

**How it's handled:** The meditation format is strictly defined in the prompt (counting down from 10 to 1 with specific formatting). The filter looks for this known structure. If the filter fails to detect the boundary, the worst case is that meditation content leaks into the streamed output (the user sees the AI reflecting on its biases, which is weird but not harmful) or that the beginning of the analysis is suppressed (the user misses some analysis text). The full unfiltered output is always saved to the agent run log, so no content is permanently lost. The filter should be conservative — when in doubt, stop filtering and stream everything rather than risk suppressing analysis content.
