#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import room_engine_v5 as engine
import room_private_model as private_model


def require(name: str, ok: bool, detail: object = "") -> None:
    if not ok:
        raise AssertionError(f"{name}: {detail}")
    print(f"PASS: {name}")


def main() -> int:
    generators = tuple(engine.ORDER)
    require(
        "autonomous generator iteration remains exactly four entities",
        generators == ("sarah", "mara", "owen", "jules"),
        generators,
    )
    require("Allen is not generated as an autonomous entity", "allen" not in generators, generators)
    require("Allen is a legal conversational member", "allen" in engine.ORDER, engine.ORDER)
    require(
        "explicit participant set contains four entities plus Allen",
        tuple(engine.PARTICIPANTS) == ("sarah", "mara", "owen", "jules", "allen"),
        engine.PARTICIPANTS,
    )

    expression_schema = private_model._schema("expression", "sarah")
    expression_targets = expression_schema["properties"]["target"].get("enum", [])
    require("expression schema can target Allen", "allen" in expression_targets, expression_targets)

    thought_schema = private_model._schema("thought", None)
    thought_targets = thought_schema["properties"]["preferred_partner"].get("enum", [])
    require("thought schema can choose Allen", "allen" in thought_targets, thought_targets)

    original_conv = engine.conv
    original_minds = engine.minds
    original_state = engine.state
    original_choose = engine.choose_partner
    try:
        current_state = engine.fresh_state()
        current_state["cycle"] = 41
        mind = engine.fresh_minds()
        allen_turn = {
            "id": "sim-allen",
            "at": "2026-08-19T22:40:00Z",
            "speaker": "allen",
            "text": "Sarah, do you actually agree with that?",
            "runtime": engine.VERSION,
            "boot_id": engine.BOOT,
            "cognition": {"target": "sarah", "move_type": "follow_up"},
        }
        engine.conv = lambda: [allen_turn]
        engine.minds = lambda: mind
        engine.state = lambda: current_state
        engine.choose_partner = lambda *args, **kwargs: "mara"
        sensed = engine.sense(1, "allen-response-sim")
        private = sensed.get("private") or {}
        require("latest Allen turn remains active partner", private.get("partner") == "allen", private.get("partner"))
        relationship = private.get("relationship")
        require(
            "Allen partner has a usable neutral relationship view",
            isinstance(relationship, dict) and "trust" in relationship and "tension" in relationship,
            relationship,
        )
    finally:
        engine.conv = original_conv
        engine.minds = original_minds
        engine.state = original_state
        engine.choose_partner = original_choose

    # room_private_commit.py uses `target not in c.ORDER`; membership behavior is
    # therefore the publication boundary. Iteration must remain four while Allen
    # membership is true.
    require("publisher membership semantics preserve Allen targets", "allen" in engine.ORDER, engine.ORDER)

    print("PASS: Allen response-relevance boundary is green")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
