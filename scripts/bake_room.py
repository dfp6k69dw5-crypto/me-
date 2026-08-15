from __future__ import annotations

import base64
from pathlib import Path

ROOM = Path("apps/sarah-room.html")
LIVE = Path("society/live.json")
TOKEN = "__ROOM_SNAPSHOT_B64__"

html = ROOM.read_text(encoding="utf-8")
if TOKEN not in html:
    raise SystemExit(f"missing bake token {TOKEN} in {ROOM}")

snapshot = LIVE.read_bytes()
encoded = base64.b64encode(snapshot).decode("ascii")
ROOM.write_text(html.replace(TOKEN, encoded), encoding="utf-8")
print(f"Baked {len(snapshot)} bytes of society state into {ROOM}")
