# Research

## Related Code

### Prompt Files (21 total — all need anti-slop + scope changes)

Every prompt file lives under `src/policy_factory/prompts/` and contains the full agent instruction as a markdown template with `{variable}` placeholders.

- `sections/meditation.md` — Bias meditation preamble. Currently a generic 10-to-1 countdown asking the model to reflect on bias categories (ideological leanings, cultural assumptions, recency bias, etc.). Does NOT instruct the model to override its training defaults. This file is the primary target for the bias-acknowledge-then-override redesign.

- `seed/values.md` — Values seed prompt. Produces initial values from LLM knowledge (no tools). Pre-specifies 10 safe domain categories ("Sovereignty and Self-Determination", "Environmental Responsibility", etc.) and asks for "cross-partisan" values that "reflect broad Finnish consensus". This is why output is committee-speak. Needs complete redesign around controversial tension-pairs.

- `seed/seed.md` — SA seed prompt. References "Finland's tech policy analysis system" and lists 10 tech-centric topics. Needs scope broadening to general policy.

- `generators/values.md` — Values generator (cascade). References "cross-party tech policy analysis system" and lists tech-centric evaluation criteria. Same scope problem as the seed prompt.

- `generators/situational-awareness.md` — SA generator. References "cross-party tech policy analysis system". Lists tech-centric assessment areas. Needs anti-slop directive and scope broadening.

- `generators/strategic.md` — Strategic objectives generator. References "cross-party tech policy analysis system". Needs scope broadening.

- `generators/tactical.md` — Tactical objectives generator. References "cross-party tech policy analysis system". Needs scope broadening.

- `generators/policies.md` — Policies generator. References "cross-party tech policy analysis system". Needs scope broadening.

- `critics/realist.md` — Realist critic. Framework text references tech-specific concerns but the analytical framework itself is sound. Needs anti-slop directive and scope broadening.

- `critics/liberal-institutionalist.md` — Liberal-institutionalist critic. Same pattern as realist.

- `critics/nationalist-conservative.md` — Nationalist-conservative critic. Same pattern.

- `critics/social-democratic.md` — Social-democratic critic. Same pattern.

- `critics/libertarian.md` — Libertarian critic. Same pattern.

- `critics/green-ecological.md` — Green/ecological critic. Same pattern.

- `synthesis/synthesis.md` — Critic synthesis agent. References "cross-party tech policy analysis system". Needs scope broadening and anti-slop directive.

- `classifier/classifier.md` — Input classifier. References "tech policy analysis system". Needs scope broadening.

- `heartbeat/skim.md` — Tier 1 news skim. References "tech policy analysis system". Significance criteria are all tech-focused ("Change Finland's geopolitical technology position", "Affect EU technology regulation", etc.). Needs broadened criteria and raised threshold.

- `heartbeat/triage.md` — Tier 2 triage. References "tech policy analysis system". Threshold text says "would this change a policy recommendation if policymakers knew about it?" — this is actually the right threshold, but the significance criteria from Tier 1 feed in pre-filtered items.

- `heartbeat/sa-update.md` — Tier 3 SA update. References "tech policy analysis system". Writing instructions say "Be factual. Stick to what the evidence supports." but have no anti-slop directive, so output becomes bureaucratic corporatespeak.

- `ideas/evaluate.md` — Idea evaluator. References "tech policy analysis system". Needs scope broadening.

- `ideas/generate.md` — Idea generator. References "tech policy analysis system". Needs scope broadening.

### Prompt Loading Mechanism

- `prompts/loader.py` — `PromptLoader` class with `load(category, name, **variables)` and `load_section(name)` methods. Section loading is available but meditation section is NOT automatically prepended — it's only referenced in docstring examples. The `build_agent_prompt()` wrapper in `agent/prompts.py` calls `load_prompt()` directly without any section prepending.

- `agent/prompts.py` — Thin wrapper `build_agent_prompt(category, name, **variables)` that just calls `load_prompt()`. No meditation injection logic.

**Key finding:** The meditation preamble file exists but is never actually loaded or prepended to any prompt in production. If the redesigned meditation/anti-slop preamble should be automatically prepended, either (a) each prompt file needs to include it inline, or (b) the loading mechanism needs modification to auto-prepend sections.

### Agent Configuration

