# Architecture

## Work Streams

This task has three independent work streams:

1. **Prompt Overhaul** — Rewrite all 21 prompt files and modify the prompt loading mechanism to auto-prepend the anti-slop preamble.
2. **Observability** — Expose `output_text` through existing API endpoints and build a heartbeat log viewer page.
3. **Cascade Trigger UI** — Verify the existing refresh button on LayerDetailPage satisfies the requirement; enhance if needed.

---

## Work Stream 1: Prompt Overhaul

### Components Affected

#### `src/policy_factory/agent/prompts.py` — Auto-Prepend Anti-Slop Preamble

The `build_agent_prompt()` function is currently a trivial pass-through to `load_prompt()`. It is the single choke point for all agent prompt construction — called from 13 distinct call sites across `heartbeat/orchestrator.py`, `cascade/orchestrator.py`, `cascade/critic_runner.py`, `cascade/synthesis_runner.py`, `cascade/classifier.py`, `ideas/evaluator.py`, `ideas/generator.py`, and `server/routers/seed.py`.

**Change:** Modify `build_agent_prompt()` to automatically prepend the anti-slop preamble section before returning the prompt. This is done by calling `load_section("anti-slop")` and prepending it to the loaded prompt content, separated by a double newline.

This approach is preferred over inlining the preamble into each of the 21 prompt files because:
- Single source of truth for the anti-slop directive
- No risk of copy-paste drift across 21 files
- Future changes to the preamble propagate automatically
- The `load_section()` mechanism already exists and works

The existing `sections/meditation.md` file is renamed/replaced with `sections/anti-slop.md` to reflect the redesigned purpose.

**Signature remains unchanged** — no callers need modification. The preamble is prepended unconditionally to all agent prompts.

#### `src/policy_factory/prompts/sections/meditation.md` → `sections/anti-slop.md`

The current meditation file is a generic 10-to-1 countdown asking the model to reflect on bias categories. It does not instruct the model to override its training defaults and is never loaded in production.

**Replace** with the redesigned anti-slop preamble that implements the bias-acknowledge-then-override pattern:

1. **Bias acknowledgment** — The model identifies its specific training-induced sanitization tendencies for the topic at hand. Not a generic checklist — the model must name what it wants to euphemize, soften, or avoid about this specific subject.
2. **Override commitment** — The model explicitly commits to counteracting each identified tendency.
3. **Anti-slop directive** — Concrete prohibitions: no euphemisms, no corporatespeak, no politician language, no hedging, no "stakeholder engagement," no "multifaceted challenges." Includes good-vs-bad output examples.
4. **Writing standard** — Direct, analytical, uncomfortable when the analysis demands it. If a sentence could appear in a government press release, it's wrong.

The preamble is model-agnostic in wording (works with both Claude and Gemini models). The core instruction is to produce output that would be useful for actual policy decisions, not output that sounds like an EU white paper.

#### `src/policy_factory/prompts/seed/values.md` — Values Seed Redesign

Currently pre-specifies 10 safe domain categories and asks for "cross-partisan" values reflecting "broad Finnish consensus." This is the direct cause of committee-speak value titles.

**Complete rewrite.** The new prompt:

- Frames values as controversial tension-pairs where reasonable people genuinely disagree
- Does NOT pre-specify categories — the model identifies the tensions that actually matter for Finnish policy
- Each value is a tension between two legitimate but conflicting priorities (e.g., "Ethnic & Cultural Cohesion vs. Open Immigration", "Military Sovereignty vs. Alliance Dependence")
- For each tension-pair, the model must analyze: where Finland actually sits today, how this compares to other Nordic/Western/global positions, what policy questions this tension governs, and why it's genuinely controversial (not a settled consensus)
- Explicitly prohibits consensus items: if nobody would seriously argue the other side, it's not a tension worth including
- Output format: maintains the existing `---` delimited frontmatter block format so the parsing logic in `server/routers/seed.py` (`_parse_values_output()` and `_slugify()`) continues to work without modification

