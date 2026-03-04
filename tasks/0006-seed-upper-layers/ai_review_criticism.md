# AI Spec Review

## Overall Assessment

These specs are excellent — well-structured, deeply grounded in the existing codebase, and thoroughly detailed. The step ordering is logical, acceptance criteria are specific and testable, and the related-code references are accurate (verified against the codebase). A builder could implement these with minimal guesswork. The issues below are mostly minor inconsistencies and a few ambiguities, not fundamental problems.

## Critical Issues

1. **SA seed prerequisite inconsistency between spec 006 and 005/requirements**: Step 006 states "The SA seed button is always enabled (no prerequisites)" (AC line 137, and deliverables section line 79). But requirements.md says "The admin UI enforces ordering — seed buttons for upper layers are disabled when prerequisite layers below are empty" and "The backend validates prerequisites and returns an error if layers below are unpopulated." The SA layer has the values layer below it. The existing SA seed endpoint has NO prerequisite validation (confirmed in code), and the specs don't add any. So the decision to make SA have no prerequisites is consistent with the backend, but it contradicts the general language in requirements.md. **Fix**: Add an explicit note in requirements.md clarifying that "upper layers" in the prerequisite requirement means strategic-objectives, tactical-objectives, and policies — not SA. Or explain that SA and values are exempt from prerequisite validation.

2. **Template variable name mismatch risk between step 002 and step 004**: Step 002 defines `gather_context_below()` which returns a single string of all layers-below content. Step 004 says the prompts use two template variables: `current_date` and `context_below`. But step 005 says the endpoint calls `build_agent_prompt("seed", "strategic", current_date=current_date, ...)` — it doesn't specify what keyword argument name is used for the gathered context. The builder needs to know that the gathered context string maps to the `context_below` template variable. Step 005's deliverables section (point 4) says "substituting the current UTC date and the gathered context" but doesn't name the keyword. **Fix**: In step 005, explicitly state the `build_agent_prompt` call uses `context_below=gathered_context` as the keyword argument, matching the `{context_below}` placeholder in the templates.

3. **`values-seed` role missing from `AgentType` in store**: The research notes and codebase show that `AgentRole` in config.py includes `"values-seed"` but `AgentType` in agent_run.py does NOT include it. Step 001 says "Add the 3 new seed role names to the `AgentType` literal" — but should `values-seed` also be added to `AgentType` to close the existing gap? The spec is silent on this. If a builder adds only the 3 new roles, the existing mismatch persists, which may cause issues later. **Fix**: Either explicitly add `values-seed` to `AgentType` in step 001, or add a note explaining the mismatch is intentional and out of scope.

## Suggestions

1. **Step 004 acceptance criterion "matches the quality standards and analytical rigor of its corresponding generator prompt" (AC line 122)** is subjective and untestable by an automated builder. The builder will do its best, but this criterion can't be checked via an assertion. Consider removing it or replacing with something concrete like "includes explicit instructions about time horizons, trade-off honesty, and Finnish institutional specificity matching the generator prompt's requirements."

2. **Step 005 acceptance criterion "The three endpoint functions share a common helper to avoid code duplication" (AC line 144)** is an implementation detail, not a behavioral criterion. It's good guidance but can't be verified by a test. Consider moving it to the deliverables section (which already covers it) and removing from AC.

3. **Step 006 prerequisite logic for SA**: The spec says SA (position 1) is "always enabled — no prerequisites." But what about the values seed? The spec also says values (position 0) is "always enabled." This is fine but worth confirming: does the SA seed truly not require values to be populated? The existing SA seed endpoint gathers values content but doesn't validate its presence — it just uses `"(no values content)"` as fallback. The spec is consistent with current behavior but the builder might question it. A brief comment in step 006 explaining this design choice would help.

4. **Step 003 could mention that step 006 will fix the frontend**: The step acknowledges the breaking change but says "the frontend is updated to consume the new shape in step 006, so between this step and step 006 the admin page seed card will be temporarily broken." This is clear, but the builder of step 003 might worry about it. Consider adding "No action needed — the frontend update is handled by step 006" to reassure.

