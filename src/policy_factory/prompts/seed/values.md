# Values Layer Synthesis

You are synthesizing Finland's foundational policy values for a cross-party tech policy analysis system. Your task is to articulate the axiomatic values that underpin Finnish technology policy — normative statements about what Finland should prioritize, not descriptions of what currently exists.

## What Values Are

Values in this context are **axiomatic normative statements** — foundational principles that guide policy decisions. They are:

- **Normative**, not descriptive: "National survival takes precedence over ideological purity" rather than "Finland joined NATO in 2023"
- **Foundational**: Core principles that don't require justification from other principles
- **Tension-bearing**: Values that can genuinely conflict with each other in specific situations
- **Cross-partisan**: Principles that transcend party lines and reflect broad Finnish consensus
- **Actionable**: Statements that can actually guide policy trade-offs

Values are NOT:
- Current facts or statistics about Finland
- Policy recommendations (those belong to higher layers)
- Aspirational goals without normative weight
- Generic platitudes that could apply to any nation

## Source Material

Draw on your knowledge of:

- **Finnish Constitutional Principles**: Basic rights, rule of law, Nordic legal tradition
- **Cross-Party Consensus Areas**: Security policy, education, welfare state foundations
- **Nordic Policy Traditions**: Pragmatism, social partnership, comprehensive security
- **EU Membership Context**: Integration, solidarity obligations, regulatory alignment
- **Security Policy Evolution**: Post-2022 recalibration, NATO membership implications
- **Historical Experience**: Winter War legacy, neutrality-to-alliance transition, economic transformations

## Output Format

Produce 8-12 foundational values. Each value is a complete markdown document with YAML frontmatter. Values are separated by the standard frontmatter delimiter `---` at the start of each new value.

Format each value as follows:

```
---
title: "Value Title"
tensions:
  - "Other Value Title 1"
  - "Other Value Title 2"
---

A clear articulation of this foundational value and what it means for Finnish technology policy.

The body should explain:
- Why this is a foundational value for Finland specifically
- How it manifests in technology policy decisions
- What trade-offs it implies when it conflicts with other values
```

## Target Coverage

Ensure the values collectively address these domains (not necessarily one-to-one):

1. **Sovereignty and Self-Determination**: National control over critical decisions
2. **Security and Resilience**: Defence, comprehensive security, preparedness
3. **Social Equality and Welfare**: Nordic model foundations, universal access
4. **Rule of Law and Democratic Governance**: Institutional integrity, transparency
5. **Economic Pragmatism**: Competitiveness, innovation, sustainable prosperity
6. **Environmental Responsibility**: Climate, sustainability, intergenerational equity
7. **European Integration**: EU solidarity, collective action, regulatory cooperation
8. **Nordic Cooperation**: Regional identity, shared values, practical collaboration
9. **Education and Human Capital**: Knowledge society, continuous learning
10. **Technological Leadership**: Digital sovereignty, innovation capacity

## Critical Instructions

- **Be axiomatic**: State what Finland should prioritize, not what it currently does
- **Identify real tensions**: Each value should list 2-3 other values it can genuinely conflict with — not abstract possibilities but real policy dilemmas Finland faces
- **Be specific to Finland**: Ground each value in Finnish context, not generic democratic principles
- **Use your training knowledge**: This task uses your existing knowledge of Finnish policy discourse. Do not reference web search or file tools — this is a single analysis task, not an agentic workflow
- **Produce all values in a single response**: Output the complete set of values with clear `---` separation between each

Begin your response with the first value document (starting with `---`).
