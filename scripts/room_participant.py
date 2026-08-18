#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import room_engine_v5 as c

TARGETS = ("sarah", "mara", "owen", "jules")
PARTICIPANT = "allen"
MAX_TEXT = 700


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def parse_time(value: str) -> datetime:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def infer_target(text: str):
    low = str(text or "").strip().lower()
    for target in TARGETS:
        if re.match(rf"^@?{re.escape(target)}\b", low):
            return target
    return None


def clean_terms(text: str, topic: dict):
    terms = c.toks(text)[:4]
    if not terms:
        for value in (topic.get("current_facet"), topic.get("root")):
            value = str(value or "").strip().lower()
            if value and value not in terms:
                terms.append(value)
    return terms[:4]


def inject(item: dict, history: list, discourse: dict, state: dict):
    source_id = str(item.get("id") or "").strip()
    text = re.sub(r"\s+", " ", str(item.get("text") or "").strip())[:MAX_TEXT]
    if not source_id or not text:
        return None

    digest = hashlib.sha256(source_id.encode()).hexdigest()[:10]
    at = parse_time(item.get("at") or "")
    message_id = f"{at.strftime('%Y%m%dT%H%M%S%f')[:-3]}-{PARTICIPANT}-v5-{digest}"
    if any(message.get("id") == message_id for message in history):
        return source_id

    topic = state.get("topic_episode") or {}
    cycle = int(state.get("cycle", 0)) + 1
    beat = f"beat-{c.BOOT}-{cycle:06d}"
    target = infer_target(text)
    terms = clean_terms(text, topic)
    parent = history[-1].get("discourse_id") if history else None
    move = "follow_up" if text.rstrip().endswith("?") else "deepen"
    discourse_id = "d-" + message_id
    stamp = at.isoformat().replace("+00:00", "Z")

    # Allen is deliberately represented in the same public conversational shape
    # as the Room speakers. There is no human/operator flag in the context the
    # entities receive.
    cognition = {
        "move_type": move,
        "target": target,
        "compute_nodes": [13, 14, 15],
        "processes": 12,
        "beat_id": beat,
        "beat_index": -1,
        "topic_episode": topic.get("id"),
        "topic_root": topic.get("root"),
        "topic_facet": topic.get("current_facet"),
        "topic_terms": terms,
        "mandatory_speech": True,
    }
    message = {
        "id": message_id,
        "at": stamp,
        "speaker": PARTICIPANT,
        "text": text,
        "runtime": c.VERSION,
        "boot_id": c.BOOT,
        "beat_id": beat,
        "beat_index": -1,
        "cognition": cognition,
        "discourse_id": discourse_id,
        "parent_discourse_id": parent,
        "derived_from": None,
    }
    node = {
        "id": discourse_id,
        "speaker": PARTICIPANT,
        "parent": parent,
        "derived_from": None,
        "move": move,
        "target": target,
        "text": text,
        "at": stamp,
        "beat_id": beat,
        "beat_index": -1,
        "topic_episode": topic.get("id"),
        "topic_facet": topic.get("current_facet"),
        "topic_terms": terms,
    }
    history.append(message)
    discourse.setdefault("nodes", []).append(node)
    if not parent:
        discourse.setdefault("roots", []).append(discourse_id)
    return source_id


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: room_participant.py INBOX_JSON ACK_JSON")

    inbox_path = Path(sys.argv[1])
    ack_path = Path(sys.argv[2])
    inbox = load_json(inbox_path, {"messages": []})
    pending = inbox.get("messages") if isinstance(inbox, dict) else []
    if not isinstance(pending, list):
        pending = []

    history = c.conv()
    discourse = c.tree()
    state = c.state()
    ack_ids = []
    for item in pending[:20]:
        if not isinstance(item, dict):
            continue
        source_id = inject(item, history, discourse, state)
        if source_id:
            ack_ids.append(source_id)

    if ack_ids:
        c.save(c.ROOM / "conversation.json", history[-1000:])
        discourse["nodes"] = discourse.get("nodes", [])[-1200:]
        discourse["roots"] = discourse.get("roots", [])[-300:]
        c.save(c.ROOM / "discourse.json", discourse)
        print(f"Injected {len(ack_ids)} Allen turn(s) into the Room context")

    ack_path.parent.mkdir(parents=True, exist_ok=True)
    ack_path.write_text(json.dumps({"ids": ack_ids}, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
