# AI Spec Review

## Overall Assessment

These specs are exceptionally well-written and implementation-ready. The requirements are clear, the architecture is grounded in verified codebase research, acceptance criteria are specific and testable, and dependencies are correctly ordered. An autonomous builder could implement all 8 steps from these specs with minimal guesswork. The few issues below are minor improvements, not blockers.

## Critical Issues

None identified.

## Suggestions

1. **Step 001 — anti-slop preamble content guidance could be more concrete.** The deliverable says "include specific banned phrases" and "examples contrasting bad vs. good output" but doesn't provide the actual banned phrases or examples. The builder will have to invent these. Given that the entire task's value hinges on the quality of this preamble, consider including 3-4 concrete bad-vs-good example pairs in the spec itself (e.g., bad: "This represents a significant development in Finland's strategic landscape" → good: "Russia's naval exercises in the Baltic increased 40% this year — Finland's eastern border is now the most active NATO frontier"). This would calibrate the builder's output and reduce the risk of a mediocre preamble.

2. **Step 002 — `_slugify()` and `_parse_values_output()` are private functions.** The spec says these have no existing tests, which is good to call out. However, since they're prefixed with `_`, they're private to the `seed.py` module. The spec leaves test file location to "the implementer's discretion" — this is fine, but the builder should be aware that testing private functions directly requires importing them with the underscore prefix, which some linters flag. A brief note acknowledging this would prevent confusion.

3. **Step 006 — `cascade_id` field in the agent-run endpoint response.** The spec says the response includes `cascade_id`, but the endpoint lives under the heartbeat router. An agent run fetched via this endpoint might have a `cascade_id` of `null` (if it was triggered by a heartbeat, not a cascade). The spec should clarify whether `cascade_id` can be null in this context — based on the `AgentRun` dataclass having `cascade_id: str | None`, it can, but the builder might not know this.

