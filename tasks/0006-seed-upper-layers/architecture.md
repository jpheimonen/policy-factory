# Architecture

## Components Affected

### 1. Agent Config (`src/policy_factory/agent/config.py`)

**New roles**: Add three new agent roles — `strategic-seed`, `tactical-seed`, `policies-seed`. Each requires entries in all 6 parallel dictionaries:
- Model: `None` (CLI picks its default, currently Opus 4.6)
- Allowed tools: MCP server reference only (file tools, no WebSearch)
- Tool set: full (list, read, write, delete)
- Google Search grounding: disabled
- Environment variable overrides following the existing naming pattern

**Existing role model change**: The 4 existing Claude SDK roles (`generator`, `critic`, `heartbeat-sa-update`, `seed`) change from their hardcoded model string to `None`. This lets them use whatever the CLI's current default model is. The `resolve_model()` function's return type changes to accommodate `None` — when the default is `None` and no env var override is set, it returns `None`. Callers that pass the resolved model to `create_agent_run()` must handle the `None` case (see store changes below).

### 2. Agent Run Store (`src/policy_factory/store/agent_run.py`)

**AgentType literal**: Add the 3 new seed role names so they are valid `agent_type` values for run tracking.

**Model field**: The `create_agent_run` method's `model` parameter and the `AgentRun` dataclass's `model` field change from `str` to `str | None` to accommodate roles that use the CLI default (where the model name is not known at call time). The SQLite column already accepts NULL since it's not constrained as NOT NULL.

### 3. Context Gathering — Extract Shared Helper

The orchestrator's `_gather_generation_context()` function collects content from all layers below a given layer. The seed endpoints need this same capability. Rather than duplicating the inline context gathering that the SA seed endpoint does, extract this function to a shared location (or make it public) so both the cascade orchestrator and the seed router can use it.

The existing `layers_below()` function from the orchestrator is also needed by the seed endpoints for prerequisite validation. It should similarly be accessible from the seed router.

### 4. Seed Router (`src/policy_factory/server/routers/seed.py`)

**Three new endpoints**: Each follows the SA seed pattern:

- `POST /api/seed/strategic-objectives` — Seeds the strategic objectives layer. Validates that values and situational-awareness layers have items. Clears existing strategic-objectives items. Gathers content from values and SA layers. Runs the `strategic-seed` agent. Commits to git.

- `POST /api/seed/tactical-objectives` — Seeds the tactical objectives layer. Validates that values, SA, and strategic-objectives layers have items. Clears existing tactical-objectives items. Gathers content from all 3 layers below. Runs the `tactical-seed` agent. Commits to git.

- `POST /api/seed/policies` — Seeds the policies layer. Validates that all 4 layers below have items. Clears existing policies items. Gathers content from all 4 layers below. Runs the `policies-seed` agent. Commits to git.

**Prerequisite validation**: Before running the agent, each endpoint checks that all layers below the target have at least one item (using `list_items()`). If any prerequisite layer is empty, the endpoint returns immediately with an error response indicating which layer(s) are missing. This is checked server-side regardless of what the UI does.

**Response model**: All 3 new endpoints return the same response shape — success boolean plus a message. They do NOT trigger cascades, so there is no cascade_id in the response.

**Refactored status endpoint**: The existing `GET /api/seed/status` response changes from hardcoded field pairs to a list of layer statuses. Each entry contains the layer slug, whether it has items, and the item count. The list covers all 5 layers in hierarchical order. This is a breaking change for the frontend.

### 5. Seed Prompt Templates (`src/policy_factory/prompts/seed/`)

Three new prompt template files — `strategic.md`, `tactical.md`, `policies.md`. Each prompt:

- Receives content from all layers below as template variables (named descriptively: the values content, the SA content, etc.)
- Instructs the agent to use `write_file` to create items in the target layer's directory
- Instructs the agent to create a `README.md` narrative summary for the layer
- Follows the same quality standards and anti-slop tone as the existing generator prompts for that layer
- Differs from the cascade generator prompts in that it's bootstrapping from scratch rather than refining existing content — no feedback memos, no cross-layer context, no existing items to evaluate
- Specifies the expected frontmatter fields (title, status, created, last_modified, last_modified_by, references) and the `last_modified_by` value to use for each seed role

The prompt content itself should draw heavily from the existing cascade generator prompts for each layer (strategic.md, tactical.md, policies.md in the generators directory) since they define the quality expectations, controversy standards, and output format for each layer. The key difference is framing: seed prompts say "create the initial set" while generator prompts say "review and update the existing set."

### 6. Admin Page (`ui/src/pages/AdminPage.tsx`)

**Seed status card redesign**: The seed status card changes from showing 2 status items with a flat button bar to a vertical layer list. Each row shows:
- The layer's display name
- A status indicator (seeded vs. not seeded) with item count
- A seed button for that layer

The layers display in hierarchical order (values at top, policies at bottom). Seed buttons for upper layers are disabled when any layer below them is empty. The disabled state is derived from the seed status data — if any entry below the target in the list has count zero, that button is disabled.

Per-button loading states are maintained individually (a dictionary or parallel state tracking), since seeding one layer shouldn't visually affect another's button.

The Full Cascade button remains at the bottom of the card, outside the per-layer rows.

