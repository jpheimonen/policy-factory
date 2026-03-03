# Anti-Slop Overhaul

Comprehensive overhaul to eliminate sanitized, committee-speak output across the entire policy factory. Three work streams: (1) rewrite all 21 prompt files with anti-slop directives and general policy scope, wiring in a bias-acknowledge-then-override preamble; (2) expose already-stored agent output text through API and build a heartbeat log viewer page; (3) verify the existing cascade trigger UI.

## Sub-tasks

| Step | Title | Done | Description |
|------|-------|------|-------------|
| [001](001.md) | Anti-slop preamble and prompt loading | [x] | Create the anti-slop section file with bias-acknowledge-then-override pattern. Modify `build_agent_prompt()` to auto-prepend it to all prompts. Remove old meditation file. Update existing prompt loading tests. |
| [002](002.md) | Values seed prompt redesign | [ ] | Complete rewrite of the values seed prompt to produce controversial tension-pairs instead of safe domain categories. Verify output format compatibility with existing `_parse_values_output()` and `_slugify()` parsing. |
| [003](003.md) | SA seed and generator prompts | [ ] | Rewrite the SA seed prompt and all 5 generator prompts (values, situational-awareness, strategic, tactical, policies) to replace tech-policy framing with general policy scope and reinforce anti-slop writing standards. |
| [004](004.md) | Critic and synthesis prompts | [ ] | Rewrite all 6 critic prompts (realist, liberal-institutionalist, nationalist-conservative, social-democratic, libertarian, green-ecological) and the synthesis prompt. Broaden from tech-specific to general policy. Add anti-slop quality criterion for critics to flag sanitized output. |
| [005](005.md) | Heartbeat, classifier, and idea prompts | [ ] | Rewrite heartbeat prompts (skim, triage, sa-update) with raised escalation threshold and anti-slop writing directives. Rewrite classifier and idea prompts (evaluate, generate) with general policy scope. Add prompt content validation tests confirming zero "tech policy" references remain across all prompt files. |
| [006](006.md) | Observability backend API | [ ] | Add `output_text` to cascade detail API response. Add new `GET /api/heartbeat/agent-run/{id}` endpoint for on-demand transcript fetching. Add API tests for both changes and regression tests for existing heartbeat endpoints. |
| [007](007.md) | Heartbeat log viewer page | [ ] | Build new HeartbeatLogPage with expandable run list, tier-by-tier detail, and on-demand transcript expansion. Add `offset` parameter to heartbeat history endpoint for pagination. Add route, nav link, i18n keys, and styled components. Add link from AdminPage heartbeat status card. |
| [008](008.md) | Cascade transcript UI and cascade trigger verification | [ ] | Add expandable output text transcript to cascade detail panel agent run entries. Update `AgentRunInfo` TypeScript interface. Verify existing LayerDetailPage refresh button satisfies cascade trigger requirement. Add E2E tests for heartbeat log page, cascade transcripts, and layer detail refresh button. |
