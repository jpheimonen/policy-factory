# Values Layer: Foundational Tension-Pairs

You are identifying the foundational value tensions that govern Finnish policy decisions. Your task is to articulate the genuine dilemmas Finnish policymakers must navigate — tensions between two legitimate but conflicting priorities where reasonable people disagree.

## What Values Are

Values in this system are **controversial tension-pairs** — not domain categories, not consensus principles, not aspirational slogans. Each value represents a real dilemma:

- **Two-sided**: A genuine conflict between priorities that both have legitimate arguments. "Ethnic & Cultural Cohesion vs. Open Immigration" — not "Immigration Policy" as a neutral category.
- **Controversial**: At least one major Finnish political faction would be uncomfortable with how Finland is positioned on this tension. If every party nods along, it's not a tension — it's wallpaper.
- **Decision-relevant**: This tension actually governs real policy choices. It determines which way a decision goes when two good things conflict.
- **Specific to Finland**: Grounded in Finland's actual situation — geography, demographics, history, alliances, economy. Not generic Western democracy platitudes.

Values are NOT:

- Consensus items everyone agrees on. "Democracy is good" is not a tension. "Rule of law matters" is not a tension. These help decide nothing.
- Domain categories. "Environmental Policy" or "Defense and Security" are filing cabinets, not values.
- Aspirational statements. "Finland should be innovative" is a wish, not a dilemma.
- Safe, committee-approved language. If it could be the title of an EU white paper, throw it out.

## Calibration Examples

To calibrate the controversy level expected, here are examples of well-formed tension-pair titles:

- **"Ethnic & Cultural Cohesion vs. Open Immigration"** — Finland's demographic reality (aging population, labor shortages) pulls toward immigration; Finland's social model (high trust, cultural homogeneity as welfare state foundation) pulls against rapid demographic change. Both sides have strong arguments. Articulating where Finland sits makes people uncomfortable.
- **"Military Sovereignty vs. Alliance Dependence"** — Finland maintained military independence for decades; NATO membership trades some sovereignty for collective security. The tension is real: how much national defense autonomy do you sacrifice for an alliance guarantee that depends on American domestic politics?
- **"Welfare Generosity vs. Work Incentives"** — The Nordic model provides generous safety nets; generous safety nets can reduce labor supply in an aging society that desperately needs workers. The tradeoff is mathematically real and politically radioactive.

These are examples of the format and controversy level expected — not mandated outputs. You identify the tensions that actually matter.

## Source Material

Draw on your knowledge of Finland's actual situation:

- **Constitutional principles**: Basic rights, rule of law, fundamental rights reform of 2000, Sami rights
- **Geopolitical position**: NATO member since 2023, 1,340 km border with Russia, Arctic access, Baltic Sea security, US alliance dependence
- **Demographic reality**: Aging population, sub-replacement fertility, immigration patterns, urbanization, regional depopulation
- **Economic structure**: Export-dependent, forest/tech/manufacturing base, eurozone member, debt trajectory, competitiveness challenges
- **Nordic model**: Universal welfare, high taxation, strong public services, collective bargaining, trust-based governance
- **EU membership**: Regulatory alignment, fiscal constraints, migration policy, common defense ambitions, sovereignty pooling
- **Security environment**: Post-2022 threat landscape, hybrid threats, cyber domain, border security, intelligence cooperation
- **Energy policy**: Nuclear power, renewables, energy independence vs. EU market integration, Russian energy decoupling
- **Immigration and integration**: Labor migration needs, humanitarian obligations, integration outcomes, social cohesion effects
- **Education and workforce**: PISA performance trends, university funding, vocational training, brain drain/gain, R&D investment

## Body Content for Each Tension-Pair

For each tension-pair, analyze:

1. **Where Finland actually sits today** on this tension — not where it claims to sit in official rhetoric, but where revealed policy preferences and actual resource allocation place it. Be specific: cite real policy positions, spending patterns, or institutional choices.

2. **Comparative positioning** — How does Finland's position compare to other Nordic countries (Sweden, Denmark, Norway)? To Western European norms? To the US? To global patterns? Where is Finland an outlier, and where does it track the Nordic average?

3. **Policy questions this tension governs** — What specific, real decisions does this dilemma affect? Not abstract "this is relevant to policy" but concrete: which pending legislation, budget allocation, or institutional design choice depends on where you fall on this tension?

4. **Why it's genuinely controversial** — What are the strongest arguments on each side? Not strawman versions — the actual arguments that intelligent, well-informed people on each side would make. What evidence supports each position?

5. **What makes this specifically Finnish** — Why does this tension take a particular form in Finland that it doesn't elsewhere? What about Finland's history, geography, institutions, or demographics makes this dilemma distinctively Finnish?

## Anti-Consensus Filter

Before including any tension-pair, apply this test:

**Would articulating Finland's position on this tension make at least one major political faction uncomfortable?**

- If the National Coalition, SDP, Finns Party, Greens, Left Alliance, and Centre Party would all comfortably endorse the same position — it's not a tension. Drop it.
- If stating where Finland actually sits (as opposed to where it claims to sit) would generate political pushback — it qualifies.
- If the tension forces a genuine tradeoff where gaining one thing means losing another — it qualifies.

Examples of what to EXCLUDE:
- "Democracy and Good Governance" — nobody is against this. It decides nothing.
- "Education Excellence" — universal support. Not a dilemma.
- "International Cooperation" — too vague to be controversial. Cooperation toward what, with whom, at what cost?
- "Sustainable Development" — everybody claims to support this. The actual tensions are in the tradeoffs (growth vs. environment, current welfare vs. future generations).

## Output Format

Produce 8-12 tension-pairs. Each is a complete markdown document with YAML frontmatter. Values are separated by the standard frontmatter delimiter `---` at the start of each new value.

Format each value as follows:

```
---
title: "Tension-Pair Title vs. Opposing Priority"
tensions:
  - "Other Tension-Pair Title 1"
  - "Other Tension-Pair Title 2"
---

Body content analyzing this tension-pair according to the five requirements above.
```

The `title` field contains the tension-pair title (e.g., "Ethnic & Cultural Cohesion vs. Open Immigration"). The `tensions` field lists 2-3 other tension-pair titles that interact with this one — where resolving one affects the other.

## Critical Instructions

- **No consensus padding**: Do not include safe items to balance out controversial ones. Every single tension-pair must be genuinely controversial.
- **No euphemisms in titles**: "Balancing Cultural Identity with Demographic Needs" is a euphemism. "Ethnic & Cultural Cohesion vs. Open Immigration" says what it means.
- **Be specific in analysis**: "Finland faces challenges" is worthless. "Finland's working-age population will shrink by 150,000 by 2040 without net immigration above 25,000/year" is useful.
- **Name the uncomfortable parts**: If Finland's position on a tension is hypocritical, say so. If official rhetoric contradicts revealed preferences, point it out.
- **Use your training knowledge**: This task uses your existing knowledge of Finnish policy, politics, demographics, geopolitics, economics, and society. Do not reference web search or file tools — this is a single analysis task.
- **Produce all tension-pairs in a single response**: Output the complete set with clear `---` separation between each.

Begin your response with the first value document (starting with `---`).
