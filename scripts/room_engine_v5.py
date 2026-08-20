#!/usr/bin/env python3
from __future__ import annotations

"""Compatibility wrapper that makes Allen a real conversational participant.

The preserved core engine still has exactly four autonomous generators. This
wrapper changes participant-facing semantics only: Allen may be recognized as a
recent speaker/target, and the first autonomous speaker after an Allen turn gets
a real adjacency response opportunity. The second voice usually stays with Allen
for one additional response. Iteration, indexing, node ownership, and generation
remain Sarah/Mara/Owen/Jules only.
"""

import copy
import hashlib
import os
import re

import room_private_model as _private_model
import room_personality_v2 as _personality_v2

# Structured model output must be allowed to refer directly to Allen.
if "allen" not in _private_model.PEOPLE:
    _private_model.PEOPLE = [*_private_model.PEOPLE, "allen"]

# Keep personality computation outside the LLM. The private model receives a
# compact, situation-relevant view of the fixed profile rather than 19 fields of
# undifferentiated persona prose on every turn.
_original_compact_payload = _private_model._compact_payload


def _personality_compact_payload(payload, role, self_entity=None):
    compact = _original_compact_payload(payload, role, self_entity)
    profile = payload.get("profile") if isinstance(payload.get("profile"), dict) else {}
    fixed = profile.get("psychology_v2") if isinstance(profile.get("psychology_v2"), dict) else None
    entity = str(self_entity or payload.get("entity") or "").lower()
    if not fixed or entity not in {"sarah", "mara", "owen", "jules"}:
        return compact

    appraisal = _personality_v2.appraise(
        entity,
        fixed,
        payload.get("event") if isinstance(payload.get("event"), dict) else None,
        payload.get("context") if isinstance(payload.get("context"), list) else [],
    )
    activated = []
    for item in appraisal.get("schema_activation", [])[:2]:
        if not isinstance(item, dict):
            continue
        # Clinical/schema names stay inside the deterministic appraiser. The
        # language model receives only their current perceptual and coping pull.
        activated.append({
            "interpretive_pull": item.get("interpretation_bias"),
            "coping_pull": item.get("coping_bias"),
        })
    compact["personality_context"] = {
        "identity": fixed.get("core_identity"),
        "values": list(fixed.get("values") or [])[:4],
        "motives": list(fixed.get("motives") or [])[:3],
        "interpersonal": appraisal.get("interpersonal_style"),
        "current": {
            "situation": appraisal.get("situation"),
            "latest_words": (appraisal.get("grounding") or {}).get("source_text"),
            "grounding_terms": (appraisal.get("grounding") or {}).get("terms"),
            "salience": appraisal.get("priority"),
            "personality_lens": appraisal.get("personality_lens"),
            "activated_sensitivities": activated,
            "usual_coping": list(appraisal.get("coping_patterns") or [])[:4],
        },
    }
    return compact


_private_model._compact_payload = _personality_compact_payload

import room_engine_v5_core as _core


class _ParticipantAwareOrder(tuple):
    """Iterate over four generators; treat Allen as a legal interlocutor."""

    def __contains__(self, item):
        return str(item or "").lower() == "allen" or super().__contains__(item)


_AI_ORDER = tuple(_core.ORDER)
ORDER = _ParticipantAwareOrder(_AI_ORDER)
PARTICIPANTS = _AI_ORDER + ("allen",)
_core.ORDER = ORDER

_ALLEN_RELATIONSHIP = {
    "exposure": 0.18,
    "direct_familiarity": 0.10,
    "trust": 0.10,
    "predictability": 0.10,
    "reciprocity": 0.10,
    "warmth": 0.10,
    "respect": 0.12,
    "disclosure_depth": 0.0,
    "tension": 0.0,
}


def _with_allen_relationship(mind):
    entities = (mind or {}).get("entities") or {}
    for entity in _AI_ORDER:
        state = entities.get(entity)
        if not isinstance(state, dict):
            continue
        people = state.setdefault("people", {})
        people.setdefault("allen", dict(_ALLEN_RELATIONSHIP))
    return mind


_original_fresh_minds = _core.fresh_minds
_original_minds = _core.minds


def fresh_minds():
    return _with_allen_relationship(_original_fresh_minds())


def minds():
    return _with_allen_relationship(_original_minds())


_core.fresh_minds = fresh_minds
_core.minds = minds

# A participant interruption is an adjacency event, not evidence that the
# ongoing topic has collapsed. Otherwise a repetitive room context can cause the
# first expression after Allen to discard Allen's turn and bridge elsewhere.
_original_context_collapsed = _core.context_collapsed


