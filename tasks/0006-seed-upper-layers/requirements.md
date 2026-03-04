# Requirements

## Problem Statement

The system can seed the Values and Situational Awareness layers via dedicated agents, but the three upper layers — Strategic Objectives, Tactical Objectives, and Policies — can only be populated through the cascade. There is no way to bootstrap these layers independently. This means an admin cannot quickly stand up a full policy stack without running a complete cascade, and has no direct control over initial content in the upper layers.

## Success Criteria

- [ ] An admin can trigger seeding of the Strategic Objectives layer from the admin page, producing agent-generated content grounded in the values and situational awareness layers below
- [ ] An admin can trigger seeding of the Tactical Objectives layer, grounded in values, situational awareness, and strategic objectives
- [ ] An admin can trigger seeding of the Policies layer, grounded in all four layers below
- [ ] Each seed operation clears existing items in the target layer before writing new ones (re-runnable, like existing seeds)
- [ ] Each seed agent uses FILE_TOOLS to write items directly (matching the SA seed pattern)
- [ ] Seeding is independent — triggering a seed does not automatically cascade to layers above
- [ ] The admin UI shows seed status for all 5 layers (not just values and SA) with item counts
- [ ] The admin UI enforces ordering — seed buttons for the three upper layers (strategic-objectives, tactical-objectives, policies) are disabled when prerequisite layers below are empty
- [ ] The backend validates prerequisites for the three upper layers and returns an error if layers below are unpopulated
- [ ] Values and SA seed buttons are always enabled — these two foundational layers have no prerequisites (the existing SA seed gathers values content but operates gracefully when none exists)
- [ ] Seeded items are treated as drafts — absent or incomplete cross-layer references are acceptable
- [ ] Each seed operation records an agent run in the store and commits changes to git
- [ ] All Claude SDK agent roles (including existing generator, critic, heartbeat-sa-update, seed) use the CLI default model instead of hardcoding a specific model string
- [ ] The seed status API response uses a list-based structure covering all 5 layers instead of hardcoded field pairs for values and SA only

## Constraints

- New seed agents must follow the established SA seed pattern: server clears items, agent writes via file tools, server commits to git
- Seed agents for the three upper layers (strategic-objectives, tactical-objectives, policies) require all layers below to be populated — the agent receives layers-below content as prompt context. Values and SA are exempt from prerequisite validation: the existing SA seed already handles missing values content gracefully with a fallback
- New seed agent roles use the Claude CLI default model (pass no model specification so the CLI picks its configured default)
- The seed status API change is a breaking change — the frontend must be updated in the same task to stay in sync
- Seeded content must coexist naturally with cascade-generated content — the cascade generators read existing items and edit/extend rather than wipe, so seeding bootstraps and cascading refines
- The admin page seed status card must be redesigned as a vertical layer list to accommodate 5 layers without becoming cramped

## Non-Goals

- Manual/import seeding (typing or uploading content directly) — agent-generated only for now
- Cascade triggering after seeding — each layer seeds independently
- Web search for upper-layer seed agents — only the SA seed agent uses web search; the upper layers derive from existing layer content
- Updating Gemini-backed agent roles — only Claude SDK roles get the model default change
- Concurrency protection between seed operations — not in scope for this task
- Fixing the pre-existing variable name mismatch in cascade generator prompts (orchestrator passes `context=` but templates use `{upstream_content}`) — this is a known bug unrelated to this task; do not attempt to fix it during this work
