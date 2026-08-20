#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIEWER = (ROOT / "room" / "index.html").read_text()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    require("semantic-epoch-v1/conversation.json" in VIEWER,
            "viewer does not load the pre-reset semantic archive")
    require("archiveHistoryData" in VIEWER,
            "viewer has no separate archive history buffer")
    require("[archiveHistoryData,historyData,liveData?.conversation||[]]" in VIEWER.replace(" ", ""),
            "viewer does not merge archive before active/live history")
    require("seen.has(m.id)" in VIEWER,
            "viewer history merge does not deduplicate message IDs")
    print("ROOM VIEWER HISTORY SIM: GREEN")


if __name__ == "__main__":
    main()
