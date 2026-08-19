#!/usr/bin/env python3
from __future__ import annotations

"""Compatibility wrapper that makes Allen a real conversational participant.

The preserved core engine still has exactly four autonomous generators. This
wrapper changes membership semantics only: Allen may be recognized as a recent
speaker/target, while iteration, indexing, node ownership, and generation remain
Sarah/Mara/Owen/Jules only.
"""

import room_private_model as _private_model

# Structured model output must be allowed to refer directly to Allen.
if "allen" not in _private_model.PEOPLE:
    _private_model.PEOPLE = [*_private_model.PEOPLE, "allen"]

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

# Re-export the preserved engine API. Functions remain bound to the core module,
# where ORDER/minds/fresh_minds above have already been patched.
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


if __name__ == "__main__":
    _core.main()
