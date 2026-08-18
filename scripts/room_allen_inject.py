#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import room_engine_v5 as c


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text()) if path.exists() else default
    except Exception:
        return default


def normalize_time(value: str | None) -> str:
    text = str(value or "").strip()
    if text:
        return text
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def infer_target(text: str):
    low = str(text or "").lower()[:180]
    for entity in c.ORDER:
        name = str(c.N.get(entity, entity)).lower()
        if re.search(rf"\b{re.escape(name)}\b", low):
            return entity
    return None


def topic_terms(text: str, topic: dict) -> list[str]:
    out: list[str] = []
    for value in (topic.get("root"), topic.get("current_facet")):
        value = str(value or "").strip().lower()
        if value and value not in out:
            out.append(value)
    for value in c.toks(text):
        value = str(value or "").strip().lower()
        if value and value not in out:
            out.append(value)
    return out[:6]


def inject(inbox_path: Path, ack_path: Path) -> int:
    payload = load_json(inbox_path, {})
    pending = payload.get("messages", []) if isinstance(payload, dict) else payload
    if not isinstance(pending, list):
        pending = []

    V = c.conv()
    T = c.tree()
    M = c.minds()
    S = c.state()
    topic = dict(S.get("topic_episode") or {})
    cycle = int(S.get("cycle", 0))

    seen = {
        str(((message.get("cognition") or {}).get("external_id") or "")).strip()
        for message in V
        if str(((message.get("cognition") or {}).get("external_id") or "")).strip()
    }
    ack_ids: list[str] = []
    injected = 0

    for item in pending:
        if not isinstance(item, dict):
            continue
        external_id = str(item.get("id") or "").strip()
        text = str(item.get("text") or "").strip()
        if not external_id or not text or len(text) > 700:
            continue
        if external_id not in ack_ids:
            ack_ids.append(external_id)
        if external_id in seen:
            continue

        safe_id = re.sub(r"[^a-zA-Z0-9_-]+", "-", external_id).strip("-")[:64] or "turn"
        message_id = f"allen-{safe_id}"
        discourse_id = "d-" + message_id
        parent = V[-1].get("discourse_id") if V else None
        target = infer_target(text)
        terms = topic_terms(text, topic)
        beat_id = f"allen-{safe_id}"
        at = normalize_time(item.get("submittedAt"))

        cognition = {
            "move_type": "contribute",
            "target": target,
            "compute_nodes": [],
            "processes": 0,
            "beat_id": beat_id,
            "beat_index": -1,
            "topic_episode": topic.get("id"),
            "topic_root": topic.get("root"),
            "topic_facet": topic.get("current_facet"),
            "topic_terms": terms,
            "mandatory_speech": False,
            "external_id": external_id,
        }
        message = {
            "id": message_id,
            "at": at,
            "speaker": "Allen",
            "text": text,
            "runtime": "room-cognition-v5-participant",
            "boot_id": c.BOOT,
            "beat_id": beat_id,
            "beat_index": -1,
            "cognition": cognition,
            "discourse_id": discourse_id,
            "parent_discourse_id": parent,
            "derived_from": None,
        }
        node = {
            "id": discourse_id,
            "speaker": "Allen",
            "parent": parent,
            "derived_from": None,
            "move": "contribute",
            "target": target,
            "text": text,
            "at": at,
            "beat_id": beat_id,
            "beat_index": -1,
            "topic_episode": topic.get("id"),
            "topic_facet": topic.get("current_facet"),
            "topic_terms": terms,
        }

        V.append(message)
        T.setdefault("nodes", []).append(node)
        if not parent:
            T.setdefault("roots", []).append(discourse_id)

        for listener in c.ORDER:
            memories = M["entities"][listener].setdefault("room_memories", [])
            memories.append({
                "source": message_id,
                "status": "observed",
                "speaker": "Allen",
                "text": text[:300],
                "discourse": discourse_id,
                "beat_id": beat_id,
                "topic_episode": topic.get("id"),
            })
            M["entities"][listener]["room_memories"] = memories[-220:]
            M["entities"][listener]["last_event"] = message_id

        participants = topic.setdefault("participants", list(c.ORDER))
        if "allen" not in participants:
            participants.append("allen")
        topic = c.update_topic(topic, [message], cycle)
        seen.add(external_id)
        injected += 1

    if injected:
        T["nodes"] = T.get("nodes", [])[-1200:]
        T["roots"] = T.get("roots", [])[-300:]
        V = V[-1000:]
        S["topic_episode"] = topic
        S["messages"] = len(V)
        S["last_public_event"] = V[-1]["id"]
        S["last_speaker"] = "Allen"
        S["last_beat_id"] = V[-1]["beat_id"]
        S["beat_contributors"] = ["allen"]
        S["beat_message_count"] = 1
        S["last_participant_input"] = V[-1]["at"]
        c.save(c.ROOM / "conversation.json", V)
        c.save(c.ROOM / "discourse.json", T)
        c.save(c.ROOM / "cognitive_state.json", M)
        c.save(c.ROOM / "state.json", S)

    ack_path.parent.mkdir(parents=True, exist_ok=True)
    ack_path.write_text(json.dumps({"ids": ack_ids}, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(f"Allen inbox: {len(pending)} pending, {injected} injected, {len(ack_ids)} ackable")
    return injected


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("inbox", nargs="?", default="room_work/allen-inbox.json")
    parser.add_argument("--ack", default="room_work/allen-ack.json")
    args = parser.parse_args()
    inject(Path(args.inbox), Path(args.ack))


if __name__ == "__main__":
    main()
