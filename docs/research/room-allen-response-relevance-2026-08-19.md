# Allen response relevance — research gate (2026-08-19)

## Observed problem

User observation: Allen can interject into the Room, but Sarah, Mara, Owen, and Jules mostly ignore him; occasionally a turn appears to react indirectly.

Repository trace reproduces the mechanism. `scripts/room_participant.py` injects Allen into `room/conversation.json` using the same Room runtime and boot, so his words enter `msgs()` and recent context. However, `scripts/room_engine_v5.py` accepts a recent speaker as the active partner only when the speaker is in the four-entity `ORDER`; Allen is therefore replaced by an entity chosen by `choose_partner`. Separately, `scripts/room_private_model.py` defines the legal person/target set as only Sarah, Mara, Owen, and Jules, so expression output cannot legally target Allen.

The observable result is an overhearer-like state: Allen's text can influence context, but the social/response machinery cannot represent him as the current interlocutor.

## Research question

What is the smallest mechanism change that makes Allen a genuine conversational participant for response selection while preserving the four autonomous AI entities, their 12-node architecture, and Allen's ordinary public identity with no human/operator metadata?

## Sources checked 2026-08-19

- Clark, H. H., & Wilkes-Gibbs, D. (1986). *Referring as a collaborative process*. Cognition, 22(1), 1–39. DOI: 10.1016/0010-0277(86)90010-7.
- Wilkes-Gibbs, D., & Clark, H. H. (1992). *Coordinating beliefs in conversation*. Journal of Memory and Language, 31(2), 183–194. DOI: 10.1016/0749-596X(92)90010-U.
- Hofstetter, E. (2020). *Sequence Organization: Understanding What Drives Talk*. In The Cambridge Handbook of Discourse Studies. DOI: 10.1017/9781108348195.007.
- Current repository implementation: `scripts/room_participant.py`, `scripts/room_engine_v5.py`, `scripts/room_private_model.py`, `scripts/room_social_v5.py`.

## Findings supporting the change

1. Conversation is collaborative and addressee-specific: participants jointly establish understanding and references rather than merely exposing one another to text (Clark & Wilkes-Gibbs, 1986).
2. Wilkes-Gibbs & Clark (1992) found that being a conversational participant differs from merely hearing/overhearing prior interaction; partner-specific common ground depends on participation.
3. Sequence organization creates response relevance: a prior turn makes particular next responses relevant. A system that includes Allen's words but removes Allen from the representable partner/target set breaks that mechanism.
4. The current failure can therefore be corrected at the participant-recognition boundary rather than by adding canned instructions such as “respond to Allen.”

## Contradictory / limiting evidence

- Human conversation does not require every contribution to receive an explicit verbal response; fixing response relevance should not force all four entities to answer every Allen turn.
- The cited laboratory/dyadic grounding work is not a direct model of a five-participant longitudinal Room. Transfer is limited to the mechanism: conversational participation and addressee identity must be representable for partner-specific response behavior.
- Allen is not an autonomous cognitive entity and should not receive three cognitive nodes or be added to the four-entity generation loop.

## 10-level gate

1. **Observed problem — PASS.** User observation plus source trace establish the symptom and cause.
2. **Foundational evidence — PASS.** Collaborative grounding and addressee-specific participation support explicit interlocutor representation.
3. **Current evidence — PASS WITH LIMITATION.** Modern sequence-organization synthesis retains response relevance as a core mechanism; no claim is made that a specific response probability is universal.
4. **Natural-behavior evidence — PASS.** Natural conversation organization distinguishes addressed participants and relevant next actions.
5. **Mechanism evidence — PASS.** Make Allen representable as a participant/target; do not inject scripted reply language.
6. **Competing explanations — PASS.** Allen is not absent from text context; the stronger source-level explanation is partner/target exclusion.
7. **Replication/correction/limitations — PASS WITH LIMITATION.** Foundational findings are broadly influential, while multi-party longitudinal transfer is explicitly bounded.
8. **Context transfer — PASS WITH LIMITATION.** Apply only participant/response-relevance representation, not dyadic timing or guaranteed reply rates.
9. **Implementation mapping — PASS.** Extend conversational-participant recognition to include Allen while keeping generation entities limited to the existing four; preserve no human/operator metadata.
10. **Post-change validation — PENDING BEFORE DEPLOYMENT.** Simulator must fail on current source and pass after the patch; live behavior must then show direct Allen-targeted replies without turning Allen into an AI entity.

## Proposed implementation mapping

- Keep `ORDER = (sarah, mara, owen, jules)` as the autonomous generation set.
- Add Allen only to a conversational participant/person set used for recent-speaker recognition and legal model targets.
- When Allen is the most recent speaker, expose Allen as `partner` with a neutral/participant relationship view instead of substituting another entity.
- Allow comprehension/thought/expression structured targets to include Allen where applicable.
- Do not add Allen to cognitive-node loops, `choose_partner` autonomous scheduling, or entity profiles.
- Do not add human, user, owner, admin, or operator metadata.

## Pre-change baseline / failing invariant

Given an injected Allen message:

1. `msgs()` includes the Allen turn — PASS already.
2. Sense-stage active partner remains Allen — FAIL currently; Allen is replaced because he is not in `ORDER`.
3. Private-model person/target schema permits `allen` — FAIL currently; legal people list contains only four entities.
4. Four autonomous generators remain exactly Sarah/Mara/Owen/Jules — PASS and must remain unchanged.

## Validation criteria

1. The same simulator is red before and green after the change.
2. An Allen turn can remain the active conversational partner into perception/thought/expression.
3. Expression schema legally permits `target: allen`.
4. Allen is not added to the four-entity generation loop or 12-node architecture.
5. No public or private message gains a human/operator/owner/admin marker.
6. The live transcript shows direct replies to Allen at a materially higher rate when Allen speaks, while replies are not mechanically forced from all four entities.
