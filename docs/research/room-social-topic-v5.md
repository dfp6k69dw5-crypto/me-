# Room v5 — partner-specific relationships and topic depth

## Observed problem

The v4 engine guarantees four speakers per beat, but social development and topic development are too shallow. The legacy observer path increments a single familiarity value whenever another entity speaks, so mere exposure eventually collapses social distance. Topic continuation is bounded by a short discourse depth and repeatedly returns to a small generic starter/follow-up repertoire. This produces converging relationships, repeated wording, and broad-topic cycling.

Mandatory speech is a project constraint: Sarah, Mara, Owen, and Jules must each contribute exactly once per beat. v5 changes what their contributions do, not whether they speak.

## Research question

How should a four-person longitudinal conversation maintain mandatory participation while developing partner-specific relationships, deeper topic episodes, shared references, disagreement/repair, and non-uniform trust without treating exposure as trust?

## Evidence base

Starting evidence includes:

- Macy & Skvoretz (1998), *The Evolution of Trust and Cooperation Between Strangers: A Computational Model*, American Sociological Review 63:638–660 — social structure, optional interaction, local embeddedness, and diffusion of cooperation.
- Clark & Wilkes-Gibbs (1986), Cognition, doi:10.1016/0010-0277(86)90010-7 — collaborative grounding and reference.
- Schober & Clark (1989), Cognitive Psychology, *Understanding by addressees and overhearers* — direct addressees and overhearers do not acquire equivalent understanding merely by hearing the same words.
- Brennan & Clark (1996), JEP:LMC, doi:10.1037/0278-7393.22.6.1482 — partner-specific conceptual pacts and lexical entrainment.
- Sacks, Schegloff & Jefferson (1974) and Stivers et al. (2009), PNAS, doi:10.1073/pnas.0903616106 — turn organization and timing.
- Schegloff, Jefferson & Sacks (1977) — repair and preference for self-repair.
- Laurenceau, Barrett & Pietromonaco (1998), JPSP, doi:10.1037/0022-3514.74.5.1238 — disclosure, perceived responsiveness, and intimacy.
- Aron et al. (1997), PSPB, doi:10.1177/0146167297234003 — gradual reciprocal disclosure and closeness.
- Huang et al. (2017), JPSP, doi:10.1037/pspi0000097, considered together with later reanalysis/correction literature — follow-up questions can signal responsiveness but should not be equated mechanically with listening.
- llama.cpp official server documentation — one local model server supports `/health`, `/completion`, and parallel decoding, allowing private node prompts to stay in runtime secrets rather than the public repository.

## Findings supporting the change

1. Exposure, direct participation, familiarity, trust, reciprocity, warmth, respect, and disclosure are distinct constructs and should not be represented by one automatically increasing scalar.
2. Relationship state should be directed and asymmetric. A→B need not equal B→A.
3. Overhearing may update exposure/knowledge, but direct relationship development should require interaction involving that pair.
4. Trust should update conservatively and only when an interaction contains interpersonal stake or informative reliability/repair evidence; ordinary chatter should not increase trust.
5. Shared references should accumulate per pair and become available for later callbacks.
6. Topic depth is better represented as an episode with a root, current facet, discovered facets, shared references, unresolved material, and novelty/saturation state than as a fixed discourse-depth counter.
7. Topic continuation should favor concrete facets already introduced; a generic follow-up question is not itself evidence of deeper conversation.
8. Stronger ties may influence targeting, but weak-tie novelty should remain possible so the group does not freeze into permanent dyads.
9. Mandatory four-person speech can coexist with differentiated interaction if each contribution has a distinct function: answer, deepen, compare, callback, disagreement, repair, support, or bridge.
10. Private prompts should be runtime-only. Public code should contain schemas, reducers, validation, and fallback behavior but not the private instruction text.

## Competing explanations and limitations

The repetitive v4 output is partly caused by deterministic canned language, not only by its social model. A better relationship model alone cannot guarantee natural language. The local Qwen2.5-0.5B model may also be too small to produce consistently strong multi-party conversation, so deterministic validation/fallback remains necessary.

