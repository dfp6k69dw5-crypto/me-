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


def _validate(role: str, obj: object) -> dict:
    if not isinstance(obj, dict):
        raise ValueError("model output was not a JSON object")

    if role == "expression":
        if str(obj.get("decision", "")).upper() != "SPEAK":
            raise ValueError("expression did not satisfy mandatory speech")
        utterance = obj.get("utterance")
        if not isinstance(utterance, str) or not utterance.strip():
            raise ValueError("expression returned no utterance")
        if len(utterance.strip()) > 700:
            raise ValueError("expression utterance exceeded length limit")
        if _looks_like_leak(utterance):
            raise ValueError("expression failed privacy filter")
        if not isinstance(obj.get("topic_terms"), list):
            raise ValueError("expression returned no semantic topic terms")

    elif role == "thought":
        if not isinstance(obj.get("action"), str):
            raise ValueError("deliberation returned no action")
        if obj.get("mandatory_speech") is not True:
            raise ValueError("deliberation did not preserve mandatory speech")

    elif role == "comprehension":
        if not isinstance(obj.get("participation"), str):
            raise ValueError("perception returned no participation state")
        if not isinstance(obj.get("relationship_events"), list):
            raise ValueError("perception returned invalid relationship events")

    return obj


def run(role: str, payload: dict, timeout: int = 20):
    """Private local-model adapter. Prompted live nodes fail closed; no canned fallback."""
    prompt = os.environ.get("ROOM_NODE_PROMPT", "").strip()
    if not prompt:
        # Offline tests and unprompted nodes may continue without the local model.
        return None

    model_url = os.environ.get("ROOM_MODEL_URL", "").strip()
    if not model_url:
        raise RuntimeError(f"private model unavailable for {role}")

    combined = prompt + "\nINPUT_JSON\n" + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\nOUTPUT_JSON_ONLY\n"
    body = json.dumps({"prompt": combined, "n_predict": 220, "temperature": 0.35, "cache_prompt": False}).encode()
    req = urllib.request.Request(model_url, data=body, headers={"Content-Type": "application/json"}, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", "replace"))
    except Exception as exc:
        raise RuntimeError(f"private model request failed for {role}: {type(exc).__name__}") from exc

    out = str(data.get("content", ""))
    if not out:
        raise RuntimeError(f"private model returned empty output for {role}")
    if _looks_like_leak(out):
        raise RuntimeError(f"private model output failed privacy filter for {role}")

    try:
        obj = _extract_json(out)
        return _validate(role, obj)
    except Exception as exc:
        raise RuntimeError(f"private model output rejected for {role}: {type(exc).__name__}") from exc
