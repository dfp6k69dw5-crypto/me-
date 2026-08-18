#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOM = ROOT / "room"
SOCIETY = ROOT / "society"
CONFIG = ROOM / "config.json"
MARKER = ROOM / "sterilization.json"
STERILIZATION_VERSION = 1
CLEAN_BOOT = "room-sterile-v1-2026-08-18"


def load(path: Path, default):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def save(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def rel_template() -> dict:
    return {
        "social_model": 3,
        "legacy_familiarity": 0.02,
        "exposure": 0.064,
        "direct_familiarity": 0.08,
        "trust": 0.10,
        "predictability": 0.12,
        "reciprocity": 0.08,
        "warmth": 0.12,
        "respect": 0.12,
        "disclosure_depth": 0.0,
        "tension": 0.0,
        "direct_turns": 0,
        "observed_turns": 0,
        "repair_attempts": 0,
        "repair_successes": 0,
        "last_direct_cycle": None,
        "shared_references": [],
        "events": [],
        "reports": [],
    }


def fresh_minds(order: list[str]) -> dict:
    entities = {}
    for entity in order:
        entities[entity] = {
            "fast": {"activation": 0.2, "attention": []},
            "medium": {"topics": [], "branch_interest": 0},
            "slow": {"social_energy": 0.55},
            "noise": {},
            "room_memories": [],
            "self_history": [],
            "last_event": None,
            "spoken": 0,
            "silences": 0,
            "people": {other: rel_template() for other in order if other != entity},
        }
    return {"entities": entities}


def clean_topic() -> dict:
    return {
        "semantic_schema": 3,
        "id": "topic-000000",
        "root": None,
        "current_facet": None,
        "facets": [],
        "visited_facets": [],
        "facet_index": 0,
        "unresolved": [],
        "examples": [],
        "disagreements": [],
        "shared_references": [],
        "participants": ["sarah", "mara", "owen", "jules"],
        "turns": 0,
        "low_novelty_beats": 0,
        "recent_terms": [],
        "last_shift_cycle": 0,
        "status": "forming",
    }


def main() -> int:
    current_marker = load(MARKER, {})
    if int(current_marker.get("sterilization_version", 0)) >= STERILIZATION_VERSION and current_marker.get("boot_id") == CLEAN_BOOT:
        print("Room sterilization already applied")
        return 0

    stamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    cfg = load(CONFIG, {})
    cfg["boot_id"] = CLEAN_BOOT
    save(CONFIG, cfg)

    order = ["sarah", "mara", "owen", "jules"]
    profiles = cfg.get("p", {})
    minds = fresh_minds(order)
    topic = clean_topic()
    state = {
        "version": "room-cognition-v5",
        "boot_id": CLEAN_BOOT,
        "cycle": 0,
        "silence_cycles": 0,
        "last_speaker": None,
        "last_run": stamp,
        "messages": 0,
        "last_public_event": None,
        "note": "sterilized private-model v5; pre-sterilization cognition quarantined",
        "last_beat_id": None,
        "beat_contributors": [],
        "beat_message_count": 0,
        "topic_episode": topic,
    }
    discourse = {"nodes": [], "roots": []}

    summary_entities = {}
    for entity in order:
        profile = profiles.get(entity, {})
        rels = minds["entities"][entity]["people"]
        summary_entities[entity] = {
            "name": profile.get("name", entity.title()),
            "profile": profile,
            "genome": profile.get("traits", {}),
            "development": {
                "turns": 0,
                "spoken": 0,
                "silences": 0,
                "topic_weights": {},
                "relationships": {
                    other: {
                        key: value
                        for key, value in rel.items()
                        if key in {
                            "exposure", "direct_familiarity", "trust", "predictability",
                            "reciprocity", "warmth", "respect", "disclosure_depth",
                            "tension", "direct_turns", "repair_successes"
                        }
                    }
                    for other, rel in rels.items()
                },
            },
            "memory": [],
        }

    live = {
        "generated_at": stamp,
        "architecture_version": "room-cognition-v5",
        "boot_id": CLEAN_BOOT,
        "minds": {"schema": 5, "entities": summary_entities},
        "profiles": profiles,
        "state": state,
        "conversation": [],
        "discourse": discourse,
        "topic_episode": topic,
        "network": {
            "compute_nodes": 12,
            "entities": 4,
            "nodes_per_entity": 3,
            "tasks_per_node": 4,
            "active_processes": 48,
            "voting": False,
            "public_bus": True,
            "private_scope": "same_entity",
            "beat_output": "4 mandatory unique speakers",
            "private_pipeline": "perception->deliberation->expression",
            "history_generation": CLEAN_BOOT,
        },
    }
    feed = {
        "generated_at": stamp,
        "state": state,
        "minds": {"entities": summary_entities},
        "conversation": [],
    }

    # Primary Room reservoirs.
    save(ROOM / "conversation.json", [])
    save(ROOM / "discourse.json", discourse)
    save(ROOM / "cognitive_state.json", minds)
    save(ROOM / "state.json", state)
    save(ROOM / "live.json", live)
    save(ROOM / "feed.json", feed)

    # Legacy Society reservoirs are sterilized too so no future migration can rehydrate them.
    save(SOCIETY / "conversation.json", [])
    save(SOCIETY / "minds.json", {"entities": {}})
    save(SOCIETY / "cognition.json", {"sterilized": True, "boot_id": CLEAN_BOOT, "at": stamp})
    save(SOCIETY / "state.json", {"sterilized": True, "boot_id": CLEAN_BOOT, "at": stamp})
    save(SOCIETY / "live.json", live)

    archive = SOCIETY / "archive"
    if archive.exists():
        for path in archive.rglob("*"):
            if path.is_file():
                path.unlink()

    # Diagnostic traces are not cognition, but clear stale historical copies anyway.
    for name in ("private-full-beat-diagnostic.json", "private-model-diagnostic.json", "private-secret-presence.json"):
        path = ROOM / name
        if path.exists():
            save(path, {"sterilized": True, "boot_id": CLEAN_BOOT, "at": stamp})

    save(MARKER, {
        "sterilization_version": STERILIZATION_VERSION,
        "boot_id": CLEAN_BOOT,
        "sterilized_at": stamp,
        "policy": "No pre-sterilization conversational or derived historical state may be loaded into cognition.",
        "reset": [
            "room conversation", "room discourse", "entity self histories", "entity room memories",
            "relationship event/report/shared-reference histories", "topic history", "live snapshots",
            "public feed", "legacy society conversation/minds/cognition/state/live", "society archives",
            "diagnostic historical traces"
        ],
    })
    print(f"STERILIZED {CLEAN_BOOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