- `agent/config.py` — `AgentConfig` dataclass, model resolution, tool set mapping. Defines all 11 agent roles. Values-seed uses `gemini-2.5-flash` with no tools. Heartbeat-skim and heartbeat-triage use `gemini-2.5-flash` with Google Search grounding. Heartbeat-sa-update uses `claude-sonnet-4` with MCP file tools + WebSearch.

### Heartbeat Orchestrator

- `heartbeat/orchestrator.py` — Four-tier escalation chain. Tier 1 fetches Yle RSS, sends to skim agent. Tier 2 receives flagged items, investigates further. Tier 3 updates SA files. Tier 4 triggers cascade + idea generation. Each tier calls `_run_tier_agent()` which creates agent run records, executes the session, parses escalation markers from output, and updates heartbeat tier records. The escalation markers are `NOTHING_NOTEWORTHY` (Tier 1) and `NO_UPDATE_NEEDED` (Tier 2).

### Backend Store — What Data Exists

- `store/agent_run.py` — `AgentRunStoreMixin`. The `AgentRun` dataclass has `output_text: str | None`. The `complete_agent_run()` method accepts and stores `output_text`. The `list_agent_runs()` method returns full `AgentRun` objects including `output_text`.

- `store/heartbeat.py` — `HeartbeatMixin`. The `HeartbeatRun` dataclass has `structured_log: list[TierEntry]`. Each `TierEntry` has `tier`, `escalated`, `outcome`, `agent_run_id`, `started_at`, `ended_at`. The `agent_run_id` field links each tier to its agent run record (which contains `output_text`).

- `store/schema.py` — Schema defines `agent_runs` table with `output_text TEXT` column and `heartbeat_runs` table with `structured_log TEXT` (JSON) column.

### Backend API — What's Exposed vs. Missing

- `server/routers/heartbeat.py` — Three endpoints:
  - `GET /api/heartbeat/history` — Returns heartbeat runs with structured log (tier entries). **Does include `agent_run_id` per tier.** Does NOT include agent output text.
  - `GET /api/heartbeat/latest` — Same format, single run.
  - `GET /api/heartbeat/status` — System-level status (scheduler active, interval, next run, is running, latest run summary).

- `server/routers/cascade.py` — Six endpoints:
  - `GET /api/cascade/{cascade_id}` — Returns cascade detail with `agent_runs` list. **Agent runs do NOT include `output_text`** — the serialization at lines 323-350 explicitly selects only `id, agent_type, agent_label, model, target_layer, started_at, completed_at, success, error_message, cost_usd`.
  - `GET /api/cascade/history` — Summary list without agent runs.
  - `POST /api/cascade/refresh` — Trigger cascade from specific layer. Already exists, already works.

**Key finding for observability:** The data is fully stored in the DB. The gap is that API responses don't serialize `output_text`. Adding it is a small change to the response serialization. No schema migration needed.

### Frontend — Existing Patterns

- `App.tsx` — Route structure. Protected routes inside `AppLayout`. Adding a new page requires: create page component, add route in App.tsx, add nav link in Navigation.tsx (if it should appear in nav bar).

- `pages/AdminPage.tsx` — Already has a heartbeat status card showing scheduler state, last run time, highest tier reached, and a manual trigger button. This is a minimal status view. The heartbeat log viewer is a new page that shows run history with tier-by-tier detail and expandable transcripts.

- `pages/CascadePage.tsx` — Has a `CascadeIdleView` with history list. Each history entry is expandable to show a `CascadeDetailPanel` that fetches `GET /api/cascade/{id}` and shows agent runs. **The detail panel already shows per-agent-run info but without output text.** This is the closest existing pattern to what the heartbeat log viewer needs.

- `pages/HistoryPage.tsx` — Git commit history per layer. Uses a list with "load more" pagination. Good pattern reference for pagination.

- `pages/LayerDetailPage.tsx` — Already has a "Refresh" button (line 228-237) that calls `POST /api/cascade/refresh` with the layer slug. **The cascade trigger from UI already exists on every layer detail page.** The button is labeled "Refresh" and uses `$variant="secondary"`.

- `stores/cascadeStore.ts` — Zustand store updated via WebSocket events and REST. Standard pattern for all stores.

- `lib/apiClient.ts` — `apiRequest<T>(path, options)` — all API calls go through this. Handles auth, token refresh, error parsing.

- `i18n/locales/en.ts` — All UI strings use translation keys. Any new page or component needs corresponding entries here.

- Styled components pattern: each page has a `.styles.ts` companion file exporting named styled components. No CSS modules or utility classes.

