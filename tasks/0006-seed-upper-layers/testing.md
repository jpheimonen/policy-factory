# Testing Plan

## Unit Tests

### Agent Config — New Roles (`tests/test_agent_config.py`)

- [ ] `resolve_model` returns `None` for the `strategic-seed` role when no env var override is set
- [ ] `resolve_model` returns `None` for the `tactical-seed` role when no env var override is set
- [ ] `resolve_model` returns `None` for the `policies-seed` role when no env var override is set
- [ ] `resolve_model` returns the env var value for each new seed role when the corresponding env var is set
- [ ] `resolve_allowed_tools` returns the MCP server reference (no WebSearch) for each new seed role
- [ ] `resolve_tool_set` returns the full tool set for each new seed role
- [ ] `resolve_use_search` returns false for each new seed role
- [ ] All 6 config dictionaries accept each new role without raising `ValueError`

### Agent Config — Existing Role Model Change (`tests/test_agent_config.py`)

- [ ] `resolve_model` returns `None` for the `generator` role when no env var override is set
- [ ] `resolve_model` returns `None` for the `critic` role when no env var override is set
- [ ] `resolve_model` returns `None` for the `heartbeat-sa-update` role when no env var override is set
- [ ] `resolve_model` returns `None` for the `seed` role when no env var override is set
- [ ] `resolve_model` still returns the env var value for existing Claude SDK roles when an override is set
- [ ] Gemini-backed roles still return their hardcoded model strings (unchanged)

### Agent Run Store (`tests/` — extend or add to store tests)

- [ ] `create_agent_run` accepts `None` as the model parameter without error
- [ ] An agent run created with `model=None` can be retrieved and its model field is `None`
- [ ] Existing agent runs with string model values still work correctly after the type change

### Seed Helpers — Slugify and Parsing (`tests/test_seed_helpers.py`)

No new tests needed — the new endpoints use FILE_TOOLS (agent writes directly), so the server-side parsing and slugify helpers are not used by the new endpoints. Existing tests remain valid.

### Context Gathering (new or extended test file)

- [ ] The shared context gathering function returns content from all layers below a given layer
- [ ] For `strategic-objectives`, context includes values and situational-awareness content
- [ ] For `tactical-objectives`, context includes values, SA, and strategic-objectives content
- [ ] For `policies`, context includes all 4 layers below
- [ ] For a layer with no layers below (values), context is empty
- [ ] Content includes both narrative summaries and individual item bodies when they exist
- [ ] Missing or empty layers below produce empty sections in the context string, not errors

### Prerequisite Validation (new test cases in seed API tests)

- [ ] Prerequisite check for strategic-objectives reports failure when values layer is empty
- [ ] Prerequisite check for strategic-objectives reports failure when SA layer is empty
- [ ] Prerequisite check for tactical-objectives reports failure when any of the 3 layers below is empty
- [ ] Prerequisite check for policies reports failure when any of the 4 layers below is empty
- [ ] Prerequisite check passes when all required layers have at least one item

## Integration Tests

### Seed Status Endpoint (`tests/test_seed_api.py` or `tests/test_integration_seeding.py`)

- [ ] `GET /api/seed/status` returns a list of 5 layer entries in hierarchical order (values first, policies last)
- [ ] Each entry in the list contains the layer slug, seeded boolean, and item count
- [ ] When no layers have items, all entries show seeded as false and count as zero
- [ ] When only values and SA are populated, those entries show seeded true with correct counts, others show false
- [ ] When all 5 layers have items, all entries show seeded true with correct counts
- [ ] The endpoint requires authentication (returns 401 without a valid token)

### Strategic Objectives Seed Endpoint (`tests/test_seed_api.py` or `tests/test_integration_seeding.py`)

- [ ] `POST /api/seed/strategic-objectives` returns a prerequisite error when values layer is empty
- [ ] `POST /api/seed/strategic-objectives` returns a prerequisite error when SA layer is empty
- [ ] `POST /api/seed/strategic-objectives` clears existing strategic-objectives items before running the agent
- [ ] `POST /api/seed/strategic-objectives` runs the agent with the `strategic-seed` role
- [ ] `POST /api/seed/strategic-objectives` commits changes to git after the agent completes
- [ ] `POST /api/seed/strategic-objectives` records an agent run in the store
- [ ] `POST /api/seed/strategic-objectives` returns success with a message on successful seeding
- [ ] `POST /api/seed/strategic-objectives` returns failure with a message when the agent errors
- [ ] `POST /api/seed/strategic-objectives` does NOT trigger a cascade
- [ ] The endpoint requires authentication

### Tactical Objectives Seed Endpoint (`tests/test_seed_api.py` or `tests/test_integration_seeding.py`)

- [ ] `POST /api/seed/tactical-objectives` returns a prerequisite error when strategic-objectives layer is empty
- [ ] `POST /api/seed/tactical-objectives` clears existing tactical-objectives items before running the agent
- [ ] `POST /api/seed/tactical-objectives` runs the agent with the `tactical-seed` role
- [ ] `POST /api/seed/tactical-objectives` commits to git and records an agent run on success
- [ ] `POST /api/seed/tactical-objectives` returns failure when the agent errors
- [ ] `POST /api/seed/tactical-objectives` does NOT trigger a cascade
- [ ] The endpoint requires authentication

### Policies Seed Endpoint (`tests/test_seed_api.py` or `tests/test_integration_seeding.py`)

- [ ] `POST /api/seed/policies` returns a prerequisite error when tactical-objectives layer is empty
- [ ] `POST /api/seed/policies` clears existing policies items before running the agent
- [ ] `POST /api/seed/policies` runs the agent with the `policies-seed` role
- [ ] `POST /api/seed/policies` commits to git and records an agent run on success
- [ ] `POST /api/seed/policies` returns failure when the agent errors
- [ ] `POST /api/seed/policies` does NOT trigger a cascade
- [ ] The endpoint requires authentication

### Prompt Template Loading

- [ ] `build_agent_prompt("seed", "strategic", ...)` loads the strategic seed prompt without error and substitutes template variables
- [ ] `build_agent_prompt("seed", "tactical", ...)` loads the tactical seed prompt without error and substitutes template variables
- [ ] `build_agent_prompt("seed", "policies", ...)` loads the policies seed prompt without error and substitutes template variables
- [ ] Each prompt includes the anti-slop preamble when loaded via `build_agent_prompt`

### Existing Seeding Still Works

- [ ] `POST /api/seed/values` still works correctly after the model default change (agent runs, values created)
- [ ] `POST /api/seed/` (SA seeding) still works correctly after the model default change
- [ ] The existing SA seed endpoint still triggers a cascade after completion (behavior unchanged)

## Browser/E2E Tests (`ui/e2e/admin-panel.spec.ts`)

- [ ] The admin page seed status card displays status for all 5 layers (values, SA, strategic objectives, tactical objectives, policies)
- [ ] Each layer row shows a status indicator (seeded or not seeded) and an item count
- [ ] The seed button for strategic objectives is disabled when values or SA layers are not seeded
- [ ] The seed button for tactical objectives is disabled when strategic objectives is not seeded
- [ ] The seed button for policies is disabled when tactical objectives is not seeded
- [ ] Seed buttons for values and SA are always enabled (no prerequisites)
- [ ] Clicking a seed button shows a loading state on that specific button
- [ ] The Full Cascade button is still present at the bottom of the seed card
- [ ] The seed card displays layers in hierarchical order (values at top, policies at bottom)

## Manual Testing

**None** — all verification must be automated.
