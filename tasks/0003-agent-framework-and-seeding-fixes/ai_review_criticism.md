# AI Spec Review

## Overall Assessment

These specs are well-structured and comprehensive. The requirements are clear, the architecture is thoughtful, and the steps are logically ordered with good granularity. There are a few ambiguities around output parsing and web search tool integration that need clarification before implementation, but overall this is ready for an autonomous builder with minor fixes.

## Critical Issues

### 1. Web search tool specification is incomplete

The specs repeatedly reference "web search" as a tool that agents can use (heartbeat, SA seeding), but there's no concrete specification of:
- How web search is invoked — is it a server-side tool handled by Anthropic's API, or a custom tool like the file tools?
- What the tool schema looks like
- How it integrates into the `AgentConfig.tools` field

Step 004 says heartbeat gets "web search only" and seed gets "file tools plus web search" but never specifies what web search IS. The architecture doc mentions "server-side tools (web search) be handled automatically by the API" but this is vague. The builder needs to know:
- Is this `web_search` a built-in Anthropic capability or a custom implementation?
- If built-in, how is it enabled in the API call?
- If custom, where is its implementation specified?

**Recommendation:** Add a section to step 004 or create a new step that explicitly defines how web search is configured. Reference the Anthropic documentation for server-side tools if that's the mechanism.

### 2. Values parsing format is underspecified

Step 007 says "parse the output to extract individual value documents (frontmatter + body)" but doesn't specify the exact format the agent should output. The prompt in step 006 asks for "YAML frontmatter including title and tensions fields" but:
- What delimiter separates individual values in the output? Multiple `---` blocks? Numbered sections?
- What's the exact YAML frontmatter schema? Just `title` and `tensions`, or are there other fields?
- How should parsing failures be handled — fail the whole operation, or write successful parses and report partial failure?

The builder will have to guess at the parsing logic, which risks building something that doesn't match what the prompt produces.

**Recommendation:** Step 007 should include an example of the expected output format:
```
---
title: "Value Title"
tensions:
  - "other-value-1"
  - "other-value-2"
---
Value body content...

---
title: "Next Value"
...
```

### 3. Step 011 authentication requirement contradiction

Step 011 acceptance criteria says "Endpoint continues to require authentication (existing behavior)" but the architecture doc (line 101) says "No auth required: Status check is public". This is a direct contradiction — the builder will not know which is correct.

**Recommendation:** Clarify which behavior is intended and fix the contradicting file.

## Suggestions

### testing.md could reference specific test file locations

The testing plan lists test scenarios but doesn't indicate which test files they belong to. While steps 012-014 provide this information, having it in testing.md would make the document more useful as a standalone reference.

### Step 010 could be earlier in the sequence

The shared Anthropic client creation (step 010) is a dependency for step 003 (AgentSession rewrite). Currently the step order suggests implementing AgentSession before the client exists. The builder could work around this, but swapping 010 to be step 003 (and renumbering) would make the dependency flow cleaner.

### Minor: Model tier not specified for values-seed role

Step 004 says to "Add default model mapping (use same tier as other seed operations)" but doesn't specify what tier that is. This is discoverable from the existing code, so not critical.

## Per-File Notes

### requirements.md
No issues. Clear problem statement, well-structured success criteria, appropriate constraints and non-goals.

### architecture.md
- Line 101 says seed status endpoint has no auth required — contradicts step 011. See critical issue #3.
- Otherwise comprehensive with good failure mode coverage.

### testing.md
No issues. Good coverage of unit, integration, and E2E scenarios. The "Manual Testing: None" is clear.

### overview.md
No issues. Step table is clear and well-organized.

### 001.md
No issues. Clean, minimal step for adding a dependency.

### 002.md
No issues. Comprehensive acceptance criteria for the tools module.

### 003.md
- Acceptance criterion "Text deltas are emitted as AgentTextChunk events during streaming" — could clarify that this means text deltas from the streaming response, not tool execution progress.
- Otherwise well-specified with good detail on what to preserve vs. rewrite.

### 004.md
- Critical: Web search tool integration is not specified. See critical issue #1.
- The acceptance criteria list tool configurations for each role which is good, but "web search" is undefined.

### 005.md
No issues. Clear scope of what to change and what to preserve.

### 006.md
- Should specify the exact output format more concretely (delimiter between values). See critical issue #2.
- Otherwise good guidance on content focus.

### 007.md
- Critical: Output parsing format is underspecified. See critical issue #2.
- Consider adding an acceptance criterion for handling malformed agent output (partial success vs. total failure).

### 008.md
No issues. Clear changes, good backward compatibility focus.

### 009.md
No issues. Clear about what to remove and what to keep.

### 010.md
- Suggestion: This step should come earlier (before step 003) since AgentSession needs the client.
- Otherwise well-specified.

### 011.md
- Critical: Authentication requirement contradicts architecture.md. See critical issue #3.

### 012.md
No issues. Good guidance on what mock infrastructure to create and what test scenarios to preserve.

### 013.md
No issues. Good security test coverage for path validation.

### 014.md
No issues. Comprehensive integration test coverage.

### 015.md
No issues. Good final verification checklist. The documentation of manual verification for live API testing is a nice touch.