## Reuse Opportunities

- **CascadeDetailPanel pattern (CascadePage.tsx)** — The expandable history entry with detail fetching is very close to what the heartbeat log viewer needs. The click-to-expand → fetch detail → show sub-components pattern can be directly adapted for heartbeat runs with tier detail.

- **Cascade history list (CascadePage.tsx)** — The `CascadeIdleView` component with `HistoryEntry`, `HistoryEntryHeader`, `HistoryEntryLeft/Right` styled components provides the visual pattern for the heartbeat log list.

- **AdminPage heartbeat status card** — Already shows basic heartbeat status. Could link to the new heartbeat log page.

- **LoadingState, ErrorState, EmptyState molecules** — Reusable across all new UI.

- **formatRelativeTime, formatDuration utilities** — Already exist in `lib/timeUtils.ts`.

- **apiRequest** — Standard API calling pattern for all new endpoints.

- **LayerDetailPage refresh button** — Already exists and works. The "trigger cascade from UI" requirement may already be satisfied. Needs verification of whether this button is visible and discoverable enough.

- **PromptLoader section mechanism** — `load_section()` and `load_sections()` exist but aren't used. Could be used to auto-prepend the redesigned meditation/anti-slop section to all prompts, or the section content could be inlined into each prompt file.

## Patterns and Conventions

- **Prompt files**: Markdown with `{variable}` placeholders for Python `str.format()`. No frontmatter. Flat structure under `prompts/{category}/{name}.md`.

- **Page structure**: Each page is a single `.tsx` file with a matching `.styles.ts` file. Pages use `PageWrapper` as root container. Headers use `PageHeader`, `HeaderLeft`, `HeaderRight` pattern.

- **State management**: Zustand stores in `stores/`. Each store is a `create()` call with interface definitions. Stores are updated via REST (initial load) and WebSocket events (real-time).

- **API pattern**: FastAPI routers in `server/routers/`. Pydantic models for request/response. JWT auth via `Depends(get_current_user)`. Background tasks via `asyncio.create_task()`.

- **i18n**: All user-visible strings use `t("key.path")` from `useTranslation()`. Keys organized by page/feature namespace in `i18n/locales/en.ts`.

- **Component hierarchy**: atoms → molecules → organisms → pages. Styled-components CSS-in-JS.

- **Navigation**: Horizontal nav bar with links to main pages. New top-level pages need a nav link and route entry.

## Risks and Concerns

- **Meditation preamble is not wired up.** The section file exists and the loading mechanism supports sections, but no production code actually loads or prepends it. This means either: (a) the anti-slop preamble must be inlined into each of the 21 prompt files (code duplication but simple), or (b) the prompt loading mechanism needs modification to auto-prepend it (cleaner but requires code changes to `build_agent_prompt` or the callers). Option (b) is cleaner but adds a code change to what would otherwise be a prompt-only task.

- **Gemini models may respond differently to anti-slop directives.** Several agents (heartbeat skim/triage, synthesis, classifier, idea evaluator/generator, values-seed) use Gemini Flash models, not Claude. The bias-acknowledge-then-override meditation was POCed with Claude. Gemini may handle these instructions differently. The prompt wording may need to be model-agnostic or we accept it works somewhat differently across models.

- **Values seed is a one-shot text generator.** It produces all values in a single response with `---` delimiters. The output parsing logic in the seed router must match whatever new format is specified. If values change from domain-based titles to tension-pair titles, any code that references value filenames by the old naming scheme could break. Need to check if anything hardcodes value filenames.

- **Heartbeat Yle RSS content.** The research confirmed RSS is the only news source, but we couldn't verify whether Yle's RSS actually carried international stories like the Iran strikes. Without logs, this remains unknown. The observability work is a prerequisite for diagnosing this properly.

- **LayerDetailPage already has a refresh button.** The requirement mentions "no UI for cross-layer cascade triggers" but the button exists at line 228-237 of `LayerDetailPage.tsx`. It calls `POST /api/cascade/refresh` with the current layer slug. This may already satisfy the requirement — or the requirement may be about something more specific (like triggering updates of layer X from within layer Y's detail page).

- **`output_text` can be large.** Agent outputs can be thousands of characters. The API needs to handle this in responses without performance issues. Consider whether `output_text` should be fetched on-demand (separate endpoint) vs. included in list responses. The current `list_agent_runs()` returns full objects including `output_text` which could make list responses very large if many agent runs exist.
