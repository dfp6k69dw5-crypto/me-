#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path

from room_prompt_guard import prompt_leak_reason

ROOT = Path(__file__).resolve().parents[1]

# Let the node think normally. The guard sits outside the model and sanitizes the
# artifact before the node is allowed to participate in the 2-of-3 vote.
proc = subprocess.run([sys.executable, str(ROOT / "scripts/society_node.py")], cwd=ROOT)
if proc.returncode != 0:
    sys.exit(proc.returncode)

changed = False
for path in sorted((ROOT / "society_parts").glob("*.json")):
    try:
        obj = json.loads(path.read_text())
    except Exception:
        continue

    reason = prompt_leak_reason(obj.get("text", ""))
    emergency = obj.get("emergency_candidate") or {}
    emergency_reason = prompt_leak_reason(emergency.get("text", ""))

    if reason:
        obj["speak"] = False
        obj["text"] = ""
        obj["topics"] = []
        obj["memory_note"] = ""
        obj.pop("emergency_candidate", None)
        obj["prompt_leak_blocked"] = reason
        changed = True
    elif emergency_reason:
        obj.pop("emergency_candidate", None)
        obj["prompt_leak_emergency_blocked"] = emergency_reason
        changed = True

    if changed:
        path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")

print("Room node prompt guard: clean" if not changed else "Room node prompt guard: leak blocked")