The `_slugify()` function in the seed router converts any title string to a filename-safe slug. It handles arbitrary title formats including multi-word tension-pair titles. No code change needed for parsing.

#### `src/policy_factory/prompts/seed/seed.md` — SA Seed Scope Broadening

Replace all references to "Finland's tech policy analysis system" and the 10 tech-centric topics with general policy scope covering all domains: geopolitical/security, immigration/demographics, economics/taxation, energy/environment, social policy/welfare, defense/military, EU relations, trade policy, drugs/public health, education/workforce.

The SA seed generates the initial situational awareness content. It must instruct the model to produce genuine geopolitical analysis, not surface-level summaries of publicly known facts.

#### `src/policy_factory/prompts/generators/*.md` — All 5 Generator Prompts

All five generator prompts (`values.md`, `situational-awareness.md`, `strategic.md`, `tactical.md`, `policies.md`) reference "cross-party tech policy analysis system" and contain tech-centric evaluation criteria.

**For each:** Replace "tech policy" framing with general policy framing. Remove tech-centric criteria lists and replace with domain-agnostic analytical criteria. The anti-slop preamble is auto-prepended by `build_agent_prompt()`, so no inline anti-slop section needed, but each prompt's own instructions should reinforce the writing standard expected (direct analysis, no filler).

The SA generator prompt additionally needs strengthened instructions to produce uncomfortable geopolitical analysis rather than Wikipedia-grade summaries.

#### `src/policy_factory/prompts/critics/*.md` — All 6 Critic Prompts

All six critic prompts (realist, liberal-institutionalist, nationalist-conservative, social-democratic, libertarian, green-ecological) have sound analytical frameworks but reference tech-specific concerns in their Finnish context sections.

**For each:** Broaden the Finnish context examples from tech-specific to general policy. Add an anti-slop quality criterion: critics should flag sanitized, hedged, or platitudinous content as a failure in the material they're reviewing. If the generator output reads like an EU white paper, the critic should call it out. The ideological framework for each critic persona remains unchanged.

#### `src/policy_factory/prompts/synthesis/synthesis.md` — Synthesis Prompt

Replace "cross-party tech policy analysis system" framing. The synthesis agent reconciles critic outputs into a revised version. Add instruction that the synthesis should preserve sharp, uncomfortable analysis from critics and not smooth it into consensus language.

#### `src/policy_factory/prompts/classifier/classifier.md` — Classifier Prompt

Replace "tech policy analysis system" framing. The classifier determines which policy layer an input event affects. Broaden from tech-centric classification criteria to general policy domains.

#### `src/policy_factory/prompts/heartbeat/skim.md` — Tier 1 Skim Prompt

Two changes:

1. **Scope broadening:** Replace tech-focused significance criteria ("Change Finland's geopolitical technology position", "Affect EU technology regulation") with general policy significance criteria covering all domains.

2. **Raised escalation threshold:** The current threshold is too low — noise gets through. The new threshold is: "Would this change a strategic or policy recommendation that a Finnish policymaker should act on?" Not "is this tangentially related to any SA topic." Include explicit examples of what should NOT escalate (routine government announcements, incremental regulatory updates, minor corporate news) vs. what should (major geopolitical shifts, significant military developments, dramatic policy changes by key partners/adversaries, events that invalidate current strategic assumptions).

#### `src/policy_factory/prompts/heartbeat/triage.md` — Tier 2 Triage Prompt

Replace "tech policy analysis system" framing. The existing threshold text ("would this change a policy recommendation if policymakers knew about it?") is actually the right threshold, but scope-broaden the evaluation criteria.

#### `src/policy_factory/prompts/heartbeat/sa-update.md` — Tier 3 SA Update Prompt

