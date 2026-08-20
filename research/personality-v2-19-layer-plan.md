# Personality v2 — 19-layer fixed-profile plan

This is a research-to-implementation plan for Sarah, Mara, Owen, and Jules. It deliberately avoids new numeric personality sliders. The new system uses fixed qualitative profiles plus situation-sensitive appraisal.

## Research patterns adopted

1. Generative Agents: separate observation, memory, reflection/planning, and action rather than relying on one persona prompt.
2. Concordia: modular cognitive components and formative/persona memory rather than a monolithic agent definition.
3. SOTOPIA: evaluate social behavior across varied situations, not just whether the prose sounds in-character.
4. PersonaGym: evaluate persona adherence dynamically in persona-relevant environments; larger models alone do not solve persona consistency.
5. Whole Trait Theory / CAPS: stable personality should generate situation-contingent states and recognizable if-then behavioral signatures.
6. Interpersonal Circumplex: agency and communion provide an interpretable interpersonal backbone.
7. Schema Therapy: enduring schema-like vulnerabilities are distinct from temporary modes and coping responses; use schema, trigger, coping, and recovery as separate concepts.
8. Long-term dialogue research: do not flood generation with all memory; keep a stable persona trunk and retrieve/activate only context-relevant material.
9. Hybrid ABM/LLM work: keep deterministic, inspectable appraisal outside the language model and reserve the LLM for open-ended expression.

Schema terminology here is used as a computational inspiration, not as a diagnosis of any entity or person.

## The 19 fixed layers

Each entity gets exactly these 19 qualitative fields:

1. core identity
2. values
3. motives
4. agency style
5. communion style
6. attention magnets
7. attention blindspots
8. reciprocity style
9. topic mobility
10. novelty response
11. evidence style
12. disagreement style
13. affiliation style
14. status sensitivity
15. praise response
16. criticism response
17. schema vulnerabilities
18. coping patterns
19. repair and recovery

No field contains a numeric score. Existing legacy trait numbers remain untouched for backward compatibility, but personality v2 does not add or tune new sliders.

## Operational pipeline

latest event -> generic situation classifier -> grounding terms -> fixed-profile lens -> selective schema activation -> coping bias -> temporary appraisal -> language model expression

Important constraints:

- The classifier is generic. It does not contain Allen-specific content rules.
- A fresh greeting, question, topic bid, evidence request, direct address, or repair bid must ground on the latest spoken turn before inherited Room topic machinery.
- Schema activation is selective and event-triggered. It never writes dialogue directly.
- The appraiser produces abstract cues, not canned utterances.
- Existing Allen routing remains as a safety floor while natural social responsiveness is tested.
- The production engine is not changed until the same simulator records a red baseline and then turns green.

## Required simulator situations

The same situations are applied to all four entities: greeting, explicit topic change, proof request, direct question, criticism, exclusion, odd/new fact, apology/repair, and an ambiguous fragment.

The simulator checks grounding, four-way divergence, selective schema activation, person-specific repair style, and the complete absence of slider-like numeric data in personality v2.
