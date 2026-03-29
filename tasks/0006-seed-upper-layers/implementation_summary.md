# Implementation Summary

## Overview

Added seed agents for the three upper policy layers — Strategic Objectives, Tactical Objectives, and Policies — so an admin can bootstrap the full 5-layer policy stack without running a cascade. The admin page seed card was redesigned from a flat 2-layer view to a vertical 5-layer list with per-layer seed buttons and prerequisite-based disabling. The seed status API was refactored from hardcoded field pairs to a list-based structure covering all 5 layers.

## Key Changes

- **3 new seed agent roles** (`strategic-seed`, `tactical-seed`, `policies-seed`) registered across all config dictionaries, with existing Claude SDK roles switched from hardcoded model strings to CLI default (`None`)
- **Shared context-gathering utilities** extracted: `gather_context_below()` and `check_prerequisites()` in `cascade/content.py`, replacing duplicated logic in the orchestrator
- **Seed status API refactored** from flat fields (`values_seeded`, `sa_seeded`, etc.) to a list-based response with 5 layer entries, each with `slug`, `display_name`, `seeded`, and `count`
- **3 seed prompt templates** created (`strategic.md`, `tactical.md`, `policies.md`) with layer-appropriate quality standards, time horizons, and output format requirements
- **3 new POST endpoints** (`/api/seed/strategic-objectives`, `/api/seed/tactical-objectives`, `/api/seed/policies`) with prerequisite validation, item clearing, agent execution, and git commit
- **Admin page seed card redesigned** as a vertical 5-layer list with per-layer status dots, item counts, and seed buttons; upper-layer buttons disabled when prerequisites are empty
- **Comprehensive test coverage**: unit tests, integration tests, prompt validation tests, and Playwright E2E tests for the full feature

## Files Modified

### Backend — Agent & Config
- `src/policy_factory/agent/config.py` — Added 3 new seed roles to all 6 config dictionaries; switched Claude SDK roles to `model=None`
- `src/policy_factory/store/agent_run.py` — Added new seed roles to `AgentType` literal; made `model` field nullable
- `src/policy_factory/store/schema.py` — Updated schema for nullable model field

### Backend — Cascade & Content
- `src/policy_factory/cascade/__init__.py` — Exported `gather_context_below` and `check_prerequisites`
- `src/policy_factory/cascade/content.py` — Added `gather_context_below()` and `check_prerequisites()` functions
- `src/policy_factory/cascade/orchestrator.py` — Refactored `_gather_generation_context()` to delegate to shared `gather_context_below()`

### Backend — Seed Prompts
- `src/policy_factory/prompts/seed/strategic.md` — New: strategic objectives seed prompt template
- `src/policy_factory/prompts/seed/tactical.md` — New: tactical objectives seed prompt template
- `src/policy_factory/prompts/seed/policies.md` — New: policies seed prompt template

### Backend — Seed Router
- `src/policy_factory/server/routers/seed.py` — Refactored `SeedStatusResponse` to list-based; added 3 new POST endpoints with shared `_run_upper_seed()` helper; added prerequisite validation

### Frontend
- `ui/src/pages/AdminPage.tsx` — Redesigned seed card as vertical 5-layer list with per-layer buttons, generic seed handler, consolidated loading state
- `ui/src/pages/AdminPage.styles.ts` — Added styled components for layer row layout (`LayerRow`, `LayerInfo`, `LayerName`, `LayerCount`)
- `ui/src/i18n/locales/en.ts` — Replaced hardcoded per-layer i18n keys with parameterized `seedLayerButton`, `seedLayerRunning` templates

### Tests
- `tests/test_agent_config.py` — Added tests for 3 new seed roles; updated existing tests for `model=None` defaults
- `tests/test_cascade_content.py` — Added `TestGatherContextBelow` and `TestCheckPrerequisites` test classes
- `tests/test_seed_api.py` — Added unit tests for 3 new endpoints: auth, prerequisites, prerequisite failure preservation
- `tests/test_integration_seeding.py` — Added integration tests for upper-layer seeding: item creation, clearing, git commits, agent runs, no cascade trigger
- `tests/test_prompt_content_validation.py` — Registered 3 new seed prompts in `_TEMPLATE_VARS`
- `tests/test_store_cascade.py` — Added tests for nullable model in agent run store
- `ui/e2e/admin-panel.spec.ts` — Added Playwright E2E tests: 5-layer display, ordering, disabled buttons, prerequisite enabling, Full Cascade presence

## How to Test

1. **Admin Page — Seed Card Display**: Navigate to `/admin`. Verify the seed status card shows 5 layers in order: Values, Situational Awareness, Strategic Objectives, Tactical Objectives, Policies. Each row should have a status dot, display name, and a seed button.

2. **Prerequisite Disabling**: With empty layers, verify Values and SA seed buttons are enabled, while Strategic Objectives, Tactical Objectives, and Policies buttons are disabled. Seed Values first, then SA — the Strategic Objectives button should become enabled.

3. **Seed Upper Layers**: After seeding Values and SA, click "Seed Strategic Objectives". Verify it runs the seed agent, the status refreshes showing strategic objectives as seeded with item count, and the Tactical Objectives button becomes enabled. Continue seeding each layer in order.

4. **Prerequisite Validation**: Try seeding an upper layer via API when prerequisites are missing (e.g., `POST /api/seed/strategic-objectives` with no values seeded). Verify the endpoint returns a failure response naming the empty prerequisite layers.

5. **Seed Status API**: Call `GET /api/seed/status` and verify it returns a `layers` list with 5 entries in hierarchical order, each with `slug`, `display_name`, `seeded`, and `count` fields.

6. **Full Cascade Button**: Verify the Full Cascade button is still present at the bottom of the seed card and functions as before.

7. **Loading State Mutual Exclusion**: While a seed operation is running, verify all other seed buttons become disabled until it completes.

## Service Status

**Status: Running**

- **Backend (FastAPI)**: Running at http://localhost:8765 — health check `GET /api/health/check` returns `{"application":"policy-factory","status":"ok"}`
- **Frontend**: Served by the backend directly at http://localhost:8765 (Vite dev server not available due to Node.js 19.2.0; requires 20.19+)
- **Started with**: `make dev`

## Notes/Concerns

- The SA seed endpoint (`POST /api/seed/`) has no prerequisite validation — it handles missing values gracefully with a fallback string. This is intentional and matches the original behavior.
- Upper-layer seed agents require an AI model (Claude via CLI) to run. If no API key / CLI is configured, the seed operation will fail at the agent execution step. The prerequisite validation and UI behavior can still be tested independently.
- The 3 new seed prompts are tailored for Finnish policy analysis with specific quality standards (time horizons, institutional specificity, trade-off honesty). The generated content quality depends on the underlying model.
