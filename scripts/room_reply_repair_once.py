#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
path = Path("scripts/room_engine_v5.py")
source = path.read_text()

if "def _coherent_recurrent(" not in source:
    source = source.replace("import json\nimport os\n", "import copy\nimport json\nimport os\n", 1)
    anchor = '\n\nif os.environ.get("ROOM_BRAIN_ACTIVE", "").strip() == "llama3.2-1b":\n'
    if anchor not in source:
        raise SystemExit("coherent reply repair anchor missing")

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

    for message in reversed(prior):
        cognition = message.get("cognition") if isinstance(message, dict) else {}
        target = str(cognition.get("target") or "").lower() if isinstance(cognition, dict) else ""
        speaker = str(message.get("speaker") or "").lower() if isinstance(message, dict) else ""
        if target == entity and speaker in participants and speaker != entity:
            live_event = message
            live_partner = speaker
            directly_addressed = True
            break

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
        field: relationship.get(field)
        for field in (
            "exposure", "direct_familiarity", "trust", "predictability", "reciprocity",
            "warmth", "respect", "disclosure_depth", "tension",
        )
        if field in relationship
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
        raise SystemExit("coherent reply activation anchor missing")
    source = source.replace(old, new, 1)
    path.write_text(source)

subprocess.run(
    [sys.executable, "-m", "py_compile", "scripts/room_engine_v5.py", "scripts/room_engine_v5_legacy.py", "scripts/room_engine_v5_core.py"],
    check=True,
)

subprocess.run(["git", "config", "user.name", "room-reply-repair"], check=True)
subprocess.run(["git", "config", "user.email", "actions@users.noreply.github.com"], check=True)
subprocess.run(["git", "add", "scripts/room_engine_v5.py"], check=True)
if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode != 0:
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
        raise SystemExit("could not publish coherent reply repair")

repo = os.environ.get("GITHUB_REPOSITORY", "maaronfanberg-lab/me-")
listing = subprocess.run(
    ["gh", "run", "list", "--repo", repo, "--workflow", "sarah-society.yml", "--status", "in_progress", "--limit", "20", "--json", "databaseId", "--jq", ".[].databaseId"],
    capture_output=True,
    text=True,
    check=True,
)
for run_id in listing.stdout.split():
    subprocess.run(["gh", "run", "cancel", run_id, "--repo", repo], check=False)
time.sleep(5)
subprocess.run(["gh", "workflow", "run", "sarah-society.yml", "--repo", repo, "--ref", "main", "-f", "entity=auto"], check=True)
print("coherent reply repair applied and fresh Room dispatched")
