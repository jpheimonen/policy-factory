# Implementation Summary

## Overview

Comprehensive overhaul to eliminate sanitized, committee-speak output across the entire policy factory. Three work streams were completed: (1) all 21 prompt files rewritten with anti-slop directives and general policy scope, wired through a bias-acknowledge-then-override preamble; (2) agent output text exposed through API with a new heartbeat log viewer page; (3) cascade transcript UI added and existing cascade trigger button verified.

## Key Changes

### Prompt Overhaul (Steps 001–005)
- **Anti-slop preamble**: Created `sections/anti-slop.md` with bias-acknowledge-then-override pattern. Modified `build_agent_prompt()` to auto-prepend it to all prompts via the single choke point — all 13 call sites get the preamble automatically.
- **Values seed redesign**: Rewrote `seed/values.md` to produce controversial tension-pairs (e.g., "Ethnic & Cultural Cohesion vs. Open Immigration") instead of safe domain categories. Added unit tests for `_slugify()` and `_parse_values_output()`.
- **SA seed & 5 generators**: Rewrote `seed/seed.md` and all generator prompts (`values.md`, `situational-awareness.md`, `strategic.md`, `tactical.md`, `policies.md`) — replaced tech-policy framing with general policy scope across all domains (defense, immigration, energy, welfare, EU relations, etc.).
- **6 critics & synthesis**: Broadened all critic Finnish context sections from tech-specific to general policy. Added anti-slop quality criterion — critics now flag sanitized output as a quality failure. Synthesis prompt preserves sharp analysis instead of smoothing into consensus.
- **Heartbeat, classifier & idea prompts**: Rewrote heartbeat skim (raised escalation threshold), triage, and sa-update prompts. Rewrote classifier and idea prompts. Added prompt content validation tests confirming zero "tech policy" references remain across all prompt files.

### Observability Backend API (Step 006)
- Added `output_text` field to cascade detail API response (agent run serialization).
- Added `GET /api/heartbeat/agent-run/{id}` endpoint for on-demand transcript fetching.
- Added API tests for both changes and regression tests for existing heartbeat endpoints.

### Heartbeat Log Viewer (Step 007)
- Built new `HeartbeatLogPage` with three levels of detail: run list → tier-by-tier detail → on-demand transcript expansion.
- Added `offset` parameter to heartbeat history endpoint for pagination.
- Added route (`/heartbeat`), nav link, i18n keys, and styled components.
- Added link from AdminPage heartbeat status card to the log viewer.

### Cascade Transcript UI & Verification (Step 008)
- Added expandable output text transcript to cascade detail panel agent run entries.
- Updated `AgentRunInfo` TypeScript interface to include `output_text`.
- Verified existing LayerDetailPage refresh button satisfies cascade trigger requirement.
- Added E2E tests for heartbeat log page, cascade transcripts, and layer detail refresh button.
- Refactored E2E test infrastructure with global setup/teardown and shared auth helpers.

## Files Modified

### Prompt System
- `src/policy_factory/agent/prompts.py` — Modified `build_agent_prompt()` to auto-prepend anti-slop preamble
- `src/policy_factory/prompts/__init__.py` — Updated docstring to reference new section name
- `src/policy_factory/prompts/sections/anti-slop.md` — **New**: bias-acknowledge-then-override preamble
- `src/policy_factory/prompts/sections/meditation.md` — **Deleted**: replaced by anti-slop.md
- `src/policy_factory/prompts/seed/values.md` — Rewritten: controversial tension-pairs
- `src/policy_factory/prompts/seed/seed.md` — Rewritten: general policy scope
- `src/policy_factory/prompts/generators/values.md` — Rewritten: tension-pair model alignment
- `src/policy_factory/prompts/generators/situational-awareness.md` — Rewritten: intelligence-briefing quality
- `src/policy_factory/prompts/generators/strategic.md` — Rewritten: general policy scope
- `src/policy_factory/prompts/generators/tactical.md` — Rewritten: general policy scope
- `src/policy_factory/prompts/generators/policies.md` — Rewritten: general policy scope
- `src/policy_factory/prompts/critics/realist.md` — Rewritten: broadened Finnish context + anti-slop criterion
- `src/policy_factory/prompts/critics/liberal-institutionalist.md` — Rewritten: broadened + anti-slop criterion
- `src/policy_factory/prompts/critics/nationalist-conservative.md` — Rewritten: broadened + anti-slop criterion
- `src/policy_factory/prompts/critics/social-democratic.md` — Rewritten: broadened + anti-slop criterion
- `src/policy_factory/prompts/critics/libertarian.md` — Rewritten: broadened + anti-slop criterion
- `src/policy_factory/prompts/critics/green-ecological.md` — Rewritten: broadened + anti-slop criterion
- `src/policy_factory/prompts/synthesis/synthesis.md` — Rewritten: preserves sharp analysis
- `src/policy_factory/prompts/heartbeat/skim.md` — Rewritten: raised escalation threshold
- `src/policy_factory/prompts/heartbeat/triage.md` — Rewritten: general policy scope
- `src/policy_factory/prompts/heartbeat/sa-update.md` — Rewritten: anti-slop writing directives
- `src/policy_factory/prompts/classifier/classifier.md` — Rewritten: general policy scope
- `src/policy_factory/prompts/ideas/evaluate.md` — Rewritten: general policy scope
- `src/policy_factory/prompts/ideas/generate.md` — Rewritten: general policy scope

