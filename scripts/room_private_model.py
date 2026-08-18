from __future__ import annotations

import json
import os
import re
import urllib.error
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


def _nullable_string():
    return {"anyOf": [{"type": "string"}, {"type": "null"}]}


def _schema(role: str) -> dict:
    people = ["sarah", "mara", "owen", "jules"]
    if role == "comprehension":
        return {
            "type": "object",
            "properties": {
                "participation": {"type": "string", "enum": ["DIRECT_ADDRESSEE", "PARTICIPANT", "OVERHEARER"]},
                "partner": {"anyOf": [{"type": "string", "enum": people}, {"type": "null"}]},
                "relationship_events": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["participation", "partner", "relationship_events"],
        }
    if role == "thought":
        return {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["ANSWER", "DEEPEN", "DISCLOSE", "COMPARE", "DISAGREE", "REPAIR", "SUPPORT", "CALLBACK", "BRIDGE", "CLOSE_TOPIC"]},
                "preferred_partner": {"type": "string", "enum": people},
                "mandatory_speech": {"type": "boolean"},
            },
            "required": ["action", "preferred_partner", "mandatory_speech"],
        }
    if role == "expression":
        return {
            "type": "object",
            "properties": {
                "decision": {"type": "string", "enum": ["SPEAK"]},
                "target": {"type": "string", "enum": people},
                "utterance": {"type": "string"},
                "topic_terms": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["decision", "target", "utterance", "topic_terms"],
        }
    raise ValueError(f"unknown private model role: {role}")


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


def _completion_url(model_url: str) -> str:
    base = model_url.rstrip("/")
    return base if base.endswith("/completion") else base + "/completion"


def run(role: str, payload: dict, timeout: int = 30):
    """Private local-model adapter. Prompted live nodes fail closed; no canned fallback."""
    prompt = os.environ.get("ROOM_NODE_PROMPT", "").strip()
    if not prompt:
        return None

    model_url = os.environ.get("ROOM_MODEL_URL", "").strip()
    if not model_url:
        raise RuntimeError(f"private model unavailable for {role}")

    combined = (
        prompt
        + "\nINPUT_JSON\n"
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        + "\nOUTPUT_JSON_ONLY\n"
    )
    request_body = {
        "prompt": combined,
        "n_predict": 320,
        "temperature": 0.25,
        "cache_prompt": False,
        "json_schema": _schema(role),
    }
    body = json.dumps(request_body, ensure_ascii=False).encode()
    req = urllib.request.Request(
        _completion_url(model_url),
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"private model request failed for {role}: HTTP {exc.code}") from exc
    except Exception as exc:
        raise RuntimeError(f"private model request failed for {role}: {type(exc).__name__}") from exc

    out = str(data.get("content", ""))
    if not out:
        raise RuntimeError(f"private model returned empty output for {role}")
    if _looks_like_leak(out):
        raise RuntimeError(f"private model output failed privacy filter for {role}")

    try:
        return _validate(role, _extract_json(out))
    except Exception as exc:
        raise RuntimeError(f"private model output rejected for {role}: {type(exc).__name__}") from exc
