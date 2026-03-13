# Research

## Related Code

### Backend — Seed Router

- `src/policy_factory/server/routers/seed.py` — The existing seed router with 3 endpoints: `POST /api/seed/values` (values seeding), `POST /api/seed/` (SA seeding), `GET /api/seed/status`. All new seed endpoints will be added here. The SA seed endpoint (`trigger_seed`) is the primary template for the new endpoints — it clears items, gathers layer content, runs an agent with FILE_TOOLS, commits to git. The values seed endpoint uses a different pattern (no tools, server-side output parsing) which is NOT the pattern for the new endpoints.

- `src/policy_factory/server/routers/__init__.py` — Router registration. The seed router is already imported and exported. No changes needed here since we're adding endpoints to the existing router, not creating a new one.

### Backend — Agent Config

- `src/policy_factory/agent/config.py` — Contains 6 dictionaries that must ALL be updated when adding new roles:
  1. `AgentRole` — Literal type union (line 26–38)
  2. `_DEFAULT_MODELS` — Default model per role (line 52–67)
  3. `_ENV_VAR_MAP` — Env var override names (line 70–82)
  4. `_ALLOWED_TOOLS_BY_ROLE` — Tool permissions (line 116–139)
  5. `_TOOL_SET_BY_ROLE` — MCP tool set identifiers (line 147–159)
  6. `_USE_SEARCH_BY_ROLE` — Google Search grounding flags (line 168–180)

  All 6 must stay in sync. Missing an entry in any one causes a `ValueError` at runtime when that role is used.

- `src/policy_factory/store/agent_run.py` — Has its own `AgentType` Literal (line 17–28) that must also be updated with new seed role names. Note: the `create_agent_run` method takes `model: str` (not `str | None`), which needs to accommodate the `None` model case when switching to CLI defaults.

### Backend — Context Gathering

- `src/policy_factory/cascade/orchestrator.py` — Contains `_gather_generation_context(data_dir, layer_slug)` (line 159–210) which collects content from all layers below a given layer. It reads narrative summaries and individual items, formatting them into a markdown string. This function (or a similar helper) can be reused for the seed endpoints to gather context from layers below.

- `src/policy_factory/cascade/orchestrator.py` — Also contains `layers_below(layer_slug)` (line 74–92) which returns the list of layer slugs below a given layer. This is the correct utility for determining prerequisites and gathering context.

- `src/policy_factory/server/routers/seed.py` — The SA seed endpoint (`trigger_seed`, line 356–511) has its own inline context gathering for the values layer (lines 393–409). This is a hand-rolled version of what `_gather_generation_context` does generically. The new seed endpoints would need content from multiple layers below, making the orchestrator's generic function a better fit.

### Backend — Layer Definitions

- `src/policy_factory/data/layers.py` — Defines `LAYERS` list (line 33–39), `LAYER_SLUGS` set, `list_items()`, `read_item()`, `delete_item()`, `read_narrative()`. All layer CRUD operations for seed endpoints will use these functions. The `list_items()` function is what determines "seeded" status (count > 0).

### Backend — Prompt System

- `src/policy_factory/agent/prompts.py` — `build_agent_prompt(category, name, **variables)` loads anti-slop preamble + template with variable substitution. New seed prompts will be loaded via `build_agent_prompt("seed", "strategic", ...)` etc.

- `src/policy_factory/prompts/loader.py` — `PromptLoader` uses `str.format(**variables)` for substitution. Variables must match `{placeholder}` in template files exactly.

- `src/policy_factory/prompts/seed/` — Currently contains `values.md` and `seed.md`. New files `strategic.md`, `tactical.md`, `policies.md` will be added here.

### Frontend — Admin Page

- `ui/src/pages/AdminPage.tsx` — The admin page component (639 lines). The seed status card is rendered at lines 542–605. It currently shows 2 status items (values, SA) and 3 buttons (Seed Values, Seed SA, Full Cascade). State variables for seed operations are at lines 146–153. Handlers at lines 284–320.

- `ui/src/pages/AdminPage.styles.ts` — Styled components for the admin page. The seed card uses `StatusCard`, `StatusCardTitle`, `StatusItem`, `StatusDot`, `StatusActions`. The `StatusGrid` is a 2-column grid (heartbeat card + seed card side by side). This layout may need adjustment when the seed card grows to show 5 layers.

- `ui/src/i18n/locales/en.ts` — All seed-related i18n keys are in the `admin` namespace (lines 514–529): `seedStatusHeading`, `seedComplete`, `seedNotComplete`, `seedGuidance`, `valuesSeeded`, `valuesNotSeeded`, `saSeeded`, `saNotSeeded`, `seedValuesButton`, `seedValuesRunning`, `seedSaButton`, `seedSaRunning`, `fullCascadeButton`, `fullCascadeRunning`.

### Frontend — API Client

- `ui/src/lib/apiClient.ts` — `apiRequest<T>()` function used for all API calls. Existing seed handlers use it directly (e.g., `apiRequest("/api/seed/values", { method: "POST" })`).

