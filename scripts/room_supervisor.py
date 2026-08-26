#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

STALE_AFTER_SECONDS = 3 * 60
MAX_RESTARTS_PER_CYCLE = 2
CIRCUIT_COOLDOWN_SECONDS = 15 * 60


def _apply_coherent_reply_repair() -> None:
    """One-shot source migration; remove this hook after the repair lands."""
    path = Path("scripts/room_engine_v5.py")
    if not path.exists():
        return
    source = path.read_text()
    if "def _coherent_recurrent(" in source:
        return

    source = source.replace("import json\nimport os\n", "import copy\nimport json\nimport os\n", 1)
    anchor = '\n\nif os.environ.get("ROOM_BRAIN_ACTIVE", "").strip() == "llama3.2-1b":\n'
    if anchor not in source:
        raise RuntimeError("coherent reply repair anchor missing")

    block = r'''


def _coherent_recurrent(node, key, bus_data):
    """Align live event, intended partner, and relationship before expression."""
    entity, _local, role, _tasks = _legacy._core.ni(node)
    if role != "expression":
        return _LLAMA_ORIGINAL_RECURRENT(node, key, bus_data)

    routed = copy.deepcopy(bus_data)
    source_part = _legacy._core.rp(routed, entity, role)
    base = source_part.get("private") if isinstance(source_part.get("private"), dict) else {}
    prior = list(_legacy._core.prior_expression_messages(node))

    thought = ((routed.get("recurrent", {}).get(entity, {}) or {}).get("thought", {}) or {})
    thought_private = thought.get("private") if isinstance(thought.get("private"), dict) else {}
    deliberation = thought_private.get("deliberation") if isinstance(thought_private.get("deliberation"), dict) else None

    participants = set(_social.PARTICIPANTS)
    planned = str((deliberation or {}).get("preferred_partner") or base.get("partner") or "").lower()
    live_partner = planned if planned in participants and planned != entity else None
    live_event = None
    directly_addressed = False

    # Adjacency-pair rule: if somebody in this beat just addressed me, that turn
    # becomes my event and that speaker becomes my partner. Do not answer a stale
    # plan while pretending to have heard the new message.
    for message in reversed(prior):
        cognition = message.get("cognition") if isinstance(message, dict) else {}
        target = str(cognition.get("target") or "").lower() if isinstance(cognition, dict) else ""
        speaker = str(message.get("speaker") or "").lower() if isinstance(message, dict) else ""
        if target == entity and speaker in participants and speaker != entity:
            live_event = message
            live_partner = speaker
            directly_addressed = True
            break

    # Otherwise preserve autonomous partner choice, but make the event match it.
    if live_event is None and live_partner:
        for message in reversed(prior):
            speaker = str(message.get("speaker") or "").lower() if isinstance(message, dict) else ""
            if speaker == live_partner:
                live_event = message
                break

    if live_event is None or not live_partner:
        return _LLAMA_ORIGINAL_RECURRENT(node, key, routed)

    base["event"] = live_event
    base["partner"] = live_partner
    mind = _legacy._core.minds()
    relationship = (((mind.get("entities") or {}).get(entity) or {}).get("people") or {}).get(live_partner) or {}
    base["relationship"] = {
        key: relationship.get(key)
        for key in (
            "exposure", "direct_familiarity", "trust", "predictability", "reciprocity",
            "warmth", "respect", "disclosure_depth", "tension",
        )
        if key in relationship
    }
    source_part["private"] = base

    if isinstance(deliberation, dict):
        deliberation["preferred_partner"] = live_partner
        if directly_addressed:
            text = str(live_event.get("text") or "").rstrip()
            deliberation["action"] = "ANSWER" if text.endswith("?") else "DEEPEN"
            deliberation["new_information_goal"] = (
                "Respond to the specific message just addressed to you. "
                "Acknowledge its concrete point before adding one relevant thought."
            )
            deliberation.pop("conversation_job", None)

    # Core expression generation uses the final prior turn as its event. Keep all
    # ambient same-beat speech in context but move the selected partner turn last.
    ordered = [item for item in prior if item is not live_event] + [live_event]
    original_prior = _legacy._core.prior_expression_messages
    _legacy._core.prior_expression_messages = lambda _node: ordered
    try:
        return _LLAMA_ORIGINAL_RECURRENT(node, key, routed)
    finally:
        _legacy._core.prior_expression_messages = original_prior
'''
    source = source.replace(anchor, block + anchor, 1)

    old = '''    _legacy._private_model.run = _llama_model_run
    _legacy._core.model_run = _llama_model_run
'''
    new = '''    _legacy._private_model.run = _llama_model_run
    _legacy._core.model_run = _llama_model_run
    _LLAMA_ORIGINAL_RECURRENT = _legacy._core.recurrent
    _legacy._core.recurrent = _coherent_recurrent
    _legacy.recurrent = _coherent_recurrent
'''
    if old not in source:
        raise RuntimeError("coherent reply activation anchor missing")
    path.write_text(source.replace(old, new, 1))

    subprocess.run(
        [sys.executable, "-m", "py_compile", "scripts/room_engine_v5.py", "scripts/room_engine_v5_legacy.py", "scripts/room_engine_v5_core.py"],
        check=True,
    )
    subprocess.run(["git", "config", "user.name", "room-supervisor"], check=True)
    subprocess.run(["git", "config", "user.email", "actions@users.noreply.github.com"], check=True)
    subprocess.run(["git", "add", "scripts/room_engine_v5.py"], check=True)
    subprocess.run(["git", "commit", "-m", "Align Room replies with live addressees"], check=True)

    pushed = False
    for attempt in range(1, 6):
        if subprocess.run(["git", "push", "origin", "HEAD:main"]).returncode == 0:
            pushed = True
            break
        subprocess.run(["git", "fetch", "origin", "main"], check=True)
        subprocess.run(["git", "rebase", "origin/main"], check=True)
        time.sleep(attempt)
    if not pushed:
        raise RuntimeError("could not publish coherent reply repair")

    if os.environ.get("GH_TOKEN"):
        listing = subprocess.run(
            ["gh", "run", "list", "--repo", os.environ.get("GITHUB_REPOSITORY", "maaronfanberg-lab/me-"),
             "--workflow", "sarah-society.yml", "--status", "in_progress", "--limit", "20",
             "--json", "databaseId", "--jq", ".[].databaseId"],
            capture_output=True, text=True, check=True,
        )
        repo = os.environ.get("GITHUB_REPOSITORY", "maaronfanberg-lab/me-")
        for run_id in listing.stdout.split():
            subprocess.run(["gh", "run", "cancel", run_id, "--repo", repo], check=False)
        time.sleep(5)
        subprocess.run(
            ["gh", "workflow", "run", "sarah-society.yml", "--repo", repo, "--ref", "main", "-f", "entity=auto"],
            check=True,
        )


