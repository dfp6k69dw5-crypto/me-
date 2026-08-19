#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import room_social_v5 as social
import room_engine_v5 as engine
import room_private_model as private_model

GENERATORS = ("sarah", "mara", "owen", "jules")
PARTICIPANTS = (*GENERATORS, "allen")


def require(name: str, ok: bool, detail: object = "") -> None:
    if not ok:
        raise AssertionError(f"{name}: {detail}")
    print(f"PASS: {name}")


def main() -> int:
    generators = tuple(engine.ORDER)
    require("autonomous generator iteration remains exactly four entities", generators == GENERATORS, generators)
    require("Allen is not generated as an autonomous entity", "allen" not in generators, generators)
    require("engine participant set contains Allen", tuple(engine.PARTICIPANTS) == PARTICIPANTS, engine.PARTICIPANTS)

    social_participants = tuple(getattr(social, "PARTICIPANTS", ()))
    require("social participant set contains Allen", social_participants == PARTICIPANTS, social_participants)
    require("social generator order remains exactly four", tuple(social.ORDER) == GENERATORS, social.ORDER)

    mind = {"entities": {entity: {"people": {}} for entity in GENERATORS}}
    social.migrate_minds(mind)
    require(
        "relationship migration creates Allen for every autonomous entity",
        all("allen" in mind["entities"][entity]["people"] for entity in GENERATORS),
        {entity: sorted(mind["entities"][entity]["people"]) for entity in GENERATORS},
    )

    allen_turn = {
        "id": "sim-allen",
        "speaker": "allen",
        "text": "Sarah, do you actually agree with that?",
        "cognition": {"target": "sarah", "move_type": "follow_up", "topic_terms": ["agreement"]},
        "discourse_id": "d-sim-allen",
        "parent_discourse_id": None,
    }
    event = social.classify_event("sarah", allen_turn, {"d-sim-allen": allen_turn})
    require(
        "social event classifier recognizes Allen as Sarah's direct addressee partner",
        isinstance(event, dict) and event.get("speaker") == "allen" and event.get("direct") is True,
        event,
    )

    topic = social.topic_template(1)
    require("topic participant state contains Allen", tuple(topic.get("participants", ())) == PARTICIPANTS, topic.get("participants"))

    social.observe_message(mind, allen_turn, 1, {"d-sim-allen": allen_turn})
    allen_rel = mind["entities"]["sarah"]["people"].get("allen", {})
    require(
        "direct Allen turn updates Sarah-to-Allen relationship state",
        int(allen_rel.get("direct_turns", 0)) >= 1 and int(allen_rel.get("observed_turns", 0)) >= 1,
        allen_rel,
    )

    expression_schema = private_model._schema("expression", "sarah")
    expression_targets = expression_schema["properties"]["target"].get("enum", [])
    require("expression schema can target Allen", "allen" in expression_targets, expression_targets)

    thought_schema = private_model._schema("thought", None)
    thought_targets = thought_schema["properties"]["preferred_partner"].get("enum", [])
    require("thought schema can choose Allen", "allen" in thought_targets, thought_targets)

    # room_engine_v5 is a compatibility wrapper; sense() remains bound to the
    # preserved core module. Patch the bindings that sense() actually resolves,
    # otherwise this simulator would accidentally read the live Room conversation.
    core = getattr(engine, "_core", engine)
    owners = (engine,) if core is engine else (engine, core)
    originals = {
        owner: (owner.conv, owner.minds, owner.state, owner.choose_partner)
        for owner in owners
    }
    try:
        current_state = engine.fresh_state()
        current_state["cycle"] = 41
        engine_mind = engine.fresh_minds()
        simulated_history = [{
            "id": "sim-allen-engine",
            "at": "2026-08-19T22:40:00Z",
            "speaker": "allen",
            "text": "Sarah, do you actually agree with that?",
            "runtime": engine.VERSION,
            "boot_id": engine.BOOT,
            "cognition": {"target": "sarah", "move_type": "follow_up"},
        }]
        for owner in owners:
            owner.conv = lambda history=simulated_history: history
            owner.minds = lambda value=engine_mind: value
            owner.state = lambda value=current_state: value
            owner.choose_partner = lambda *args, **kwargs: "mara"
        sensed = engine.sense(1, "allen-response-sim")
        private = sensed.get("private") or {}
        require("latest Allen turn remains active engine partner", private.get("partner") == "allen", private.get("partner"))
        relationship = private.get("relationship")
        require(
            "Allen engine partner has a usable relationship view",
            isinstance(relationship, dict) and "trust" in relationship and "tension" in relationship,
            relationship,
        )
    finally:
        for owner, values in originals.items():
            owner.conv, owner.minds, owner.state, owner.choose_partner = values

    print("PASS: Allen social participation boundary is green")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
