#!/usr/bin/env python3
from __future__ import annotations

# trigger: 2026-08-19 validated Allen response relevance repair

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import room_engine_v5 as engine
import room_private_model as private_model


def check(name: str, ok: bool, detail: str = "") -> dict:
    return {"name": name, "pass": bool(ok), "detail": detail}


def main() -> int:
    results: list[dict] = []

    results.append(check(
        "four autonomous generators remain unchanged",
        tuple(engine.ORDER) == ("sarah", "mara", "owen", "jules"),
        repr(tuple(engine.ORDER)),
    ))

    participants = tuple(getattr(engine, "PARTICIPANTS", ()))
    results.append(check(
        "Allen is a conversational participant without becoming a generator",
        participants == ("sarah", "mara", "owen", "jules", "allen"),
        repr(participants),
    ))

    expression_schema = private_model._schema("expression", "sarah")
    targets = expression_schema["properties"]["target"].get("enum", [])
    results.append(check(
        "expression schema may target Allen",
        "allen" in targets,
        repr(targets),
    ))

    thought_schema = private_model._schema("thought", None)
    preferred = thought_schema["properties"]["preferred_partner"].get("enum", [])
    results.append(check(
        "thought schema may select Allen as preferred partner",
        "allen" in preferred,
        repr(preferred),
    ))

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
        sensed = engine.sense(1, "allen-response-sim")  # Sarah thought node: no model call.
        partner = (sensed.get("private") or {}).get("partner")
        results.append(check(
            "latest Allen speaker remains the active partner",
            partner == "allen",
            repr(partner),
        ))
        relationship = (sensed.get("private") or {}).get("relationship")
        results.append(check(
            "Allen partner receives a usable relationship view",
            isinstance(relationship, dict) and "tension" in relationship and "trust" in relationship,
            repr(relationship),
        ))
    except Exception as exc:
        results.append(check("latest Allen speaker remains the active partner", False, f"{type(exc).__name__}: {exc}"))
        results.append(check("Allen partner receives a usable relationship view", False, f"{type(exc).__name__}: {exc}"))
    finally:
        engine.conv = original_conv
        engine.minds = original_minds
        engine.state = original_state
        engine.choose_partner = original_choose

    commit_source = (SCRIPTS / "room_private_commit.py").read_text()
    results.append(check(
        "publisher preserves Allen as a legal expression target",
        commit_source.count("target not in c.PARTICIPANTS") >= 2,
        "PARTICIPANTS guards=" + str(commit_source.count("target not in c.PARTICIPANTS")),
    ))

    forbidden = ("human_role", "operator_role", "owner_role", "admin_role")
    changed_sources = "\n".join((SCRIPTS / name).read_text() for name in (
        "room_engine_v5.py", "room_private_model.py", "room_private_commit.py"
    ))
    results.append(check(
        "no human/operator identity metadata is introduced",
        not any(marker in changed_sources for marker in forbidden),
        "forbidden identity fields absent",
    ))

    passed = all(item["pass"] for item in results)
    diagnostic = {"pass": passed, "results": results}
    print(json.dumps(diagnostic, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