**Seed status type**: The TypeScript interface for the seed status response changes to match the new list-based API shape. All existing code that destructures `seedStatus.values_seeded` or `seedStatus.sa_seeded` must be updated to find the relevant entry by slug from the list.

**New handlers**: Three new handler functions for triggering the upper-layer seeds, following the same pattern as the existing values and SA handlers — call the API endpoint, set loading state, refresh status on completion.

### 7. Admin Page Styles (`ui/src/pages/AdminPage.styles.ts`)

The `StatusGrid` currently uses a 2-column grid layout (heartbeat card | seed card). With the seed card growing to show 5 layer rows, the layout may need adjustment. Options include making the seed card span full width below the heartbeat card, or keeping the grid but allowing the seed card to be taller. The existing `StatusItem` and `StatusDot` components can be reused for the per-layer rows. A new styled component may be needed for the per-layer row that includes the status info and the button side by side.

### 8. i18n (`ui/src/i18n/locales/en.ts`)

New translation keys in the `admin` namespace for:
- Status text for each new layer (seeded with count, not seeded)
- Seed button labels for each new layer
- Running/loading state labels for each new layer
- A guidance message about seeding order (displayed when upper-layer buttons are disabled)

The existing values and SA keys are replaced or restructured to match the new pattern, since the UI is being redesigned from individual lines to a uniform per-layer list.

## New Entities/Endpoints

### API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/seed/strategic-objectives` | Seed the strategic objectives layer |
| POST | `/api/seed/tactical-objectives` | Seed the tactical objectives layer |
| POST | `/api/seed/policies` | Seed the policies layer |

All require JWT authentication. All return a response with success status and message. All validate prerequisites before proceeding.

The existing `GET /api/seed/status` endpoint is modified (not a new endpoint) to return the list-based response covering all 5 layers.

### Agent Roles

| Role Key | Model | Tools | Web Search |
|----------|-------|-------|------------|
| `strategic-seed` | CLI default (None) | Full file tools via MCP | No |
| `tactical-seed` | CLI default (None) | Full file tools via MCP | No |
| `policies-seed` | CLI default (None) | Full file tools via MCP | No |

### Prompt Templates

| File | Template Variables |
|------|--------------------|
| `prompts/seed/strategic.md` | Content from values layer, content from SA layer, current date |
| `prompts/seed/tactical.md` | Content from values layer, content from SA layer, content from strategic objectives layer, current date |
| `prompts/seed/policies.md` | Content from all 4 layers below, current date |

## Integration Points

### Seed Router → Context Gathering

The seed endpoints need to gather formatted content from layers below the target. This is the same operation the cascade orchestrator performs for its generation step. The context gathering logic (currently private in the orchestrator) becomes a shared utility that both modules call. The seed endpoints call it with the target layer slug, and it returns the assembled content from all layers below.

### Seed Router → Agent Framework

Each seed endpoint creates an `AgentConfig` with the appropriate role, builds the prompt via `build_agent_prompt("seed", template_name, ...)`, creates an `AgentSession`, and calls `run()`. This is identical to how the SA seed endpoint and the cascade generation runner interact with the agent framework. No new integration patterns are introduced.

### Seed Router → Data Layer

The seed endpoints use `list_items()` for prerequisite validation and `delete_item()` for clearing. The agent handles writing via its file tools. After the agent completes, the endpoint calls `commit_changes()` for git. These are all existing integration points.

### Seed Router → Store

Each seed endpoint records an agent run via `create_agent_run()` before running and `complete_agent_run()` after. The `model` parameter may be `None` for CLI-default roles, which the store must accept.

### Frontend → Seed Status API

The admin page fetches `GET /api/seed/status` on load and after any seed operation completes. The response shape changes, so the frontend type and all consuming code must be updated in the same change.

### Frontend → Seed Trigger APIs

Three new POST calls from the admin page to the new seed endpoints. These follow the existing pattern of the values and SA seed button handlers.

## Failure Modes

### Prerequisite validation failure
The endpoint returns an error response immediately without running any agent. The response indicates which layer(s) below are empty. The frontend should already prevent this via disabled buttons, so this is a defense-in-depth check.

### Agent failure during seeding
The target layer has already been cleared when the agent runs. If the agent fails partway through, the layer may be partially populated. This is the same behavior as the existing SA seed — acceptable because seeding is re-runnable. The agent run is recorded as failed in the store. The frontend shows the seed button as available again, and the admin can retry.

### Git commit failure after seeding
The agent has already written files, so the content exists on disk even if the git commit fails. This matches the existing pattern — commit failures are logged as warnings but don't cause the endpoint to return an error. The content is usable; it just won't appear in git history until the next successful commit.

### Large context size for policies seed
The policies seed agent receives content from all 4 layers below. If layers are heavily populated, the prompt could exceed context limits. This would trigger a `ContextOverflowError` in the agent session, which is non-retryable. The endpoint returns a failure response. Mitigation is the same as for cascade generators — the prompt templates should be concise, and the context gathering should use narrative summaries where available rather than full item bodies. This is a known tradeoff, not a new risk.

### Breaking change coordination
The seed status API response shape changes. If the frontend and backend are deployed out of sync, the admin page's seed card will break. This is mitigated by making both changes in the same task and building the frontend as part of the backend package (static assets served by FastAPI).
