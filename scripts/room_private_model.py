from __future__ import annotations

import json
import os
import re
import urllib.request

LEAK_MARKERS = (
    "system prompt", "developer message", "hidden prompt", "chain of thought",
    "internal instructions", "system instructions", "room_prompt_",
)


def enabled(role: str) -> bool:
    return bool(os.environ.get("ROOM_NODE_PROMPT", "").strip() and os.environ.get("ROOM_MODEL_URL", "").strip())


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
    combined = prompt + "\nINPUT_JSON\n" + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\nOUTPUT_JSON_ONLY\n"
    body = json.dumps({"prompt": combined, "n_predict": 220, "temperature": 0.35, "cache_prompt": False}).encode()
    req = urllib.request.Request(os.environ["ROOM_MODEL_URL"], data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", "replace"))
    except Exception:
        return None
    out = str(data.get("content", ""))
    if not out or _looks_like_leak(out):
        return None
    try:
        return _extract_json(out)
    except Exception:
        return None