Replace "tech policy analysis system" framing. The current writing instructions say "Be factual. Stick to what the evidence supports." but produce bureaucratic output. Add explicit anti-slop writing directive: no restating the obvious, no bureaucratic framing, no filler sentences, no "this represents a significant development." The SA update should read like a sharp intelligence briefing, not a corporate memo.

#### `src/policy_factory/prompts/ideas/evaluate.md` and `ideas/generate.md` — Idea Prompts

Replace "tech policy analysis system" framing in both. Broaden evaluation criteria and idea generation scope to cover all policy domains.

### New Entities

None. All changes are to existing prompt files and one function signature-compatible modification to `build_agent_prompt()`.

### Integration Points

- **`build_agent_prompt()` ↔ all callers** — The function signature does not change. All 13 call sites continue to work unchanged. The only behavioral change is that returned prompts now include the anti-slop preamble at the top.
- **Values seed output ↔ `_parse_values_output()`** — The output format (frontmatter blocks delimited by `---`) is preserved. Only the content within each block changes (tension-pair titles, restructured body). The `_slugify()` function handles arbitrary title strings.
- **Heartbeat escalation ↔ orchestrator** — The escalation markers (`NOTHING_NOTEWORTHY`, `NO_UPDATE_NEEDED`) are unchanged. The prompts still instruct agents to use these markers. The change is in what the agent considers noteworthy.

### Failure Modes

- **Gemini models may respond differently to anti-slop directives.** The preamble was POCed with Claude. Several agents use Gemini Flash. Mitigation: keep preamble wording model-agnostic, focus on concrete prohibitions and examples rather than abstract instructions. Accept that quality may vary across models.
- **Values seed may produce fewer or different tension-pairs than expected.** Since the prompt no longer pre-specifies categories, the model chooses which tensions to include. Mitigation: the prompt specifies a target count range and the parsing logic handles any number of output blocks.
- **Raised heartbeat threshold may suppress too aggressively.** If the bar is set too high, genuine signals may be missed. Mitigation: the observability work (work stream 2) enables monitoring of what gets filtered. Threshold can be adjusted in follow-up once logs are visible.

---

## Work Stream 2: Observability

### Components Affected

#### `src/policy_factory/server/routers/cascade.py` — Expose `output_text` in Cascade Detail

The cascade detail endpoint (`GET /api/cascade/{cascade_id}`) serializes agent runs at lines 336-350 but explicitly omits `output_text`.

**Change:** Add `output_text` to the agent run serialization dict. This is a one-line addition to the dict comprehension: `"output_text": r.output_text`.

No store or schema changes needed — `list_agent_runs()` already returns `AgentRun` objects with `output_text` populated from the database.

**Performance consideration:** Agent outputs can be large (thousands of characters), and a cascade can have 10+ agent runs. For the cascade detail view, this is acceptable because: (a) the endpoint is fetched on-demand when a user clicks into a specific cascade, not in list views, and (b) the frontend already fetches full cascade detail on expand.

#### `src/policy_factory/server/routers/heartbeat.py` — New Endpoint for Agent Run Output

The existing heartbeat endpoints return structured logs with `agent_run_id` per tier but do not include agent output text. Rather than bloating the history list response with full transcripts, a new on-demand endpoint is added.

**New endpoint:** `GET /api/heartbeat/agent-run/{agent_run_id}` — Returns the full agent run record including `output_text` for a specific agent run. This endpoint uses the existing `store.get_agent_run(agent_run_id)` method which already returns the complete `AgentRun` dataclass.

This on-demand approach is preferred because:
- Heartbeat history lists could contain dozens of runs, each with up to 4 tier entries, each linking to an agent run with potentially large output text
- Loading all output text upfront would make the history endpoint slow and wasteful
- The UI only needs output text when the user explicitly expands a tier entry

**Response format:** Same fields as the cascade agent run serialization (id, agent_type, agent_label, model, target_layer, started_at, completed_at, success, error_message, cost_usd, output_text).

#### `ui/src/pages/HeartbeatLogPage.tsx` (new) — Heartbeat Log Viewer

