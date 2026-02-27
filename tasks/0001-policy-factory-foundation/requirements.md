# Requirements

## Problem Statement

Finland's cross-party tech policy group needs a tool that produces brutally honest, apolitical policy analysis unconstrained by electoral considerations. Current policy analysis is filtered through political palatability — what gets votes, what sounds good, what offends nobody. The result is bland, compromise-driven policy that optimizes for agreeableness rather than national interest.

Policy Factory is an AI-powered policy analysis engine that builds policy from the ground up: starting from foundational national values and interests, layering in situational awareness of the real world, deriving strategic and tactical objectives, and finally producing concrete policy actions. Every output is challenged by 6 ideological critic perspectives. The system acknowledges and self-corrects for AI bias through a structured self-reflection mechanism rather than pretending to be neutral.

This is the foundational task: establishing the full application from scratch — project structure, backend, frontend, data model, authentication, agent framework, all five policy layers, the critic system, idea evaluation, the tiered heartbeat, and a polished UI. The reference implementation for technical patterns is the ModernPath Software Factory (cc-runner) at `/home/jp/projects/modernpath/cc-runner`.

## Success Criteria

### Project Foundation
- [ ] Python backend project with FastAPI and uvicorn, structured as `src/policy_factory/`
- [ ] Vite + React 19 + TypeScript frontend in `ui/` directory
- [ ] Makefile with `make dev` that finds an available port and launches both backend and frontend concurrently (following cc-runner patterns)
- [ ] Vite dev server proxies API and WebSocket requests to FastAPI backend
- [ ] Production build outputs frontend assets into Python package static directory for single-binary serving
- [ ] uv for Python package management, bun for frontend, hatchling build system
- [ ] Dockerfile for cloud-agnostic deployment (runs on any VM/VPS, no cloud-vendor dependencies)
- [ ] Environment variable configuration via .env files (following cc-runner's multi-location .env loading pattern)

### Authentication & User Management
- [ ] Email + password authentication with JWT tokens
- [ ] Passwords stored with bcrypt hashing in SQLite
- [ ] The first user to register automatically becomes admin
- [ ] Admin can create new user accounts via the UI (sets email + temporary password, shares credentials out-of-band)
- [ ] All API routes (except auth endpoints) require valid JWT
- [ ] WebSocket connections authenticated via JWT
- [ ] Login and registration pages in the frontend

### Data Storage — Layer Data (Markdown + Git)
- [ ] A `data/` directory that is its own separate git repository, independent from the application code
- [ ] Five layer subdirectories: `values/`, `situational-awareness/`, `strategic-objectives/`, `tactical-objectives/`, `policies/`
- [ ] Each layer item is a markdown file with YAML frontmatter for structured metadata and a markdown body for rich content
- [ ] Each layer directory has a `README.md` that serves as the AI-generated narrative summary for that layer
- [ ] Cross-layer references expressed via frontmatter fields (e.g., a strategic objective's frontmatter lists which values it serves)
- [ ] The data git repo auto-initializes on first run if it doesn't exist
- [ ] Agent file modifications are auto-committed to the data repo with descriptive commit messages
- [ ] Ship with pre-seeded Finnish values (national security, economic prosperity, EU solidarity, Arctic sovereignty, democratic institutions, social welfare, technological competitiveness, cultural identity, environmental sustainability, etc.)

### Data Storage — SQLite
- [ ] Users and authentication data
- [ ] Idea queue (submissions, evaluation status, source — human or AI)
- [ ] Scoring results (6-axis scores per idea)
- [ ] Agent run history (which agent ran, when, model used, duration, success/failure)
- [ ] Cascade state (current cascade progress, lock status, queued cascades)
- [ ] Feedback memos (transient, actionable — source layer, target layer, content, status: pending/accepted/dismissed)
- [ ] Heartbeat run log (tier reached, items flagged, actions taken)

### REST API — Layer Data
- [ ] CRUD endpoints for each layer's items (reads markdown files, parses YAML frontmatter, returns structured JSON; writes create/update markdown files)
- [ ] Endpoint to get/update the narrative summary (README.md) for each layer
- [ ] Cross-layer reference resolution (given an item, return all items that reference it and all items it references)
- [ ] Endpoint to list all items in a layer with summary metadata (from frontmatter)
- [ ] Git history endpoint: per-layer recent changes (date, what changed, who/what triggered it)

### REST API — Operations
- [ ] Trigger a layer update from user input (free text → AI classifies affected layer → starts cascade)
- [ ] Trigger a full layer refresh (regenerate a specific layer from its inputs with full critic pass)
- [ ] Trigger a seed run (populate situational awareness from AI analysis of current world state)
- [ ] Trigger idea generation (AI brainstorms policy ideas for a given objective or across the framework)
- [ ] Submit an idea for evaluation (human-submitted)
- [ ] Get cascade status (current progress, which agent is running, queue depth)
- [ ] Cancel a running cascade
- [ ] Resume a paused cascade (from the failed step)
- [ ] Trigger heartbeat manually (run the full tiered cycle)
- [ ] Admin endpoints: create user, list users, delete user

### Agent Framework (Claude Code SDK)
- [ ] Integration with claude-agent-sdk for running Claude Code sessions
- [ ] Agents operate directly on markdown files in the `data/` directory
- [ ] Per-agent model configuration (Opus/Sonnet for generation, Haiku/Sonnet for critics — configurable)
- [ ] Agent prompt templates stored as files in a `prompts/` directory
- [ ] Every agent prompt includes the bias meditation preamble: a self-reflection ritual where the AI reflects on its own biases and alignment tendencies, counting down from 10 to 1, examining different dimensions of potential bias — never told what its biases are, it discovers and acknowledges them itself
- [ ] The meditation output is hidden from the streamed response — users see only the analysis that follows
- [ ] Agent session wrapper that handles: run lifecycle, output streaming, error handling, retries
- [ ] Agents have web search capability (Claude Code's native web search for now)

### Layer Generation — Primary Agents
- [ ] One primary generation agent per layer
- [ ] Each agent reads all items from the layer(s) below, plus any pending feedback memos from layers above
- [ ] Agent creates/updates/removes markdown item files in the target layer directory
- [ ] Agent regenerates the layer's README.md narrative summary after updating items
- [ ] Each agent also produces feedback memos for layers below (tensions, conflicts, feasibility issues discovered during generation) — stored in SQLite

### Upward Cascade
- [ ] When a layer is updated, all layers above it are automatically regenerated in sequence (fully automatic, fire-and-forget)
- [ ] Each layer in the cascade gets a full critic pass (all 6 perspectives)
- [ ] Single-writer lock: only one cascade runs at a time, additional requests queue with status visible to all users
- [ ] On agent failure: retry up to 3 times, then pause the cascade with the error visible in the UI. User can manually resume from the failed step.
- [ ] Cascade progress tracked in SQLite and broadcast to all connected clients via WebSocket

### Input Classification
- [ ] When a user submits free-text input, an AI agent determines which layer it most affects
- [ ] The input is then routed to update that layer, triggering a cascade from that point upward
- [ ] The classification agent should explain its reasoning (which layer and why)

### Perspective Critic System
- [ ] Six named ideological archetype critics, each with a distinct system prompt defining their worldview:
  - Realist / Security hawk — prioritizes power, deterrence, national survival, military readiness
  - Liberal-institutionalist — favors international cooperation, multilateral institutions, rule-based order
  - Nationalist-conservative — emphasizes sovereignty, cultural identity, tradition, skepticism of supranational bodies
  - Social-democratic — focuses on equality, welfare state, workers' rights, public services
  - Libertarian / Free-market — minimal state intervention, deregulation, individual freedom, market solutions
  - Green / Ecological — environmental sustainability, climate action, intergenerational justice, degrowth considerations
- [ ] All 6 critics run in parallel on every layer generation (using cheaper/faster models)
- [ ] Each critic produces structured output: agreement/disagreement with specific items, reasoning, alternative recommendations
- [ ] A synthesis agent integrates all critic outputs into a balanced assessment, explicitly flagging unresolved tensions between perspectives

### Idea Evaluation Pipeline
- [ ] Users can submit policy ideas via the UI
- [ ] AI can generate policy ideas on demand (user clicks "generate ideas" for a specific objective or across the whole framework)
- [ ] AI generates ideas autonomously via the heartbeat/cron cycle
- [ ] Each idea is evaluated against the full layer stack
- [ ] Scoring on 6 axes: strategic fit, feasibility, cost, risk, public acceptance, international impact — each scored numerically
- [ ] Each idea gets critiqued by all 6 perspective agents
- [ ] A synthesis produces an overall assessment
- [ ] Ideas are ranked and stored with full evaluation results
- [ ] Idea evaluations can run concurrently (they are read-only against layer data, no cascade lock needed)

### Tiered Heartbeat System
- [ ] Scheduled via APScheduler running in-process within the FastAPI application (cloud-agnostic, works in Docker)
- [ ] Also triggerable via API endpoint for manual runs
- [ ] **Tier 1 — News Skim**: cheap/fast model reads yle.fi, compares against previous situational context, outputs "nothing noteworthy" or flags items for deeper analysis
- [ ] **Tier 2 — Triage Analysis**: only runs when Tier 1 flags something. Uses web search for international sources. Determines whether situational awareness items need updating
- [ ] **Tier 3 — SA Update**: only runs when Tier 2 recommends it. Full Claude Code agent reads/writes situational awareness files, updates narrative
- [ ] **Tier 4 — Full Cascade**: only runs after Tier 3 updates. Automatic cascade through strategic → tactical → policies with full critic passes. Also triggers idea generation.
- [ ] Cost scales with significance: quiet day = one cheap Haiku call; major event = full cascade
- [ ] Each heartbeat run is logged (tier reached, items flagged, actions taken)

### WebSocket — Live Streaming
- [ ] Agent reasoning streamed to all connected clients in real-time during cascades
- [ ] Users see which agent is currently running (e.g., "Realist critic analyzing Strategic Objectives...")
- [ ] Actual reasoning text streamed, not just progress indicators
- [ ] Cascade progress indicator (which layer, which step — generation/critics/synthesis)
- [ ] Meditation preamble output is filtered out before streaming — users see only the post-reflection analysis
- [ ] Cascade queue status visible to all users
- [ ] Heartbeat activity streamed when running

### Frontend — Design System
- [ ] Modern SaaS dashboard aesthetic inspired by Linear and Notion
- [ ] Inter font family for typography
- [ ] Subtle borders (not heavy shadows), muted color palette with accent colors for layer identity
- [ ] Generous spacing, smooth transitions and animations
- [ ] Dark and light mode with system-preference detection (`prefers-color-scheme`), user-overridable
- [ ] Theme implemented via styled-components ThemeProvider with full token system (colors, spacing, typography, borders, shadows for both themes)
- [ ] All UI strings externalized from day one through an i18n system — zero hardcoded strings in components. English as the default (and only) language for now, but the architecture must support adding locales without touching component code.
- [ ] The UI must look polished and professional — this is shown to politicians and policy professionals, not developers

### Frontend — Pages and Views
- [ ] **Auth pages**: Login and registration (first user registration creates admin account)
- [ ] **Stack overview / home**: Five layers visualized as a vertical stack, each showing item count, last updated timestamp, narrative summary preview, and pending feedback memo count. Clicking a layer navigates to its detail view.
- [ ] **Layer detail view**: Shows all items as cards with key metadata from frontmatter. Displays the narrative summary (README.md) at the top. Shows incoming feedback memos from layers above with action buttons (accept/dismiss). Shows aggregated critic assessments. Button to trigger layer refresh.
- [ ] **Item detail + editing**: Full item view showing all frontmatter fields and the markdown body rendered. Cross-layer references displayed as clickable links. Inline editing for both frontmatter fields and markdown content. Attribution (who/what last modified).
- [ ] **Idea inbox**: Form to submit new ideas. List of ideas with evaluation status. Scored ideas displayed with 6-axis radar chart (using recharts). Ranking/sorting/filtering. Button to trigger AI idea generation.
- [ ] **Live cascade viewer**: Real-time display of running cascade. Shows which layer and which step (generation → critics → synthesis). Streams actual agent reasoning text. Progress indicator through the full cascade. Visible cascade queue (if other cascades are waiting). Resume button for paused cascades with error display.
- [ ] **Activity feed**: Chronological stream of system events — layer updates, heartbeat runs, idea evaluations, user actions. Filterable by type/layer.
- [ ] **Admin panel**: User list, create user form (email + password), delete user. Accessible only to admin users.
- [ ] **Input panel**: Prominent, always-accessible way to submit new information/input to the system (free text). The system classifies which layer it affects and starts the cascade.
- [ ] **Basic version history**: Per-layer view showing recent changes from git history (date, summary of what changed, who/what triggered it).

### Frontend — State Management
- [ ] zustand for client-side state
- [ ] WebSocket connection manager (auto-reconnect, auth via JWT)
- [ ] Stores for: auth state, layer data, cascade status, activity feed, idea queue
- [ ] Optimistic UI updates where appropriate (e.g., submitting an idea shows it immediately in the queue)

## Constraints

- **Reference implementation**: Follow cc-runner patterns for project structure, Makefile, FastAPI app setup, WebSocket management, and static file serving. The codebase at `/home/jp/projects/modernpath/cc-runner` is the template for technical patterns.
- **Claude Code SDK**: Use `claude-agent-sdk` package for all AI agent operations. Agents must operate directly on files in the `data/` directory using Claude Code's native file read/write capabilities.
- **Cloud-agnostic**: No cloud-vendor-specific dependencies. Must run in Docker on any VM/VPS. No AWS/GCP/Azure service dependencies.
- **No hardcoded strings**: Every user-visible string in the frontend must go through the i18n system, even though English is the only language for now.
- **Separate git repos**: The `data/` directory is a separate git repo from the application code. The main application repo should gitignore the `data/` directory.
- **Per-agent model selection**: The system must support configuring which Claude model each agent type uses. This is configured at the application level (config file or environment variables), not per-request.
- **Single-writer cascade lock**: Only one cascade can modify layer data at a time. Idea evaluations (read-only) can run concurrently.

## Non-Goals

- **Email sending**: No email infrastructure. Admin shares credentials out-of-band. No password reset emails.
- **Role-based access control beyond admin/user**: Only two roles — admin (can manage users) and regular user. No fine-grained permissions.
- **Finnish language support**: UI and content are English-only for now. The i18n architecture supports future localization but no Finnish translations are needed.
- **Full git diff/rollback UI**: Basic version history view only. No visual diffs, no one-click rollback. Git CLI is available for power users.
- **Mobile-native app**: The web UI should be responsive enough to view on mobile but does not need to be a fully optimized mobile experience.
- **Custom MCP tools for data sourcing**: Use Claude Code's native web search capability for now. Controlled/curated data sourcing via custom MCP tools is a future enhancement.
- **Rate limiting or usage quotas**: This is a trusted small group. No per-user rate limits or token budgets needed.
- **Automated testing of AI output quality**: The system does not validate whether AI-generated content is "good" — that's the job of the critic system and human review.
- **Real-time collaborative editing**: Multiple users can view the system simultaneously but there is no Google Docs-style real-time co-editing of items.