4. **Step 007 — outcome derivation logic is underspecified.** The spec says outcomes are "nothing noteworthy," "update made," or "cascade triggered" and gives rough derivation rules (highest tier is 1 and tier 1 didn't escalate → nothing noteworthy; tier 3 completed → update made; tier 4 reached → cascade triggered). But what about edge cases: tier 2 reached but didn't escalate? Tier 3 started but failed? The builder will need to handle these. Consider either enumerating the full outcome mapping or saying the outcome is derived from `highest_tier_reached` and the final tier's `escalated` field with a fallback.

5. **Step 007 — heartbeat history API pagination parameters.** The spec says "initial load fetches 20 runs" and "each click loads 20 more" using the HistoryPage pattern. But it doesn't specify the actual query parameters for the existing `GET /api/heartbeat/history` endpoint. The builder needs to know whether this endpoint supports `offset`/`limit` or `page`/`size` parameters. The spec for step 006 says "no change needed" to the history endpoint, so the builder must rely on existing behavior. A brief note about the actual pagination parameters the endpoint accepts would help.

6. **Step 008 — E2E test data setup is vague.** The cascade transcript E2E tests say "the test setup should create test data directly via API endpoints" but doesn't specify which API endpoints or what data structures to create. Creating a cascade with agent runs requires multiple API calls in sequence. The heartbeat log E2E tests say "when heartbeat runs exist (created via API)" — does this mean triggering a real heartbeat (which requires RSS feed, agents, etc.) or inserting data directly? If the latter, through what mechanism? The existing E2E specs (`cascade-viewer.spec.ts`, `layer-detail.spec.ts`) should be checked for how they handle test data, and the spec should reference that pattern explicitly.

7. **Testing plan — "Manual Testing: None" is aspirational but realistic.** The testing plan states all verification must be automated. This is correct for the observability and code changes, but verifying that *prompt content quality* actually produces better LLM output is inherently non-automatable. The prompt content tests (no "tech policy" strings, files load without error) verify format but not quality. The spec acknowledges this in architecture.md ("Prompt changes are not unit-testable in a meaningful way") but testing.md's "None" for manual testing contradicts this. Consider adding a manual testing note: "Prompt quality is verified by running the system and reviewing outputs via the observability tools built in this task."

8. **Steps 003-005 — prompt rewrite specs are thorough but repetitive.** Each prompt rewrite deliverable carefully specifies template variables and tool instructions to preserve. This is good. However, the acceptance criteria for steps 003 and 004 don't explicitly verify that the prompt contains no `{variable}` placeholders that aren't in the expected set — unlike step 002 which explicitly checks for no unexpected placeholders. If a builder accidentally introduces a `{new_var}` placeholder, the prompt would fail at runtime. Step 005's content validation tests partially catch this ("every prompt file can be loaded without error"), but only if the test supplies all expected variables.

9. **Architecture.md — "21 prompt files" count includes `sections/meditation.md`.** The architecture says "Rewrite all 21 prompt files" and the files summary shows 20 prompt files + 1 section replacement. This is correct but could confuse a builder counting files. The research.md lists 21 files including `sections/meditation.md`, but that file is being *replaced* not *rewritten*. Minor terminology nitpick — the actual count of files to rewrite is 20 (prompts) + 1 new file (anti-slop.md) + 1 deletion (meditation.md).

## Per-File Notes

### requirements.md
No issues. Clear problem statement, well-defined success criteria with checkboxes, reasonable constraints and non-goals. The constraint about the system being "anchored to Finnish national interests" is important context that the builder needs, and it's well-placed here.

### architecture.md
Well-structured with three independent work streams clearly delineated. The component-level detail (specific line numbers, function signatures, integration points, failure modes) is excellent — this is the level of detail an autonomous builder needs. The "Alternatively" note about heartbeat log placement in nav vs. admin-only should be resolved to a decision rather than left as an option. The steps all chose nav bar placement, so this is effectively resolved, but the architecture doc still hedges.

### testing.md
Thorough and well-organized. All acceptance criteria are objectively verifiable. The "Manual Testing: None" note is addressed in suggestions above. The integration tests for `_slugify()` and `_parse_values_output()` are particularly valuable since these functions have no existing coverage. One gap: there are no tests specified for verifying that the anti-slop preamble does NOT undergo variable substitution — step 001's acceptance criteria mention this, but testing.md's integration test section doesn't have a dedicated checkbox for it (though the unit test section does).

### overview.md
Clean step table with clear descriptions. The ordering is logical: foundational preamble mechanism (001) → prompt rewrites building on it (002-005) → backend API (006) → frontend consuming the API (007-008). Each step's description accurately summarizes its content.

### 001.md
Excellent. The most critical step is the most thoroughly specified. Related code references are accurate (verified against codebase). The four-component preamble structure is clearly defined. The instruction to update existing tests that assert meditation is NOT prepended is crucial — without this, the builder would break existing tests and might not understand why. One minor note: the spec says `build_agent_prompt()` should import `load_section` from `policy_factory.prompts` — the builder should verify this import path works from within `agent/prompts.py`.

### 002.md
Well-specified with good attention to output format compatibility. The parsing pipeline compatibility is thoroughly addressed (`_parse_values_output()`, `_slugify()`). The test deliverables for previously-untested private functions are valuable. The acceptance criterion about `{variable}` placeholders is good — the values seed prompt is called with no template variables, so any placeholder would cause a runtime error.

### 003.md
Thorough coverage of 6 prompt files. The per-prompt deliverables are detailed enough for independent implementation. The SA generator's anti-slop reinforcement instructions are particularly well-calibrated ("would a Finnish policymaker learn something they didn't already know?"). Template variable preservation is correctly specified per prompt. No issues.

### 004.md
Good structure — the per-critic Finnish context broadening instructions are well-differentiated by ideology. The decision to add the anti-slop quality criterion as a sixth instruction point (woven into Analysis rather than adding a new output format section) is pragmatic and correctly preserves synthesis runner compatibility. No issues.

### 005.md
Appropriately placed as the final prompt step since it includes the cross-cutting validation tests. The escalation marker preservation (`STATUS: NOTHING_NOTEWORTHY`, `STATUS: FLAGGED`, `STATUS: NO_UPDATE_NEEDED`, `STATUS: UPDATE_RECOMMENDED`) is critical and correctly called out. The content validation tests (no "tech policy" strings across all files) serve as a regression guard for the entire prompt overhaul. No issues.

### 006.md
Clean backend-only step. The one-line cascade detail change and new endpoint are clearly specified. Test patterns reference existing test infrastructure accurately. The decision to place the agent-run endpoint on the heartbeat router is justified. The serialization field list is explicit. No issues.

### 007.md
The most complex frontend step, well-structured with three levels of detail. The i18n key list is comprehensive. Reuse opportunities from CascadePage and HistoryPage patterns are correctly identified. The pagination concern (suggestion #5 above) is the only gap. The transcript caching instruction ("subsequent expand/collapse does not re-fetch") is a good detail that prevents unnecessary API calls.

### 008.md
Good wrap-up step combining cascade UI changes, verification of existing functionality, and E2E tests. The verification-only approach for the LayerDetailPage refresh button is pragmatic. The E2E test specifications are reasonable but could use more detail on test data setup (suggestion #6 above). The decision to split E2E tests across three files (new heartbeat-log.spec.ts, extended cascade-viewer.spec.ts, extended layer-detail.spec.ts) follows existing conventions.
