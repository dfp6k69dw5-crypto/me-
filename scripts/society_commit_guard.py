#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path

from room_prompt_guard import prompt_leak_reason

ROOT = Path(__file__).resolve().parents[1]
PARTS = ROOT / "society_parts"


def sanitize_parts():
    blocked = 0
    for path in sorted(PARTS.rglob("*.json")):
        try:
            obj = json.loads(path.read_text())
        except Exception:
            continue
        dirty = False
        reason = prompt_leak_reason(obj.get("text", ""))
        if reason:
            obj["speak"] = False
            obj["text"] = ""
            obj["topics"] = []
            obj["memory_note"] = ""
            obj.pop("emergency_candidate", None)
            obj["prompt_leak_blocked_at_commit"] = reason
            blocked += 1
            dirty = True
        emergency = obj.get("emergency_candidate") or {}
        emergency_reason = prompt_leak_reason(emergency.get("text", ""))
        if emergency_reason:
            obj.pop("emergency_candidate", None)
            obj["prompt_leak_emergency_blocked_at_commit"] = emergency_reason
            blocked += 1
            dirty = True
        if dirty:
            path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")
    return blocked


def scrub_persistent_state():
    conv_path = ROOT / "society/conversation.json"
    minds_path = ROOT / "society/minds.json"
    state_path = ROOT / "society/state.json"
    live_path = ROOT / "society/live.json"

    conversation = json.loads(conv_path.read_text()) if conv_path.exists() else []
    minds = json.loads(minds_path.read_text()) if minds_path.exists() else {"entities": {}}
    state = json.loads(state_path.read_text()) if state_path.exists() else {}

    removed_messages = []
    clean_conversation = []
    for msg in conversation:
        reason = prompt_leak_reason(msg.get("text", ""))
        if reason:
            removed_messages.append((msg, reason))
        else:
            clean_conversation.append(msg)

    removed_memory = 0
    contaminated_topics = {}
    for eid, entity in (minds.get("entities", {}) or {}).items():
        memory = entity.get("memory", []) or []
        clean_memory = []
        bad_topics = set()
        for item in memory:
            reason = prompt_leak_reason(item.get("text", ""))
            if reason:
                removed_memory += 1
                bad_topics.update(str(t).lower().strip() for t in (item.get("topics") or []) if str(t).strip())
            else:
                clean_memory.append(item)
        entity["memory"] = clean_memory
        if bad_topics:
            contaminated_topics[eid] = sorted(bad_topics)
            dev = entity.setdefault("development", {})
            for field in ("topic_weights", "topic_fatigue"):
                table = dev.get(field) or {}
                for topic in bad_topics:
                    table.pop(topic, None)
                dev[field] = table

    # Archives are historical display data too; prompt text must not remain there.
    archive_removed = 0
    archive_dir = ROOT / "society/archive"
    if archive_dir.exists():
        for path in archive_dir.glob("*.json"):
            try:
                rows = json.loads(path.read_text())
            except Exception:
                continue
            clean_rows = [row for row in rows if not prompt_leak_reason(row.get("text", ""))]
            archive_removed += len(rows) - len(clean_rows)
            if len(clean_rows) != len(rows):
                path.write_text(json.dumps(clean_rows, indent=2, ensure_ascii=False) + "\n")

    if removed_messages:
        state["messages"] = max(0, int(state.get("messages", len(conversation))) - len(removed_messages))
        state["last_speaker"] = clean_conversation[-1].get("speaker") if clean_conversation else None

    conv_path.write_text(json.dumps(clean_conversation, indent=2, ensure_ascii=False) + "\n")
    minds_path.write_text(json.dumps(minds, indent=2, ensure_ascii=False) + "\n")
    state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n")

    generated_at = state.get("last_run")
    live = {"generated_at": generated_at, "minds": minds, "state": state, "conversation": clean_conversation}
    live_path.write_text(json.dumps(live, indent=2, ensure_ascii=False) + "\n")

    return {
        "messages": len(removed_messages),
        "memories": removed_memory,
        "archives": archive_removed,
        "topics": contaminated_topics,
    }


blocked = sanitize_parts()
proc = subprocess.run([sys.executable, str(ROOT / "scripts/society_commit.py")], cwd=ROOT)
if proc.returncode != 0:
    sys.exit(proc.returncode)
result = scrub_persistent_state()
print(f"Room commit prompt guard: blocked_parts={blocked} scrubbed={json.dumps(result, ensure_ascii=False)}")
