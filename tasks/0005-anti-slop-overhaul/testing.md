# Testing Plan

## Unit Tests

### Prompt Loading — Anti-Slop Preamble Auto-Prepend

- [ ] `build_agent_prompt()` returns content that starts with the anti-slop preamble section content before the template body
- [ ] `build_agent_prompt()` separates the anti-slop preamble from the template body with a double newline
- [ ] `build_agent_prompt()` still performs template variable substitution correctly when the preamble is prepended
- [ ] `build_agent_prompt()` raises `FileNotFoundError` when the anti-slop section file is missing (not silently omitted)
- [ ] `build_agent_prompt()` raises `FileNotFoundError` when the template file is missing (existing behavior preserved)
- [ ] `build_agent_prompt()` works correctly when called with no template variables (preamble still prepended)
- [ ] The anti-slop section file loads correctly via `load_section("anti-slop")`
- [ ] The old `meditation.md` section file no longer exists (or if it does, is not loaded by `build_agent_prompt`)

### Prompt Loading — Real Prompt Files

- [ ] Every prompt file under `src/policy_factory/prompts/` loads without error via `build_agent_prompt()` with the required template variables for that prompt
- [ ] No prompt file under `src/policy_factory/prompts/` contains the string "tech policy" (case-insensitive)
- [ ] No prompt file under `src/policy_factory/prompts/` contains the string "technology policy" (case-insensitive)
- [ ] The anti-slop section file (`sections/anti-slop.md`) exists and is non-empty

### Heartbeat Agent Run Endpoint

- [ ] `GET /api/heartbeat/agent-run/{agent_run_id}` returns 200 with the full agent run record including `output_text` when the agent run exists
- [ ] `GET /api/heartbeat/agent-run/{agent_run_id}` returns `output_text` as `null` when the agent run completed without output text stored
- [ ] `GET /api/heartbeat/agent-run/{agent_run_id}` returns 404 when the agent run ID does not exist
- [ ] `GET /api/heartbeat/agent-run/{agent_run_id}` returns 401 without authentication
- [ ] The response includes all standard agent run fields: `id`, `agent_type`, `agent_label`, `model`, `target_layer`, `started_at`, `completed_at`, `success`, `error_message`, `cost_usd`, `output_text`

### Cascade Detail — Output Text Exposure

- [ ] `GET /api/cascade/{cascade_id}` response includes `output_text` in each agent run dict
- [ ] `output_text` is `null` for agent runs that have no stored output
- [ ] `output_text` contains the full stored text for agent runs that completed with output
- [ ] Existing fields in the agent run dict are unchanged (id, agent_type, agent_label, model, target_layer, started_at, completed_at, success, error_message, cost_usd)

### Heartbeat History — Existing Behavior Preserved

- [ ] `GET /api/heartbeat/history` continues to return structured logs with `agent_run_id` per tier entry (no regressions from adding the new endpoint)
- [ ] `GET /api/heartbeat/history` accepts an `offset` query parameter for pagination (the store already supports it — the endpoint must expose it)
- [ ] `GET /api/heartbeat/history` with `offset` and `limit` returns the correct slice of runs in reverse chronological order
- [ ] `GET /api/heartbeat/latest` continues to return the most recent run with structured log (no regressions)

## Integration Tests

### Prompt Preamble Integration

- [ ] Loading a real generator prompt (e.g., `generators/values`) via `build_agent_prompt()` returns content that begins with the anti-slop preamble followed by the generator-specific instructions
- [ ] Loading a real critic prompt (e.g., `critics/realist`) via `build_agent_prompt()` returns content that begins with the anti-slop preamble followed by the critic-specific instructions
- [ ] Loading a real heartbeat prompt (e.g., `heartbeat/skim`) via `build_agent_prompt()` returns content that begins with the anti-slop preamble followed by the heartbeat-specific instructions
- [ ] Loading a seed prompt (e.g., `seed/values`) via `build_agent_prompt()` returns content that begins with the anti-slop preamble followed by the seed-specific instructions

### Heartbeat Agent Run API Integration

- [ ] Create a heartbeat run with tier entries that have `agent_run_id` values → create corresponding agent runs with `output_text` → verify `GET /api/heartbeat/agent-run/{id}` returns the correct output text for each agent run
- [ ] Create a cascade with multiple agent runs including output text → verify `GET /api/cascade/{id}` returns all agent runs with their output text included

### Values Seed Output Format Compatibility

- [ ] The values seed prompt, when loaded, does not break the expected output format contract — specifically, it instructs the model to produce `---` delimited frontmatter blocks that the existing `_parse_values_output()` function can parse
- [ ] The `_slugify()` function correctly handles tension-pair style titles (e.g., "Ethnic & Cultural Cohesion vs. Open Immigration" produces a valid, non-empty filename slug)
- [ ] The `_slugify()` function handles titles with special characters: ampersands, "vs." notation, hyphens, long multi-word titles

## Browser/E2E Tests (for UI changes)

### Heartbeat Log Page — Navigation and Structure

- [ ] The heartbeat log page is accessible at `/heartbeat` after login
- [ ] The navigation bar includes a link to the heartbeat log page
- [ ] The page shows an empty state message when no heartbeat runs exist

### Heartbeat Log Page — Run List

- [ ] When heartbeat runs exist, the page displays a list of run entries
- [ ] Each run entry shows the trigger type (scheduled or manual)
- [ ] Each run entry shows the highest tier reached
- [ ] Run entries are displayed in reverse chronological order (most recent first)

### Heartbeat Log Page — Expandable Detail

- [ ] Clicking a heartbeat run entry expands it to show tier-by-tier detail
- [ ] The expanded detail shows tier number, escalation status, and outcome for each tier
- [ ] Each tier entry has a control to expand the full agent output transcript
- [ ] Expanding the transcript section shows the agent's output text content
- [ ] Clicking the same run entry again collapses the detail

### Cascade Page — Output Text Transcripts

- [ ] The cascade detail panel shows agent run entries with an expand control for output text
- [ ] Expanding an agent run entry in the cascade detail shows the `output_text` content
- [ ] Agent runs without output text show an appropriate empty/unavailable state when expanded

### Admin Page — Heartbeat Log Link

- [ ] The heartbeat status card on the admin page contains a link to the heartbeat log page
- [ ] Clicking the link navigates to the heartbeat log page

### Layer Detail Page — Cascade Refresh Button

- [ ] The layer detail page displays a refresh/cascade trigger button
- [ ] Clicking the refresh button triggers a cascade (button becomes disabled or shows loading state)

## Manual Testing

**None** — all verification of code changes must be automated.

**Note on prompt quality:** The automated tests verify that prompt files load correctly, contain no "tech policy" references, and have proper template variables. They cannot verify that the rewritten prompts actually produce better LLM output — that is inherently non-automatable. As noted in the architecture spec, prompt quality is verified by running the system and reviewing outputs via the observability tools built in this task. This verification happens post-implementation, not as part of the test suite.
