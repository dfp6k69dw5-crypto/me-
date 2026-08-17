#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOM = ROOT / "room"
live = json.loads((ROOM / "live.json").read_text())
entities = {}
for entity_id, mind in (live.get("minds", {}).get("entities", {}) or {}).items():
    entities[entity_id] = {
        "name": mind.get("name", entity_id),
        "genome": mind.get("genome", {}),
        "development": mind.get("development", {}),
        "memory": mind.get("memory", [])[-12:],
    }
conversation = [{
    "id": m.get("id"), "speaker": m.get("speaker"), "text": m.get("text"),
    "at": m.get("at"), "beat_id": m.get("beat_id")
} for m in (live.get("conversation", []) or [])[-160:]]
feed = {
    "generated_at": live.get("generated_at"), "state": live.get("state", {}),
    "minds": {"entities": entities}, "conversation": conversation,
}
(ROOM / "feed.json").write_text(json.dumps(feed, ensure_ascii=False, separators=(",", ":")) + "\n")