### Backend API
- `src/policy_factory/server/routers/cascade.py` — Added `output_text` to agent run serialization
- `src/policy_factory/server/routers/heartbeat.py` — Added `GET /api/heartbeat/agent-run/{id}` endpoint; added `offset` query parameter to history endpoint

### Frontend
- `ui/src/pages/HeartbeatLogPage.tsx` — **New**: heartbeat log viewer with expandable run/tier/transcript detail
- `ui/src/pages/HeartbeatLogPage.styles.ts` — **New**: styled components for heartbeat log page
- `ui/src/pages/CascadePage.tsx` — Added agent run entries with expandable transcripts to detail panel; updated `AgentRunInfo` interface
- `ui/src/pages/CascadePage.styles.ts` — Added styled components for agent run entries and transcript display
- `ui/src/pages/AdminPage.tsx` — Added link from heartbeat status card to log viewer
- `ui/src/App.tsx` — Added `/heartbeat` route
- `ui/src/components/organisms/Navigation.tsx` — Added "Heartbeat" nav link
- `ui/src/i18n/locales/en.ts` — Added heartbeat and cascade transcript i18n keys
- `ui/src/lib/timeUtils.ts` — Utility updates

### Tests
- `tests/test_agent_prompts.py` — Updated for anti-slop preamble prepending behavior
- `tests/test_prompt_content_validation.py` — **New**: validates zero "tech policy" references across all prompts
- `tests/test_seed_helpers.py` — **New**: unit tests for `_slugify()` and `_parse_values_output()`
- `tests/test_cascade_api.py` — Added tests for `output_text` in cascade detail response
- `tests/test_heartbeat_api.py` — Added tests for new agent-run endpoint
- `tests/test_prompt_loader.py` — Updated for new section name
- `tests/test_agent_gemini.py` — Updated for prompt changes
- `tests/test_agent_session.py` — Updated for prompt changes

### E2E Tests
- `ui/e2e/heartbeat-log.spec.ts` — **New**: E2E tests for heartbeat log page
- `ui/e2e/cascade-viewer.spec.ts` — Extended with cascade transcript tests
- `ui/e2e/layer-detail.spec.ts` — Extended with refresh button tests
- `ui/e2e/global-setup.ts` — **New**: shared E2E global setup
- `ui/e2e/global-teardown.ts` — **New**: shared E2E global teardown
- `ui/e2e/helpers.ts` — **New**: shared E2E auth helpers
- `ui/e2e/00-auth.spec.ts` — Renamed from `auth.spec.ts`
- Various other E2E spec files updated for shared helper pattern

## How to Test

### Prompt Changes (Steps 001–005)
1. Run Python tests: `cd /home/jp/projects/personal/policy-factory && python -m pytest tests/test_agent_prompts.py tests/test_prompt_content_validation.py tests/test_seed_helpers.py -v`
2. Verify no prompt file contains "tech policy" or "technology policy" (covered by `test_prompt_content_validation.py`)
3. Optionally trigger a heartbeat or cascade run to see anti-slop output quality in action

### Observability API (Step 006)
4. Verify cascade detail includes `output_text`: navigate to Cascade page → click a completed cascade → verify agent runs show in the detail panel
5. Test agent-run endpoint: `GET /api/heartbeat/agent-run/{some-id}` (with auth)

### Heartbeat Log Viewer (Step 007)
6. Navigate to `/heartbeat` — verify the page loads with empty state or run history
7. Click the "Heartbeat" link in the navigation bar — confirm it navigates to the log page
8. If runs exist: click a run entry → verify tier-by-tier detail expands
9. In expanded detail: click to expand a tier transcript → verify output text loads
10. Test "Load more" pagination if many runs exist
11. On Admin page: verify the heartbeat status card has a link to the log viewer

### Cascade Transcript UI (Step 008)
12. Navigate to Cascade page → expand a completed cascade history entry
13. Verify individual agent run entries appear below the summary (agent label, target layer, status, duration)
14. For agent runs with output text: click the expand control → verify transcript displays in a scrollable preformatted block
15. Verify multiple transcripts can be expanded simultaneously

### Cascade Trigger Verification (Step 008)
16. Navigate to any Layer Detail page → verify the "Refresh Layer" button is visible
17. Click the refresh button → verify it shows loading state

## Service Status

**Status: Running**

- **Backend (FastAPI):** Running on `http://localhost:8765`
- **Health check:** `GET /api/health/check` returns `{"application": "policy-factory", "status": "ok"}`
- **Frontend:** Served by the backend directly at `http://localhost:8765/` (returns HTTP 200)
- **Vite dev server:** Failed to start — Node.js 19.2.0 is installed but Vite requires 20.19+. This is non-blocking since the built frontend is served by the backend.
- **Started with:** `make dev`

## Notes/Concerns

- The prompt changes are the core of this overhaul — the quality difference will only be visible when running actual agent tasks (heartbeat cycles or cascade runs), which require API keys for Claude/Gemini.
- E2E tests were refactored with global setup/teardown and shared auth helpers for reliability. Some cascade transcript E2E tests may be limited if no completed cascades with agent run output exist in the test environment.
- The `ui/.vite/deps/` directory appears in the diff as cached Vite dependencies — these are build artifacts and not part of the implementation.