## Reuse Opportunities

- **`_gather_generation_context()` from `cascade/orchestrator.py`** — This function already does exactly what the new seed endpoints need: given a layer slug, it reads content from all layers below and formats it as a markdown string. It can be called directly from the seed endpoints or extracted into a shared utility. Currently it's a private function in the orchestrator module.

- **`layers_below()` from `cascade/orchestrator.py`** — Returns the list of layer slugs below a given layer. Useful for both prerequisite validation (check all layers below have items) and context gathering.

- **`list_items()` from `data/layers.py`** — Already used by the status endpoint to check if layers are seeded. The refactored status endpoint would loop over all 5 layer slugs calling `list_items()` for each.

- **Existing SA seed endpoint pattern** — The `trigger_seed()` function in `seed.py` establishes the exact pattern: clear items → gather context → build prompt → create agent config → record agent run → create session → run → commit. The 3 new endpoints follow this same structure, just targeting different layers with different context.

- **`_slugify()` helper in `seed.py`** — Used by the values seed endpoint for filename generation. Not needed by the new endpoints since the FILE_TOOLS agent writes files directly with its own naming.

- **Existing `StatusCard`, `StatusDot`, `StatusItem` styled components** — Can be reused directly for the redesigned seed card. The vertical layer list will use the same visual primitives.

## Patterns and Conventions

- **Router structure**: All endpoints in a single router file with `APIRouter(prefix="/api/seed")`. Response models defined as Pydantic `BaseModel` classes at the top. Handlers use `Depends(get_current_user)` for auth.

- **Agent lifecycle**: Lazy imports of agent framework (`from policy_factory.agent.config import ...`). Create config → record agent run → create session → run → complete agent run → handle result. This pattern is consistent across seed.py and orchestrator.py.

- **i18n keys**: Flat dot-notation under the `admin` namespace. Pattern for seeded/not-seeded status: `{layer}Seeded` / `{layer}NotSeeded`. Pattern for buttons: `seed{Layer}Button` / `seed{Layer}Running`.

- **Model resolution**: `resolve_model(role)` checks env var first, falls back to `_DEFAULT_MODELS[role]`. Currently returns `str` (never None). When changing Claude SDK roles to `None`, the return type would need to become `str | None`, which propagates to `create_agent_run(model=...)`.

- **Role registration**: Adding a new role requires updating 6 parallel dictionaries in `config.py` plus the `AgentType` literal in `store/agent_run.py`. All must be in sync.

- **Prompt template variables**: Generator prompts use `{upstream_content}`, `{layer_content}`, `{feedback_memos}`, `{cross_layer_context}`. Seed prompts use `{values_content}`, `{current_date}`. The new seed prompts should use descriptive names like `{values_content}`, `{sa_content}`, `{strategic_content}`, `{tactical_content}`.

## Risks and Concerns

- **Variable name mismatch in generator prompts**: The orchestrator passes `context=context` to `build_agent_prompt("generators", ...)` but the generator templates use `{upstream_content}` as the placeholder. This means `{upstream_content}` is not being substituted in cascade generation — it remains as literal text. This is a pre-existing bug, not introduced by this task, but worth noting since the new seed prompts must use matching variable names.

- **`resolve_model()` return type change**: Currently `resolve_model()` returns `str`. Changing Claude SDK roles to `None` in `_DEFAULT_MODELS` means the function must return `str | None`. This propagates to `create_agent_run(model: str)` in the store and to `store.create_agent_run()` calls in every caller that passes the resolved model. The `model` column in the SQLite `agent_runs` table would need to accept NULL.

- **`AgentType` literal divergence**: The `AgentType` in `store/agent_run.py` (line 17–28) is a separate Literal from `AgentRole` in `config.py` (line 26–38). They have different members (e.g., `AgentType` has `"seed"` but not `"values-seed"`). Both need updating but with potentially different values. The store's `AgentType` is used for the `agent_type` column, while `AgentRole` is for config resolution.

- **StatusGrid layout**: The current admin page uses a 2-column `StatusGrid` (heartbeat card | seed card). If the seed card grows significantly with 5 layer rows, it may become visually imbalanced against the heartbeat card. The card layout or grid structure may need adjustment.

- **Seed status API breaking change**: Changing `SeedStatusResponse` from flat fields (`values_seeded`, `sa_seeded`) to a list-based structure is a breaking change. The frontend `SeedStatus` TypeScript interface and all code that destructures the old shape must be updated in lockstep. The admin page currently accesses `seedStatus.values_seeded`, `seedStatus.sa_seeded`, etc. directly.

- **Context size for policies seed**: The policies seed agent receives content from ALL 4 layers below. If each layer has 10+ items with full body text, the prompt context could be very large. The same concern exists for the cascade generators, so this is a known tradeoff rather than a new risk.

- **No concurrency protection**: Multiple seed operations could run simultaneously. If a user seeds strategic objectives and then immediately seeds tactical objectives, the tactical seed might read a partially-written strategic layer. The existing SA seed has the same vulnerability. Not in scope for this task but worth noting.