def _parse_time(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _stamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _base_control(control: dict | None) -> dict:
    source = control if isinstance(control, dict) else {}
    return {
        "version": 1,
        "last_observed_cycle": int(source.get("last_observed_cycle") or 0),
        "restart_cycle": int(source.get("restart_cycle") or 0),
        "restart_attempts": int(source.get("restart_attempts") or 0),
        "circuit_open": bool(source.get("circuit_open", False)),
        "circuit_opened_at": str(source.get("circuit_opened_at") or ""),
        "last_action": str(source.get("last_action") or ""),
        "last_checked_at": str(source.get("last_checked_at") or ""),
    }


def decide(state: dict, control: dict | None = None, *, now: datetime | None = None) -> dict:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)

    cycle = int((state or {}).get("cycle") or 0)
    last_run = _parse_time((state or {}).get("last_run"))
    age = None if last_run is None else max(0.0, (current - last_run).total_seconds())
    stale = last_run is None or age >= STALE_AFTER_SECONDS
    has_baseline = isinstance(control, dict) and "last_observed_cycle" in control
    ctl = _base_control(control)

    if not has_baseline:
        ctl.update({
            "last_observed_cycle": cycle,
            "restart_cycle": cycle if stale else 0,
            "restart_attempts": 1 if stale else 0,
            "circuit_open": False,
            "circuit_opened_at": "",
            "last_action": "restart" if stale else "initialize",
            "last_checked_at": _stamp(current),
        })
        if stale:
            return {"action": "restart", "reason": "stale_first_observation", "age_seconds": age, "control": ctl}
        return {"action": "initialize", "reason": "baseline_created", "age_seconds": age, "control": ctl}

    previous_cycle = ctl["last_observed_cycle"]
    progressed = cycle > previous_cycle

    if progressed:
        ctl.update({
            "last_observed_cycle": cycle,
            "restart_cycle": 0,
            "restart_attempts": 0,
            "circuit_open": False,
            "circuit_opened_at": "",
            "last_action": "healthy",
            "last_checked_at": _stamp(current),
        })
        return {"action": "healthy", "reason": "cycle_progress", "control": ctl}

    if not stale:
        ctl.update({
            "last_observed_cycle": max(previous_cycle, cycle),
            "restart_cycle": 0,
            "restart_attempts": 0,
            "circuit_open": False,
            "circuit_opened_at": "",
            "last_action": "healthy",
            "last_checked_at": _stamp(current),
        })
        return {"action": "healthy", "reason": "recent_beat", "age_seconds": age, "control": ctl}

    same_stalled_cycle = ctl["restart_cycle"] == cycle
    attempts = ctl["restart_attempts"] if same_stalled_cycle else 0

    if ctl["circuit_open"] and same_stalled_cycle:
        opened = _parse_time(ctl.get("circuit_opened_at"))
        cooled = opened is not None and (current - opened).total_seconds() >= CIRCUIT_COOLDOWN_SECONDS
        if cooled:
            ctl.update({
                "last_observed_cycle": max(previous_cycle, cycle),
                "restart_cycle": cycle,
                "restart_attempts": 1,
                "circuit_open": False,
                "circuit_opened_at": "",
                "last_action": "probe_restart",
                "last_checked_at": _stamp(current),
            })
            return {"action": "probe_restart", "reason": "circuit_cooldown_probe", "age_seconds": age, "control": ctl}
        ctl["last_checked_at"] = _stamp(current)
        ctl["last_action"] = "circuit_open"
        return {"action": "circuit_open", "reason": "cooldown", "age_seconds": age, "control": ctl}

    if attempts >= MAX_RESTARTS_PER_CYCLE:
        ctl.update({
            "last_observed_cycle": max(previous_cycle, cycle),
            "restart_cycle": cycle,
            "restart_attempts": MAX_RESTARTS_PER_CYCLE,
            "circuit_open": True,
            "circuit_opened_at": _stamp(current),
            "last_action": "circuit_open",
            "last_checked_at": _stamp(current),
        })
        return {"action": "circuit_open", "reason": "same_cycle_failed_replacements", "age_seconds": age, "control": ctl}

    ctl.update({
        "last_observed_cycle": max(previous_cycle, cycle),
        "restart_cycle": cycle,
        "restart_attempts": attempts + 1,
        "circuit_open": False,
        "circuit_opened_at": "",
        "last_action": "restart",
        "last_checked_at": _stamp(current),
    })
    return {"action": "restart", "reason": "stale_room", "age_seconds": age, "control": ctl}


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text())
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] != "check":
        print("usage: room_supervisor.py check [state.json] [control.json] [decision.json]", file=sys.stderr)
        return 2
    _apply_coherent_reply_repair()
    state_path = Path(argv[2]) if len(argv) > 2 else Path("room/state.json")
    control_path = Path(argv[3]) if len(argv) > 3 else Path(".github/room-supervisor-state.json")
    decision_path = Path(argv[4]) if len(argv) > 4 else Path(".github/room-supervisor-decision.json")
    result = decide(_load(state_path), _load(control_path))
    decision_path.parent.mkdir(parents=True, exist_ok=True)
    decision_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(result["action"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