A new page following the CascadePage expandable-detail pattern:

**Top-level list:** Shows recent heartbeat runs in reverse chronological order. Each entry shows:
- When the run started (relative time via existing `formatRelativeTime`)
- Trigger type (scheduled / manual)
- Highest tier reached (1–4)
- Duration (via existing `formatDuration`)
- Outcome summary (nothing noteworthy / update made / cascade triggered)

**Expanded detail (click to expand):** Shows tier-by-tier breakdown for the selected run:
- Tier number, whether it escalated, outcome text, duration
- Expandable transcript section per tier: fetches `GET /api/heartbeat/agent-run/{agent_run_id}` on demand and renders the full output text in a preformatted/markdown block

**Pagination:** "Load more" button pattern matching HistoryPage.tsx. Initial load fetches 20 runs, each click loads 20 more.

**Data source:** Uses `GET /api/heartbeat/history` for the run list (already exists, no change needed) and the new `GET /api/heartbeat/agent-run/{id}` for transcript expansion.

#### `ui/src/pages/HeartbeatLogPage.styles.ts` (new) — Styled Components

Companion styles file following the project convention. Reuses patterns from CascadePage.styles.ts (HistoryEntry, HistoryEntryHeader, expandable sections).

#### `ui/src/pages/CascadePage.tsx` — Expose Output Text in Cascade Detail

The existing `CascadeDetailPanel` shows agent run info but without output text.

**Change:** Add an expandable transcript section to each agent run entry. When the user clicks to expand, display the `output_text` field (now included in the API response) in a preformatted/markdown block. No additional API call needed — the data comes with the existing cascade detail fetch.

Update the `AgentRunInfo` TypeScript interface to include `output_text: string | null`.

#### `ui/src/App.tsx` — New Route

Add route entry: `<Route path="/heartbeat" element={<HeartbeatLogPage />} />` inside the protected routes.

#### `ui/src/components/organisms/Navigation.tsx` — New Nav Link

Add nav link for the heartbeat log page. Position it after "Activity" in the nav bar. The link label uses a new i18n key `nav.heartbeat`. The link is visible to all authenticated users (not admin-only) since heartbeat observability is useful for anyone monitoring system behavior.

#### `ui/src/i18n/locales/en.ts` — New Translation Keys

Add translation keys for:
- `nav.heartbeat` — Nav link label
- `heartbeat.pageTitle` — Page title
- `heartbeat.emptyState` — Empty state message
- `heartbeat.triggerScheduled` / `heartbeat.triggerManual` — Trigger type labels
- `heartbeat.tierN` — Tier labels (Tier 1: Skim, Tier 2: Triage, Tier 3: SA Update, Tier 4: Cascade)
- `heartbeat.outcome.*` — Outcome labels
- `heartbeat.expandTranscript` / `heartbeat.collapseTranscript` — Toggle labels
- `heartbeat.loadMore` — Load more button
- `cascade.expandTranscript` / `cascade.collapseTranscript` — For cascade page transcript toggle

#### `ui/src/pages/AdminPage.tsx` — Link to Heartbeat Log

The AdminPage already has a heartbeat status card. Add a link/button from this card to the new heartbeat log page for discoverability.

### New Entities / Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/heartbeat/agent-run/{agent_run_id}` | GET | Returns full agent run record including `output_text`. Uses existing `store.get_agent_run()`. Auth required. |

No new database tables or columns. No schema migration.

### Integration Points

- **Heartbeat log page ↔ existing heartbeat history endpoint** — The page consumes `GET /api/heartbeat/history` which already returns structured logs with `agent_run_id` per tier. No change to this endpoint.
- **Heartbeat log page ↔ new agent-run endpoint** — On-demand transcript fetch when user expands a tier entry.
- **Cascade detail page ↔ modified cascade detail endpoint** — The existing `GET /api/cascade/{id}` response now includes `output_text` in each agent run dict. The frontend `AgentRunInfo` interface is updated to match.
- **AdminPage ↔ heartbeat log page** — Link from heartbeat status card to the new page.
- **Navigation ↔ heartbeat log page** — New nav link, new route entry.