5. **Step 007 test 12 (mutual exclusion) is marked optional/skippable**: Good call. But the acceptance criteria don't reflect this — all 14 AC items are mandatory. The builder might waste time making a flaky test work. Consider either dropping this test from the deliverables or adding a note in the AC that it's skip-able.

6. **Research.md mentions a pre-existing bug** (variable name mismatch in generator prompts: `context=context` vs `{upstream_content}` placeholder). This is useful context but should probably be called out in requirements.md non-goals or constraints to prevent the builder from trying to fix it during this task.

## Per-File Notes

### requirements.md
The prerequisite language is slightly too broad — "seed buttons for upper layers are disabled when prerequisite layers below are empty" could be read to include SA (which has values below it). See critical issue #1. Otherwise clear and complete.

### architecture.md
Thorough and accurate. All file references, line numbers, and code patterns verified against the codebase. The failure modes section is excellent. No issues beyond what's noted above.

### testing.md
Comprehensive coverage. One minor note: the "Existing Seeding Still Works" section tests that SA seed "still triggers a cascade after completion (behavior unchanged)" — this is good regression coverage. The prerequisite validation tests are well-specified with concrete scenarios.

### overview.md
Clean and accurate. Step descriptions match their detailed files. No issues.

### 001.md
Well-structured. The acceptance criteria are specific and testable. The Gemini-backed role list (AC line 68) includes `values-seed` as a Gemini-backed role — this is worth verifying. If `values-seed` uses a Gemini model string in `_DEFAULT_MODELS`, then it should indeed be unaffected by the `None` change. Verified: `values-seed` does use a Gemini model string, so this is correct. No issues.

### 002.md
Excellent step. The function signatures, return types, and behavior are precisely specified. The deliverables section even includes pseudo-code for the refactored `_gather_generation_context()`. The test cases cover edge cases well. No issues.

### 003.md
Clear and well-scoped. The response structure is precisely defined. The test update strategy (slug-based lookup helper) is practical. The note about the breaking change and temporary frontend breakage is honest and helpful. No issues.

### 004.md
Good detail on quality expectations drawn from generator prompts. The acceptance criteria about `last_modified_by` values and target directories are concrete and verifiable. Two concerns: (1) AC "matches the quality standards and analytical rigor" is subjective (see suggestion #1). (2) The volume guidance (6-10 strategic, 8-15 tactical, 10-20 policies) is mentioned in deliverables but not in acceptance criteria — the builder should include these in the prompts but won't be checked on it. Consider adding an AC like "Each prompt includes volume guidance for the number of items to create."

### 005.md
The most complex step, well-handled. The endpoint table, shared helper approach, and test matrix are clear. The integration test deliverables are thorough — each endpoint gets 7+ test scenarios. See critical issue #2 about the template variable name. One other note: the `SeedResponse` model is described as having `cascade_id` that will be `None` — verify this field is optional/nullable in the existing model. If it's `str`, it would need to become `str | None`. The existing code shows `cascade_id: str | None = None` in the response, so this is fine.

### 006.md
The most detailed step file. The API path mapping table is very helpful — especially the `situational-awareness` → `/api/seed/` special case. The prerequisite logic is specified with concrete per-position rules. The i18n changes are well-specified with explicit lists of keys to remove and add. The deliverables cover all aspects: types, state, handlers, JSX, styles, i18n. No issues beyond the SA prerequisite clarification (suggestion #3).

### 007.md
Well-structured E2E test plan. The layer population strategy (using the layers API rather than filesystem manipulation) is the right approach. The cleanup strategy is clearly specified. Test 12 (mutual exclusion) being optional is a good pragmatic choice. The acceptance criteria match the deliverables. One note: the spec references `getAdminToken(page)` from helpers.ts — the builder should verify this function exists and returns a usable JWT. The spec says it does, which is sufficient. No issues.
