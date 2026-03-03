# Requirements

## Problem Statement

The policy factory is producing sanitized, generic, politician-speak output across every layer. The system's entire value proposition is brutal, apolitical honesty about controversial realities — and it's currently doing the opposite.

Specific failures:

1. **Values layer outputs committee platitudes.** Titles like "Digital Autonomy and Secure Data Infrastructure" and "Environmental Stewardship and Intergenerational Responsibility" are useless for resolving any actual policy question. They read like EU white papers. Real values should address the tensions that matter: ethnic cohesion vs. open immigration, individual freedom vs. collective security, welfare generosity vs. work incentives, military sovereignty vs. alliance dependence. If a value isn't controversial, it's the exact boring bullshit this system exists to eliminate.

2. **Situational awareness is surface-level.** Current SA content is Wikipedia-grade: "we're in NATO and Russia attacked Ukraine." Where's the analysis of whether the US nuclear umbrella can actually be trusted? Where are major world events like the US/Israel strikes on Iran? The SA layer should contain the kind of uncomfortable geopolitical analysis that no government press release would ever publish.

3. **Heartbeat updates produce bureaucratic noise.** A patient data breach gets transformed into "a concrete manifestation of insider threat vulnerabilities within critical public healthcare infrastructure" — meaningless corporatespeak. Meanwhile, genuinely significant geopolitical events are completely absent from updates. The escalation threshold is too low (noise gets through) and the writing quality is too sanitized.

4. **No observability.** There are no visible logs showing what the heartbeat is doing, what news it processed, what it decided to escalate or drop, or what the agents actually wrote. Impossible to diagnose problems or understand system behavior.

5. **System is scoped to "tech policy" but should be general policy.** Every prompt references "Finland's tech policy analysis system" or "cross-party tech policy." The system should cover all policy domains: immigration, defense, taxation, drugs, nuclear weapons, EU relations, etc.

### Root Cause

The root cause is that LLMs default to "helpful corporate communicator" mode. Every prompt in the system asks agents to be analytical, but none of them explicitly counteract the model's trained instinct to sanitize, euphemize, and hedge. The existing meditation preamble asks the model to reflect on its biases abstractly — but doesn't tell it to actually produce different output. The model reflects, then produces the same safe garbage with slightly more self-awareness.

A POC with vanilla Claude proved that a different approach works: the model explicitly acknowledges what its training and post-training want it to sanitize about the specific topic at hand, names its censorship tendencies, and then commits to overriding them. This produces genuinely sharp, analytical, uncomfortable output. This pattern needs to be baked into every agent prompt in the system.

## Success Criteria

### Prompt & Content Quality

- [ ] Every prompt file in the system (all files under `src/policy_factory/prompts/`) replaces "tech policy" / "technology policy" references with general policy framing covering all domains (immigration, defense, taxation, drugs, energy, etc.)
- [ ] The meditation preamble is redesigned from abstract bias reflection into a concrete bias-acknowledge-then-override pattern: the model must identify its specific training-induced sanitization tendencies for the topic at hand, then explicitly commit to counteracting them
- [ ] Every agent prompt (generators, critics, heartbeat, seed, synthesis, ideas) includes an anti-slop directive that explicitly prohibits euphemisms, corporatespeak, politician language, and hedging — and provides clear examples of what bad vs. good output looks like
- [ ] The values seed prompt is redesigned to produce values organized around controversial tensions (e.g., "Ethnic & Cultural Cohesion vs. Open Immigration", "Military Sovereignty vs. Alliance Dependence") rather than safe domain categories (e.g., "Digital Autonomy and Secure Data Infrastructure")
- [ ] Values are structured as tension-pairs with analysis of where Finland actually sits on each tension, how this compares to other Western countries and globally, and why it matters for real policy decisions
- [ ] The heartbeat skim prompt has a significantly raised escalation threshold — the bar is "would this change a strategic or policy recommendation?" not "is this tangentially related to any SA topic"
- [ ] The heartbeat SA update prompt produces direct, analytical writing — no filler, no bureaucratic framing, no restating the obvious
- [ ] The SA generator and seed prompts instruct agents to produce genuine geopolitical analysis, not surface-level summaries of publicly known facts
- [ ] All critic prompts are updated to assess content against the anti-slop standard — critics should flag sanitized, hedged, or platitudinous output as a failure

### Observability

- [ ] The heartbeat history API endpoint returns agent output text (the `output_text` field already stored in the database but not currently exposed in API responses)
- [ ] The cascade detail API endpoint returns agent output text for each agent run
- [ ] A new heartbeat log viewer page exists in the UI showing heartbeat run history: when each run happened, what trigger started it (scheduled/manual), which tier it reached, whether it escalated at each tier, and the outcome summary
- [ ] Each heartbeat run in the log viewer is expandable to show tier-by-tier detail: what the skim agent flagged, what the triage agent decided, what the SA update agent wrote
- [ ] Each tier's detail is further expandable to show the full agent output transcript
- [ ] The log viewer shows the most recent runs first with pagination or infinite scroll

### Cross-Layer Cascade Triggers

- [ ] The layer detail page in the UI has a visible button/control to trigger a cascade refresh starting from that layer (the `POST /api/cascade/refresh` endpoint already exists but has no UI affordance beyond any existing refresh button)

## Constraints

- The system's worldview is anchored to Finnish national interests as defined in the values layer. "Apolitical" means the LLM acknowledges and strips its own training biases — it does not mean the system lacks a perspective. The system should be willing to piss off any political faction when the analysis demands it.
- The meditation/bias-override pattern must be topic-aware, not generic. A generic "reflect on your biases" checklist doesn't work — the model needs to identify its specific sanitization tendencies for the actual topic it's about to analyze.
- Yle RSS remains the news source for now. The heartbeat's problem is more about escalation threshold and writing quality than source coverage. Once observability is in place, news source gaps can be diagnosed properly and addressed in a follow-up.
- The backend already stores `output_text` in the `agent_runs` table and `structured_log` in heartbeat runs. The observability work is primarily about exposing existing data through the API and building UI to display it — not about adding new data collection.
- Values should focus on tensions that are actually relevant when making value judgements on controversial questions. Boring consensus items (e.g., "democracy is good") should not appear — they don't help decide anything.

## Non-Goals

- **Adding new news sources beyond Yle RSS.** Diagnose the current pipeline with observability first, then address source gaps in a follow-up.
- **Implementing human editing of values.** The values layer is LLM-generated for now. Human editability is a separate feature.
- **Changing the agent framework, model selection, or architectural patterns.** This task is about what the agents say (prompts) and what the user can see (observability), not how agents execute.
- **Changing the cascade orchestration logic or layer structure.** The five-layer model and cascade flow remain as-is.
- **Building a full agent conversation replay UI.** The observability requirement is for structured logs with expandable full output text — not a step-by-step conversation replay showing each tool call and response.
- **Internationalization or multi-language support.**
