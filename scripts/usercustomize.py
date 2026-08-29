"""Protect the persistent Room world from accidental boot-id resets.

Python imports ``usercustomize`` during interpreter startup after ``sitecustomize``.
The Room core historically treated any config ``boot_id`` change as permission to
wipe conversation, discourse, cognition, and state.  For an existing world, the
persisted state now owns the world identity.  A changed config may still change
personality and behavior fields, but it cannot silently become a destructive reset.

An explicitly destructive maintenance run can opt out with
``ROOM_ALLOW_DESTRUCTIVE_BOOT_RESET=1``.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

_ORIGINAL_READ_TEXT = Path.read_text
_ROOT = Path(__file__).resolve().parents[1]
_CONFIG = (_ROOT / "room" / "config.json").resolve()
_STATE = _ROOT / "room" / "state.json"


def _json_file(path: Path) -> dict:
    try:
        value = json.loads(_ORIGINAL_READ_TEXT(path))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _install_room_boot_guard() -> None:
    if os.environ.get("ROOM_ALLOW_DESTRUCTIVE_BOOT_RESET", "").strip() == "1":
        return
    if not _CONFIG.exists() or not _STATE.exists():
        return

    persisted = _json_file(_STATE)
    configured = _json_file(_CONFIG)
    persisted_boot = str(persisted.get("boot_id") or "").strip()
    configured_boot = str(configured.get("boot_id") or "").strip()
    if not persisted_boot or not configured_boot or persisted_boot == configured_boot:
        return

    protected = dict(configured)
    protected["boot_id"] = persisted_boot
    protected["requested_boot_id"] = configured_boot
    encoded = json.dumps(protected, ensure_ascii=False)

    def _continuity_read_text(path: Path, *args, **kwargs):
        try:
            if path.resolve() == _CONFIG:
                return encoded
        except Exception:
            pass
        return _ORIGINAL_READ_TEXT(path, *args, **kwargs)

    Path.read_text = _continuity_read_text
    print(
        "ROOM_BOOT_CONTINUITY_GUARD "
        f"preserved={persisted_boot} ignored_destructive_config_boot={configured_boot}",
        flush=True,
    )


_install_room_boot_guard()
