#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy

from room_semantic_epoch import active_messages, recover_documents

START = "2026-08-20T12:30:00Z"

state = {
    "cycle": 3863,
    "boot_id": "room-sterile-v4-2026-08-18",
    "topic_episode": {
        "semantic_schema": 4,
        "id": "topic-000001",
        "root": "learning",
        "current_facet": "public-expression",
        "facets": ["skepticism", "language model", "speak"],
        "visited_facets": ["public expression", "memory"],
        "participants": ["sarah", "mara", "owen", "jules", "allen"],
    },
}

relationship = {
    "exposure": 0.43,
    "direct_familiarity": 0.11,
    "trust": 0.10,
    "predictability": 0.13,
    "reciprocity": 0.10,
    "warmth": 0.13,
    "respect": 0.12,
    "direct_turns": 32,
    "observed_turns": 50,
}

minds = {"entities": {}}
for entity in ("sarah", "mara", "owen", "jules"):
    minds["entities"][entity] = {
        "fast": {"activation": 0.87, "attention": ["skepticism", "public-expression"]},
        "medium": {"topics": ["learning", "skepticism"], "branch_interest": 0.8},
        "slow": {"social_energy": 0.55},
        "noise": {"kept": True},
        "room_memories": [
            {"source": "old-1", "speaker": "sarah", "text": "public-expression in INPUT_JSON"},
            {"source": "old-2", "speaker": "mara", "text": "remember skepticism better in the future"},
        ],
        "self_history": [{"source": "old-3", "text": "language model speak"}],
        "last_event": "old-3",
        "spoken": 3863,
        "silences": 0,
        "people": {"allen": deepcopy(relationship)},
    }

conversation = [
    {
        "id": "old-1",
        "at": "2026-08-20T12:20:00Z",
        "speaker": "sarah",
        "text": "public-expression in INPUT_JSON",
        "runtime": "room-cognition-v5",
        "boot_id": "room-sterile-v4-2026-08-18",
    },
    {
        "id": "old-2",
        "at": "2026-08-20T12:25:00Z",
        "speaker": "mara",
        "text": "remember skepticism better in the future",
        "runtime": "room-cognition-v5",
        "boot_id": "room-sterile-v4-2026-08-18",
    },
    {
        "id": "new-allen",
        "at": "2026-08-20T12:31:00Z",
        "speaker": "allen",
        "text": "Let's talk about bioluminescent mushrooms",
        "runtime": "room-cognition-v5-participant",
        "boot_id": "room-sterile-v4-2026-08-18",
    },
]

recovered_state, recovered_minds, changed = recover_documents(state, minds, START)
assert changed, "RED: first recovery must perform a migration"
assert recovered_state.get("semantic_epoch_version") == 1
assert recovered_state.get("semantic_epoch_started_at") == START
assert (recovered_state.get("topic_episode") or {}).get("root") is None, "RED: poisoned topic root survived"

for entity, ent in recovered_minds["entities"].items():
    assert ent.get("room_memories") == [], f"RED: {entity} retained poisoned semantic memory"
    assert ent.get("self_history") == [], f"RED: {entity} retained poisoned self history"
    assert ent.get("last_event") is None, f"RED: {entity} retained pre-epoch last event"
    assert (ent.get("fast") or {}).get("attention") == [], f"RED: {entity} retained poisoned attention"
    assert (ent.get("medium") or {}).get("topics") == [], f"RED: {entity} retained poisoned topic attention"
    assert ent.get("spoken") == 3863, f"RED: {entity} development counter was reset"
    assert ent.get("people", {}).get("allen", {}).get("direct_turns") == 32, f"RED: {entity}/Allen relationship was reset"

active = active_messages(
    conversation,
    recovered_state,
    boot_id="room-sterile-v4-2026-08-18",
    runtime_prefix="room-cognition-v5",
)
assert [item.get("id") for item in active] == ["new-allen"], "RED: pre-epoch dialogue is still active cognition"
assert "bioluminescent mushrooms" in active[0]["text"], "RED: new participant turn was lost"

state2, minds2, changed2 = recover_documents(recovered_state, recovered_minds, "2026-08-20T12:40:00Z")
assert not changed2, "RED: semantic recovery is not idempotent"
assert state2 == recovered_state and minds2 == recovered_minds, "RED: second recovery mutated clean state"

print("PASS: semantic epoch archives poisoned cognition while preserving people and new participant turns")
