# AI Spec Review

## Overall Assessment
Needs work: Step 008 is too large, position indexing inconsistencies, and step ordering creates a dependency problem between 008 and 009.

## Critical Issues

1. **Step 008 is oversized and should be split.** The conversation runner step combines: context assembly, prompt assembly, agent execution, streaming events, file edit detection, git commit, cascade pending queueing, message persistence, error handling, and context truncation. This is 8+ distinct concerns in one step that would reasonably touch 6+ files. An autonomous builder implementing this step will struggle to deliver coherently. Split into:
   - 008a: Core runner (prompt assembly, agent execution, message persistence, streaming events)
   - 008b: File edit detection, git commit integration, cascade pending queueing

2. **Position 0 vs position 1 inconsistency.** requirements.md says "new 'philosophy' layer exists at position 0 (below values)" but step 001 says "Add philosophy layer to LAYERS list at position 1 (bottom of the stack)" with acceptance criteria "values=2, situational-awareness=3". The builder cannot know whether this is 0-indexed or 1-indexed. Pick one and update all references.

3. **Circular dependency between steps 008 and 009.** Step 008's acceptance criteria include "Foundational layer edits trigger ConversationCascadePending event" and the deliverables say "Store the pending cascade record (handled in step 009)". But step 009 comes AFTER step 008, so the builder implementing 008 cannot call store methods that don't exist yet. Either:
   - Move step 009 before step 008, or
   - Remove cascade-pending logic from step 008's scope and have 009 integrate it retroactively, or
   - Have 008 only emit the event, and 009 adds the listener that stores the pending cascade record

4. **Missing: public function signature for conversation runner.** Step 011 says "Launches the conversation runner as a background task" but neither 008 nor 011 specifies the function signature. What arguments does the runner accept? The builder of 011 needs to know the function name and parameters to call it. Step 008 should specify something like: `async def run_conversation_turn(conversation_id: str, user_content: str, store: PolicyStore, emitter: EventEmitter, data_dir: Path) -> None`.

5. **Context truncation criteria are vague.** Step 008 says "If the assembled prompt exceeds context limits... Truncate older messages from conversation history". What are "context limits"? Is this a token count? What target? The acceptance criterion says "Context truncation handles long conversation histories" — how does the builder verify this passes? Specify: "If assembled prompt exceeds 150,000 tokens, truncate oldest messages until under 120,000 tokens."

6. **Step 009: ambiguous scope for API endpoints.** Step 009 deliverables include "POST /api/cascade/trigger-pending" and "DELETE /api/cascade/pending" endpoints. But these are described as additions to "cascade router" (existing file). The acceptance criteria test these endpoints. This means step 009 touches the router, not step 011. But step 011 is "Conversation API endpoints" — will the builder of 011 expect to add cascade endpoints? Clarify: should 009 implement the cascade router additions, or does 011 handle all conversation-related API?

## Suggestions

1. **Reorder step 004 (values prompt fix) earlier.** It only depends on step 001 (philosophy layer exists for context reference). Moving it to position 003 or 004 would let prompt work happen together before database/API implementation.

2. **Step 017/018 are large but acceptable.** Test steps often cover multiple features. Consider mentioning that the builder may implement tests incrementally rather than all at once.

3. **Add explicit "foundational layers" definition.** Instead of hardcoding "philosophy, values, situational-awareness" in multiple places, step 001 or architecture.md should define: "Foundational layers are those with position <= 3 in the LAYERS list" or maintain a `FOUNDATIONAL_LAYERS = {"philosophy", "values", "situational-awareness"}` constant. The builder needs to know where this list lives.

4. **Step 003 acceptance criteria should include theme color distinction test.** The criterion "Philosophy color is visually distinct from all other layer colors" is subjective. Add something testable like "Philosophy primary color is in the red/pink/rose hue family (not purple, cyan, blue, yellow, or green)."

## Per-File Notes

### requirements.md
- Line mentioning "position 0" conflicts with step 001 and architecture.md which say "position 1". Resolve this.
- Otherwise comprehensive with clear success criteria, constraints, and non-goals.

### architecture.md
- Says "position 1" for philosophy, matching step 001 but not requirements.md.
- Context Too Large failure mode mentions truncation but doesn't specify thresholds.
- Otherwise well-structured with clear component descriptions.

### testing.md
- Values prompt fix verification (line 119-122) tests output format with a mocked agent — this doesn't actually verify the prompt works, just that tests can check the format. Consider how this is meaningfully tested.
- Otherwise comprehensive with unit, integration, and E2E coverage.

### overview.md
No issues.

### 001.md
- Position 1 — confirm this matches requirements.md after resolving the inconsistency.
- Otherwise clear deliverables and testable acceptance criteria.

### 002.md
- Acceptance criterion "Seed prompt requires 8-12 philosophy items" — is this enforced by the prompt text or by tests? Clarify.
- Otherwise good detail on prompt content structure.

### 003.md
- "Philosophy color is visually distinct" is subjective — add hue specification.
- Otherwise clear.

### 004.md
- "Context layer description updated to show 6 layers with philosophy at position 1" — this assumes 004 updates a layer description in the values prompt. Is this describing the layer hierarchy within the prompt? Clarify what "context layer description" means.
- Otherwise well-specified with concrete bad/good examples.

### 005.md
No issues. Comprehensive schema and CRUD methods.

### 006.md
No issues. Clear event type definitions with matching TypeScript types.

### 007.md
- "resolve_allowed_tools" function mentioned in acceptance criteria — verify this function exists or should be "resolve_tool_set".
- Otherwise clear.

### 008.md
Critical issues noted above (oversized step, dependency on 009, missing function signature, vague truncation).

### 009.md
- Scope ambiguity on API endpoints noted above.
- "DELETE /api/cascade/pending returns 404 for non-existent pending cascade" — acceptance criteria show "404 (or 204 for idempotent behavior)" but criterion says nothing about 204. Pick one.
- Otherwise clear mechanism description.

### 010.md
- "Prompt is comprehensive (1500+ words) but not padded" — good testable criterion.
- No issues.

### 011.md
- "POST /api/conversations validates layer_slug against LAYER_SLUGS" — LAYER_SLUGS constant not mentioned in step 001. The builder needs to know where this comes from (presumably from layers.py LAYERS list).
- Missing function signature for calling conversation runner as noted above.

### 012.md
No issues. Good detail on state shape and handler naming.

### 013.md
No issues. Clear event routing.

### 014.md
- "Send button (enabled when input is non-empty and not streaming)" — acceptance criterion says "Ctrl+Enter sends message" but should also say "when not disabled (streaming)".
- Large component but appropriately scoped.

### 015.md
- "Handle case where item is being edited (warn user or merge changes)" — this is vague. The acceptance criterion says "User is warned if they have unsaved edits when AI modifies the item" but doesn't specify the warning mechanism. Banner? Modal? Blocking the sidebar open?
- Otherwise clear.

### 016.md
No issues. Follows 015 pattern.

### 017.md
- TestValuesPromptFix section tests format but not actual AI output quality — acknowledged as a mocked test limitation.
- Comprehensive test plan.

### 018.md
- "Streaming display test passes (may require mock backend)" — acknowledge this is difficult to test deterministically.
- Comprehensive E2E coverage.
