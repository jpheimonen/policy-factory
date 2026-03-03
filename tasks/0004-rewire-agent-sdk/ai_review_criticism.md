# AI Spec Review

## Overall Assessment

These specs are excellent — among the best I've seen for autonomous implementation. The requirements are clear and complete, the architecture is thoroughly documented with integration points and failure modes, the step ordering is correct, and acceptance criteria are specific and testable. A builder could implement this with minimal guesswork. The issues below are minor refinements, not blockers.

## Critical Issues

1. **Step 001 creates a broken state with no clear guard rails.** The step explicitly says callers will fail at import time because `get_anthropic_client()` is removed from `deps.py` but callers still reference it until step 005. The spec says "the test suite is expected to be in a transitional state across steps 001–006." This is technically fine for a staged rewrite, but the acceptance criteria for step 001 should make this explicit by saying something like "Tests for caller modules (heartbeat, cascade, seed, ideas) are NOT expected to pass at this point." As written, a builder might try to run the full test suite after step 001 and interpret widespread import failures as evidence they did something wrong. **Recommendation**: Add an acceptance criterion to step 001 explicitly stating which test categories are expected to fail and why.

2. **Step 002 also creates import breakage in `config.py`.** The step removes `FILE_TOOLS`, `READ_ONLY_TOOLS`, `FILE_TOOLS_WITH_WEB_SEARCH`, `WEB_SEARCH_ONLY` from `tools.py`, but `config.py` imports these until step 003 rewrites it. The step mentions this ("These imports will break when the old constants are removed. This is expected — step 003 will update config.py") but there is no acceptance criterion addressing it. The builder will run tests after step 002 and see config-related import failures. Same recommendation: add a note to acceptance criteria about expected transitional breakage.

3. **`permission_mode` value is never specified.** Architecture says "Set to a restrictive mode that prevents Claude Code from using its built-in file/edit/bash tools." Step 004 says "sets `permission_mode` to restrict built-in Claude Code tools." But neither specifies the actual value. The builder needs to know the exact `PermissionMode` enum value or string to use. The cc-runner reference project presumably uses one — specify it (e.g., `"bypassPermissions"` or whatever the SDK provides). Without this, the builder must reverse-engineer the SDK or guess. This is the closest thing to a real blocker.

4. **Step 006 prompt test deliverables overlap with step 001.** Step 001 lists prompt test updates as deliverables. Step 006 says "This step verifies those changes are complete and correct. If step 001 has already made all the changes below, this deliverable is verification-only." This ambiguity means neither step clearly owns the prompt test changes. The builder of step 001 might skip some changes thinking step 006 will handle them, and vice versa. **Recommendation**: Assign prompt test changes to exactly one step. Step 001 is the natural owner since that's when `build_agent_prompt()` changes.

## Suggestions

1. **Step 001 `__init__.py` — clarify which `FILE_TOOLS`/`READ_ONLY_TOOLS`/`TOOL_FUNCTIONS` exports stay.** The step says "do NOT remove them here as `config.py` still references them." This is correct but could confuse a builder who sees these exports in the acceptance criteria for step 002. Add a brief note in step 002's `__init__.py` section about removing these exports from `__init__.py` at that point.

2. **Step 002 MCP content format is vague.** The step says results are returned "in MCP content format (a dict with a `content` list containing text blocks)" but doesn't specify the exact structure. The cc-runner's `make_result()` is referenced, which helps, but specifying the exact dict shape (e.g., `{"content": [{"type": "text", "text": "..."}]}`) would prevent misinterpretation. The builder could look at cc-runner, but spelling it out removes ambiguity.

3. **Step 003 — MCP server reference string should be verified against SDK docs.** The step states the reference string is `"mcp__policy-factory-tools"` (double underscore). If the SDK convention is actually `mcp__<name>` with double underscore, great. But this naming convention is stated as fact without citation. If the builder looks at the SDK and finds a different convention, they'll be stuck. Consider adding a note that this convention should be verified against the cc-runner reference.

