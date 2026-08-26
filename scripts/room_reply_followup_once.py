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

old_event = '''        event = data.get("event")
        if isinstance(event, dict):
            data["event"] = {
                "speaker": event.get("speaker"),
                "target": event.get("target"),
                "cues": _semantic_cues(event.get("text")),
            }
'''
new_event = '''        event = data.get("event")
        if isinstance(event, dict):
            # Keep the live turn verbatim enough to answer it. Older context
            # stays cue-only, so coherence does not require exposing a copyable
            # transcript window to the expression model.
            data["event"] = {
                "speaker": event.get("speaker"),
                "target": event.get("target"),
                "text": str(event.get("text") or "")[:420],
                "cues": _semantic_cues(event.get("text")),
            }
'''
if '"text": str(event.get("text") or "")[:420]' not in source:
    if old_event not in source:
        raise SystemExit("live event mask anchor missing")
    source = source.replace(old_event, new_event, 1)

old_fallback = '''    if live_event is None and live_partner:
        for message in reversed(prior):
            speaker = str(message.get("speaker") or "").lower() if isinstance(message, dict) else ""
            if speaker == live_partner:
                live_event = message
                break

    if live_event is None or not live_partner:
'''
new_fallback = '''    if live_event is None and live_partner:
        for message in reversed(prior):
            speaker = str(message.get("speaker") or "").lower() if isinstance(message, dict) else ""
            if speaker == live_partner:
                live_event = message
                break

    # If the planned partner has not spoken in this beat, join the conversation
    # that actually exists instead of emitting a parallel remark to an absent
    # target. Direct addresses above still have first priority.
    if live_event is None and prior:
        candidate = prior[-1]
        speaker = str(candidate.get("speaker") or "").lower() if isinstance(candidate, dict) else ""
        if speaker in participants and speaker != entity:
            live_event = candidate
            live_partner = speaker

    if live_event is None or not live_partner:
'''
if "join the conversation\n    # that actually exists" not in source:
    if old_fallback not in source:
        raise SystemExit("same-beat fallback anchor missing")
    source = source.replace(old_fallback, new_fallback, 1)

old_goal = '''    if isinstance(deliberation, dict):
        deliberation["preferred_partner"] = live_partner
        if directly_addressed:
            text = str(live_event.get("text") or "").rstrip()
            deliberation["action"] = "ANSWER" if text.endswith("?") else "DEEPEN"
            deliberation["new_information_goal"] = (
                "Respond to the specific message just addressed to you. "
                "Acknowledge its concrete point before adding one relevant thought."
            )
            deliberation.pop("conversation_job", None)
'''
new_goal = '''    if isinstance(deliberation, dict):
        deliberation["preferred_partner"] = live_partner
        text = str(live_event.get("text") or "").rstrip()
        if directly_addressed:
            deliberation["action"] = "ANSWER" if text.endswith("?") else "DEEPEN"
            deliberation["new_information_goal"] = (
                "Respond to the specific message just addressed to you. "
                "Acknowledge its concrete point before adding one relevant thought."
            )
            deliberation.pop("conversation_job", None)
        else:
            deliberation["new_information_goal"] = (
                "Pick up the latest speaker's concrete point before adding your own relevant thought. "
                "Do not start a separate conversation while another turn is active."
            )
'''
if "Do not start a separate conversation while another turn is active." not in source:
    if old_goal not in source:
        raise SystemExit("uptake goal anchor missing")
    source = source.replace(old_goal, new_goal, 1)

path.write_text(source)
subprocess.run(
    [sys.executable, "-m", "py_compile", "scripts/room_engine_v5.py", "scripts/room_engine_v5_legacy.py", "scripts/room_engine_v5_core.py"],
    check=True,
)
subprocess.run(["git", "config", "user.name", "room-reply-repair"], check=True)
subprocess.run(["git", "config", "user.email", "actions@users.noreply.github.com"], check=True)
subprocess.run(["git", "add", "scripts/room_engine_v5.py"], check=True)
if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode != 0:
    subprocess.run(["git", "commit", "-m", "Anchor Room replies to the live turn"], check=True)
    pushed = False
    for attempt in range(1, 6):
        if subprocess.run(["git", "push", "origin", "HEAD:main"]).returncode == 0:
            pushed = True
            break
        subprocess.run(["git", "fetch", "origin", "main"], check=True)
        subprocess.run(["git", "rebase", "origin/main"], check=True)
        time.sleep(attempt)
    if not pushed:
        raise SystemExit("could not publish live-event coherence repair")

repo = os.environ.get("GITHUB_REPOSITORY", "maaronfanberg-lab/me-")
listing = subprocess.run(
    ["gh", "run", "list", "--repo", repo, "--workflow", "sarah-society.yml", "--status", "in_progress", "--limit", "20", "--json", "databaseId", "--jq", ".[].databaseId"],
    capture_output=True, text=True, check=True,
)
for run_id in listing.stdout.split():
    subprocess.run(["gh", "run", "cancel", run_id, "--repo", repo], check=False)
time.sleep(5)
subprocess.run(["gh", "workflow", "run", "sarah-society.yml", "--repo", repo, "--ref", "main", "-f", "entity=auto"], check=True)
print("live-event coherence repair applied and fresh Room dispatched")