### Failure Modes

- **Large `output_text` responses.** Agent outputs can be thousands of characters. For the agent-run endpoint this is fine (single record). For the cascade detail endpoint, outputs are included inline — acceptable because the endpoint is fetched on-demand for a single cascade, not in list views.
- **Missing agent run records.** If an `agent_run_id` from a tier entry no longer exists in the database (data corruption or manual deletion), the agent-run endpoint returns 404. The UI handles this gracefully with an error state in the transcript section.

---

## Work Stream 3: Cascade Trigger UI

### Components Affected

#### `ui/src/pages/LayerDetailPage.tsx` — Verify Existing Refresh Button

Research confirmed that LayerDetailPage already has a "Refresh" button (line 228-237) that calls `POST /api/cascade/refresh` with the current layer slug. This may already satisfy the cross-layer cascade trigger requirement.

**Verify:** The button triggers a cascade starting from the current layer and propagating downward through the stack. This is the intended behavior — "refresh from this layer" means "regenerate this layer and everything below it."

**If the button is sufficient:** No code changes needed. The requirement is already met. Document this finding in the task overview.

**If enhancement is needed:** Consider improving the button's discoverability (label, position, visual treatment) or adding a confirmation dialog that explains what "Refresh" does (triggers a cascade regeneration from this layer downward).

The `POST /api/cascade/refresh` endpoint already exists and works. No backend changes needed for this work stream.

### New Entities / Endpoints

None. Existing endpoint and UI element are reused.

### Integration Points

- **LayerDetailPage refresh button ↔ `POST /api/cascade/refresh`** — Already wired and functional.
- **Cascade status feedback ↔ WebSocket events** — Cascade progress is already broadcast via WebSocket and displayed in the nav bar's cascade status indicator.

### Failure Modes

None specific to this work stream — the existing mechanism is already in production.

---

## Cross-Cutting Concerns

### Ordering of Work Streams

The three work streams are independent and can be implemented in any order. However, the recommended sequence is:

1. **Observability first** — Enables monitoring of prompt changes. Without logs, it's impossible to tell if the anti-slop changes are working.
2. **Prompt overhaul second** — With observability in place, the effect of each prompt change can be verified.
3. **Cascade trigger UI last** — Smallest scope, may require no changes.

### Testing Approach

- **Prompt changes** are not unit-testable in a meaningful way (they change LLM behavior). Verification is through running the system and reviewing outputs via the observability tools.
- **API changes** (adding `output_text` to responses, new endpoint) are testable with standard API tests.
- **UI changes** (new page, expanded components) are testable with component rendering tests and manual verification.

### Files Changed Summary

| Category | Files | Change Type |
|---|---|---|
| Prompt loading | `agent/prompts.py` | Modify (auto-prepend) |
| Preamble | `prompts/sections/meditation.md` → `anti-slop.md` | Replace |
| Prompts | 20 prompt files under `prompts/` | Rewrite |
| Backend API | `server/routers/cascade.py` | Modify (add output_text) |
| Backend API | `server/routers/heartbeat.py` | Modify (add endpoint) |
| Frontend page | `pages/HeartbeatLogPage.tsx` | New |
| Frontend styles | `pages/HeartbeatLogPage.styles.ts` | New |
| Frontend page | `pages/CascadePage.tsx` | Modify (add transcript) |
| Frontend routing | `App.tsx` | Modify (add route) |
| Frontend nav | `organisms/Navigation.tsx` | Modify (add link) |
| Frontend i18n | `i18n/locales/en.ts` | Modify (add keys) |
| Frontend page | `pages/AdminPage.tsx` | Modify (add link) |
| Frontend page | `pages/LayerDetailPage.tsx` | Verify only |