4. **Step 004 — `result_text` vs `full_output` distinction needs tighter definition.** The spec says `result_text` comes from `ResultMessage.result` and `full_output` is concatenated `AssistantMessage` text blocks. But what happens if `ResultMessage.result` is `None` or empty? Does `result_text` fall back to `full_output`? The existing code probably has this behavior — the spec should preserve it explicitly or state the new behavior.

5. **Step 004 — duck-typing detection for `ResultMessage`.** The spec says to detect `ResultMessage` via `hasattr(message, "is_error")`. But what if a future SDK version adds `is_error` to another message type? This is a minor concern but worth noting. The cc-runner uses the same pattern, so it's established — just wanted to flag it.

6. **Step 005 is very repetitive.** The 8 caller module updates follow an identical pattern, and each is spelled out with the same 4-5 bullet points. This is actually fine for an autonomous builder (clarity > brevity), but the acceptance criteria list 28 checkboxes that are essentially 4 checkboxes × 8 callers (minus the seed-specific ones). Consider whether a table format would be clearer.

7. **Testing plan — no negative test for `create_tools_server()` with invalid tool set identifier.** The server factory tests verify full, read-only, and no tools. But what happens if an invalid identifier is passed? Should it raise? Ignore? The behavior should be specified.

## Per-File Notes

### requirements.md
Excellent. Clear problem statement, specific success criteria, well-defined constraints, and thorough non-goals that prevent scope creep. The 15 success criteria checkboxes are all objectively verifiable. No issues.

### architecture.md
Very thorough. The component-by-component breakdown is clear, integration points are well-documented, and failure modes cover real scenarios (CLI not installed, auth, crashes, context overflow, concurrency). The only gap is the unspecified `permission_mode` value (see Critical Issue #3).

### testing.md
Comprehensive and well-organized. Clear separation between unchanged tests, updated tests, and new tests. Each test is specific enough to implement. The test plan covers unit, integration, and explicitly states no browser/E2E or manual tests are needed. No issues beyond what's noted in suggestions.

### overview.md
Clean step table with correct ordering and accurate descriptions. Each step description matches its detailed file. No issues.

### 001.md
Well-structured foundational step. Clear file-by-file deliverables with specific line references. The `load_section` import removal has a good guard ("check before removing"). The only concern is the expected test breakage not being explicit in acceptance criteria (Critical Issue #1) and the prompt test ownership overlap with step 006 (Critical Issue #4).

### 002.md
Good detail on the MCP conversion. The reference to cc-runner files is helpful. Acceptance criteria are specific and testable. The MCP content format could be more precise (Suggestion #2), and the transitional config breakage should be noted (Critical Issue #2). The deliverables section for test updates is thorough.

### 003.md
Clean separation of `allowed_tools` resolution vs. MCP tool set resolution. The per-role mappings are exhaustive (all 11 roles listed). Good that it preserves the `ValueError` pattern for unknown roles. The `mcp__policy-factory-tools` convention should be verified (Suggestion #3). No other issues.

### 004.md
The most complex step, appropriately detailed. The cc-runner reference file paths are helpful. The mock infrastructure replacement is well-specified. The `_build_options()` method is clearly described. Two concerns: the `permission_mode` value is unspecified (Critical Issue #3), and the `result_text` vs `full_output` edge case needs clarification (Suggestion #4). The test rewrite section is thorough with specific test names and mock patterns.

### 005.md
Highly mechanical and well-specified. Each of the 8 callers gets its own section with specific changes. The seed router gets extra detail for its unique `try/except RuntimeError` pattern and `resolve_tools` removal. The line number references are helpful. The 28 acceptance criteria are repetitive but unambiguous. No issues.

### 006.md
Good final integration step. The dependency removal integration checks are a smart addition that catches leftover references. The prompt test overlap with step 001 is the main concern (Critical Issue #4). The `MockAgentResult` update for `session_id` is correctly identified. The call site update patterns are clearly documented with specific test function names.
