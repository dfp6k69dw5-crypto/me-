"""Production startup guards for the persistent Room world.

Two invariants live here because they must exist before the Room engine imports:
1. A configuration boot-id change must not silently erase an existing world.
2. Expression generation should get a fresh-seed retry when the same deterministic
   hygiene rules that protect publication would otherwise drop an agent entirely.

An explicitly destructive maintenance run can opt out of continuity protection with
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


def _install_expression_retry_guard() -> None:
    """Align generation with publication hygiene without weakening the final gate.

    The autonomy model already retries internally, but all of those attempts share the
    same cycle seed family. If the resulting candidate is still missing or would be
    quarantined by the deterministic publication hygiene classifier, make one more
    autonomy pass under a fresh cycle-key salt. This keeps invalid text out while
    preventing a single unlucky seed from turning a four-person beat into one speaker.
    """
    try:
        import room_private_model_autonomy as autonomy
        import room_research_architecture as research
    except Exception:
        return

    if hasattr(autonomy, "_startup_original_run"):
        return
    autonomy._startup_original_run = autonomy.run
    original_run = autonomy.run

    def _guarded_run(role: str, payload: dict, timeout: int = 30, min_words: int = 5):
        if role != "expression":
            return original_run(role, payload, timeout=timeout, min_words=min_words)

        entity = str((payload or {}).get("entity") or "").strip().lower()
        original_key = os.environ.get("ROOM_CYCLE_KEY")
        base_key = original_key or "room-cycle"
        try:
            for quality_pass in range(2):
                os.environ["ROOM_CYCLE_KEY"] = (
                    base_key if quality_pass == 0 else f"{base_key}:publish-retry-{quality_pass}"
                )
                result = original_run(
                    role,
                    payload,
                    timeout=min(int(timeout), 22),
                    min_words=max(4, int(min_words)),
                )
                if not isinstance(result, dict):
                    continue
                utterance = str(result.get("utterance") or "").strip()
                issue = research.autonomous_text_issue({"speaker": entity, "text": utterance})
                if issue:
                    print(
                        f"Expression pre-publication retry for {entity}: {issue}",
                        flush=True,
                    )
                    continue
                return result
            print(f"Expression exhausted pre-publication retries for {entity}", flush=True)
            return None
        finally:
            if original_key is None:
                os.environ.pop("ROOM_CYCLE_KEY", None)
            else:
                os.environ["ROOM_CYCLE_KEY"] = original_key

    autonomy.run = _guarded_run


_install_room_boot_guard()
_install_expression_retry_guard()