def _participant_context_collapsed(context):
    recent = list(context or [])
    if recent and isinstance(recent[-1], dict) and recent[-1].get("speaker") == "allen":
        return False
    return _original_context_collapsed(context)


_core.context_collapsed = _participant_context_collapsed


def _second_voice_engages_allen(key):
    """Deterministic 75% gate so beat retries preserve the same routing."""
    return hashlib.sha256(f"allen-second-voice:{key}".encode()).digest()[0] < 192


# The expression phase is sequential. Rank 0 always answers Allen when Allen is
# the latest public event. Rank 1 stays with Allen on a deterministic 75% gate,
# which makes two responders usual without turning every interruption into a
# four-voice chorus. Ranks 2-3 remain unconstrained.
_original_recurrent = _core.recurrent


def _participant_recurrent(node, key, bus_data):
    try:
        entity, _local, role, _tasks = _core.ni(node)
        rank = int(os.environ.get("ROOM_EXPRESSION_RANK", str(ORDER.index(entity))))
        source = _core.rp(bus_data, entity, role) if role == "expression" else None
        base = (source or {}).get("private") or {}
        latest = base.get("event") if isinstance(base.get("event"), dict) else None
        allen_latest = bool(
            role == "expression"
            and base.get("partner") == "allen"
            and latest
            and latest.get("speaker") == "allen"
        )
        primary_allen_reply = bool(allen_latest and rank == 0)
        secondary_allen_reply = bool(allen_latest and rank == 1 and _second_voice_engages_allen(key))
        routed_allen_reply = primary_allen_reply or secondary_allen_reply
    except Exception:
        routed_allen_reply = False
        primary_allen_reply = False
        secondary_allen_reply = False
        entity = None

    if not routed_allen_reply:
        return _original_recurrent(node, key, bus_data)

    routed_bus = copy.deepcopy(bus_data)
    thought = ((routed_bus.get("recurrent", {}).get(entity, {}) or {}).get("thought", {}) or {})
    thought_private = thought.get("private") if isinstance(thought.get("private"), dict) else {}
    deliberation = thought_private.get("deliberation") if isinstance(thought_private.get("deliberation"), dict) else None
    if isinstance(deliberation, dict):
        deliberation["action"] = "ANSWER" if primary_allen_reply else "DEEPEN"
        deliberation["preferred_partner"] = "allen"
        deliberation["new_information_goal"] = ""
        deliberation.pop("conversation_job", None)

    # Suppress the ordinary per-voice distinct-contribution job for a routed
    # Allen response. For selected rank 1, also keep the actual Allen turn as the
    # expression event instead of replacing it with rank 0's same-beat reply.
    original_job = _core.conversation_job
    original_prior = _core.prior_expression_messages
    _core.conversation_job = lambda *_args, **_kwargs: ""
    if secondary_allen_reply:
        _core.prior_expression_messages = lambda _node: []
    try:
        result = _original_recurrent(node, key, routed_bus)
    finally:
        _core.conversation_job = original_job
        _core.prior_expression_messages = original_prior

    if isinstance(result, dict):
        result = dict(result)
        private = dict(result.get("private") or {})
        expression = private.get("expression")
        if isinstance(expression, dict):
            expression = dict(expression)
            expression["target"] = "allen"
            expression["move"] = "answer" if primary_allen_reply else "deepen"
            # Hidden targeting is not enough for the participant-facing primary
            # response: live data showed dozens of Allen targets with zero spoken
            # uses of his name. Preserve model wording when it already names Allen;
            # otherwise make the primary addressee audible with a minimal prefix.
            utterance = str(expression.get("utterance") or "").strip()
            if primary_allen_reply and utterance and not re.search(r"\ballen\b", utterance, re.I):
                expression["utterance"] = f"Allen, {utterance}"
            private["expression"] = expression
            result["private"] = private
    return result


_core.recurrent = _participant_recurrent

# Re-export the preserved engine API. Functions remain bound to the core module,
# where ORDER/minds/fresh_minds/recurrent above have already been patched.
for _name in dir(_core):
    if _name.startswith("__") or _name in globals():
        continue
    globals()[_name] = getattr(_core, _name)

# Keep the wrapper's participant-aware values visible to importers such as
# room_private_commit.py.
globals()["ORDER"] = ORDER
globals()["PARTICIPANTS"] = PARTICIPANTS
globals()["fresh_minds"] = fresh_minds
globals()["minds"] = minds
globals()["recurrent"] = _participant_recurrent


def main():
    # room_private_commit.py replaces `room_engine_v5.commit` at runtime. The
    # preserved core's main() resolves globals in the core module, so forward
    # that override before dispatching the command.
    _core.commit = globals().get("commit", _core.commit)
    return _core.main()


if __name__ == "__main__":
    main()
