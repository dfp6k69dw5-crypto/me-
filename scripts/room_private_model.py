from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

LEAK_MARKERS = (
    "system prompt", "developer message", "hidden prompt", "chain of thought",
    "internal instructions", "system instructions", "room_prompt_",
)


def enabled(role: str) -> bool:
    return bool(os.environ.get("ROOM_NODE_PROMPT", "").strip() and os.environ.get("ROOM_MODEL_CLI", "").strip() and os.environ.get("ROOM_MODEL_PATH", "").strip())


def _extract_json(text: str):
    text = str(text or "").strip()
    if text.startswith("{"):
        return json.loads(text)
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("model returned no JSON object")
    return json.loads(m.group(0))


def _looks_like_leak(text: str) -> bool:
    low = text.lower()
    if any(marker in low for marker in LEAK_MARKERS):
        return True
    secret = os.environ.get("ROOM_NODE_PROMPT", "").strip()
    if secret:
        chunks = [secret[i:i+48].lower() for i in range(0, max(0, len(secret)-47), 24)]
        if any(chunk and chunk in low for chunk in chunks):
            return True
    return False


def run(role: str, payload: dict, timeout: int = 20):
    """Optional local-model adapter. Each node receives only its own runtime prompt."""
    if not enabled(role):
        return None
    prompt = os.environ["ROOM_NODE_PROMPT"].strip()
    cli = Path(os.environ["ROOM_MODEL_CLI"])
    model = Path(os.environ["ROOM_MODEL_PATH"])
    if not cli.exists() or not model.exists():
        return None
    user_data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    combined = prompt + "\nINPUT_JSON\n" + user_data + "\nOUTPUT_JSON_ONLY\n"
    child_env = {k: v for k, v in os.environ.items() if k != "ROOM_NODE_PROMPT" and not k.startswith("ROOM_PROMPT_")}
    proc = subprocess.run(
        [str(cli), "-m", str(model), "-n", "220", "--temp", "0.35", "-p", combined],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        timeout=timeout,
        check=False,
        env=child_env,
    )
    if proc.returncode != 0:
        return None
    out = proc.stdout[-12000:]
    if _looks_like_leak(out):
        return None
    try:
        return _extract_json(out)
    except Exception:
        return None
