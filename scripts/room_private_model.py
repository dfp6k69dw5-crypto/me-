from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

PROMPT_ENV = {
    "comprehension": "ROOM_PROMPT_PERCEPTION",
    "thought": "ROOM_PROMPT_DELIBERATION",
    "expression": "ROOM_PROMPT_EXPRESSION",
}
LEAK_MARKERS = (
    "system prompt", "developer message", "hidden prompt", "chain of thought",
    "internal instructions", "system instructions", "room_prompt_",
)


def enabled(role: str) -> bool:
    return bool(os.environ.get(PROMPT_ENV.get(role, ""), "").strip() and os.environ.get("ROOM_MODEL_CLI", "").strip() and os.environ.get("ROOM_MODEL_PATH", "").strip())


def _extract_json(text: str):
    text = str(text or "").strip()
    if text.startswith("{"):
        return json.loads(text)
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("model returned no JSON object")
    return json.loads(m.group(0))


def _looks_like_leak(text: str, role: str) -> bool:
    low = text.lower()
    if any(marker in low for marker in LEAK_MARKERS):
        return True
    secret = os.environ.get(PROMPT_ENV.get(role, ""), "").strip()
    if secret:
        chunks = [secret[i:i+48].lower() for i in range(0, max(0, len(secret)-47), 24)]
        if any(chunk and chunk in low for chunk in chunks):
            return True
    return False


def run(role: str, payload: dict, timeout: int = 20):
    """Optional local-model adapter. Prompt text is read only from runtime secrets."""
    if not enabled(role):
        return None
    prompt = os.environ[PROMPT_ENV[role]].strip()
    cli = Path(os.environ["ROOM_MODEL_CLI"])
    model = Path(os.environ["ROOM_MODEL_PATH"])
    if not cli.exists() or not model.exists():
        return None
    user_data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    combined = prompt + "\nINPUT_JSON\n" + user_data + "\nOUTPUT_JSON_ONLY\n"
    proc = subprocess.run(
        [str(cli), "-m", str(model), "-n", "220", "--temp", "0.35", "-p", combined],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        timeout=timeout,
        check=False,
        env={k: v for k, v in os.environ.items() if not k.startswith("ROOM_PROMPT_")},
    )
    if proc.returncode != 0:
        return None
    out = proc.stdout[-12000:]
    if _looks_like_leak(out, role):
        return None
    try:
        return _extract_json(out)
    except Exception:
        return None