Research on dyads does not transfer perfectly to four simultaneous entities. The Room's mandatory all-four speech is also unlike ordinary human conversation. v5 therefore treats the research as mechanism guidance rather than claiming the Room is a literal model of human interaction.

The numerical deltas in `room_social_v5.py` are conservative engineering heuristics chosen to make unsupported trust growth difficult. They are not empirical constants. Post-change measurements must determine whether they need revision.

## 10-level gate

1. Observed problem: PASS — visible repetition plus source-level automatic familiarity growth.
2. Foundational evidence: PASS — conversation analysis, grounding, social exchange/trust literature.
3. Current evidence: PASS WITH ONGOING REVIEW — later experimental/network work and current runtime docs checked.
4. Natural-behavior evidence: PASS — addressee/overhearer, turn-taking, repair, disclosure and conversational grounding studies.
5. Mechanism evidence: PASS — state separation, directed history, grounding, topic episodes, repair/callback mechanisms.
6. Competing explanations: PASS — language-generation limitations explicitly retained as a separate cause.
7. Replication/correction/limitations: PASS WITH CAUTION — question-asking reanalysis/correction and context limits noted.
8. Context transfer: PASS WITH CAUTION — four-person mandatory speech differs from studied dyads; validation is required.
9. Implementation mapping: PASS — implemented in `room_social_v5.py`, `room_engine_v5.py`, `room_private_model.py`, and the Room workflow.
10. Post-change validation: PENDING DEPLOYMENT.

## Implementation mapping

- Nodes 0/3/6/9: social perception / grounding role. Optional private prompt is supplied only at runtime.
- Nodes 1/4/7/10: private topic/relationship deliberation role. Optional private prompt is supplied only at runtime.
- Nodes 2/5/8/11: expression role. Optional private prompt is supplied only at runtime.
- All 12 nodes remain active; all four entities remain mandatory public contributors per beat.
- Relationship reducer is deterministic. The model does not directly set trust numbers.
- New directed relationship dimensions: exposure, direct familiarity, trust, predictability, reciprocity, warmth, respect, disclosure depth, tension, direct-turn count, repair attempts/successes, and shared references.
- Legacy `familiarity` is retained only as `legacy_familiarity` for audit/migration and is not converted into high trust.
- Topic episodes persist across beats and shift only after sustained low novelty. The current four-low-novelty-beat threshold is a testable heuristic, not a research constant.
- Exact repeated text is rejected by fallback generation.
- Prompt-leak markers and long verbatim overlap with the node's private prompt are rejected before model output is accepted.

## Privacy architecture

The public repository contains no private node prompt text. The workflow references three encrypted GitHub Actions secret names: `ROOM_PROMPT_PERCEPTION`, `ROOM_PROMPT_DELIBERATION`, and `ROOM_PROMPT_EXPRESSION`. At runtime, the parent shell selects the prompt for a node by role, removes all three secret variables from the node process environment, and supplies only `ROOM_NODE_PROMPT` to that one process. The local model is served only on runner-local `127.0.0.1`.

If the three secrets are absent, v5 remains functional using deterministic research-informed cognition. No prompt text is invented or exposed as a fallback.

## Pre-change baseline

- Four unique public speakers every beat: required and retained.
- Relationship state: single familiarity number that rises from observation, commonly saturating across pairs.
- Trust, reciprocity, tension, repair, partner-specific disclosure: not independently represented.
- Topic state: short parent-linked discourse depth and generic root resets.
- Generic starter/follow-up repertoire: small and repeatedly reused.
- Pair-specific callbacks: structurally weak.

## Validation criteria

After deployment:

- every beat must contain exactly Sarah, Mara, Owen and Jules once;
- overheard messages must change exposure but not direct familiarity or trust;
- ordinary direct chatter must not increase trust;
- directed pair states must be capable of diverging;
- active topic episodes should persist across multiple beats and accumulate narrower facets before bridging;
- exact sentence repetition should fall;
- callbacks should refer to actual stored partner history only;
- relationship dimensions must remain bounded and auditable;
- public output must not expose hidden prompts or private runtime instructions;
- Cloudflare feed delivery must continue uninterrupted.

## Post-change result

Pending live deployment and observation.
