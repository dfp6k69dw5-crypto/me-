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
    if not text:
        raise ValueError("model returned no JSON object")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    if start < 0:
        raise ValueError("model returned no JSON object")
    obj, _ = json.JSONDecoder().raw_decode(text[start:])
    return obj


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


def _public_message(message: object, text_limit: int) -> dict:
    if not isinstance(message, dict):
        return {"speaker": None, "text": str(message or "")[:text_limit], "target": None}
    cognition = message.get("cognition") if isinstance(message.get("cognition"), dict) else {}
    return {
        "speaker": message.get("speaker"),
        "text": str(message.get("text", ""))[:text_limit],
        "target": cognition.get("target"),
        "topic_episode": message.get("topic_episode") or cognition.get("topic_episode"),
    }


def _compact_payload(payload: dict, role: str) -> dict:
    out = dict(payload or {})
    if role == "comprehension":
        context_count, text_limit, event_limit = 4, 320, 420
    else:
        context_count, text_limit, event_limit = 6, 450, 520

    if "event" in out:
        out["event"] = _public_message(out.get("event"), event_limit)
    context = out.get("context")
    if isinstance(context, list):
        out["context"] = [_public_message(m, text_limit) for m in context[-context_count:]]

    profile = out.get("profile")
    if isinstance(profile, dict):
        traits = profile.get("traits", {}) if isinstance(profile.get("traits"), dict) else {}
        if role == "comprehension":
            traits = {k: traits.get(k) for k in ("social_sensitivity", "curiosity", "skepticism") if k in traits}
        out["profile"] = {"name": profile.get("name"), "traits": traits}

    topic = out.get("topic")
    if isinstance(topic, dict):
        if role == "comprehension":
            keep = ("id", "root", "current_facet", "facets", "status", "shared_references")
        else:
            keep = ("id", "root", "current_facet", "facets", "visited_facets", "status", "unresolved", "shared_references")
        out["topic"] = {k: topic.get(k) for k in keep if k in topic}

    keywords = out.get("keywords")
    if isinstance(keywords, list):
        out["keywords"] = keywords[:8 if role == "comprehension" else 12]
    return out


def _safe_http_detail(exc: urllib.error.HTTPError) -> str:
    detail = ""
    try:
        raw = exc.read().decode("utf-8", "replace")
        parsed = json.loads(raw)
        error = parsed.get("error") if isinstance(parsed, dict) else None
        if isinstance(error, dict):
            detail = str(error.get("message") or error.get("type") or "")
        elif error:
            detail = str(error)
        if not detail and isinstance(parsed, dict):
            detail = str(parsed.get("message") or "")
    except Exception:
        detail = ""
    for key in ("ROOM_NODE_PROMPT", "ROOM_PROMPT_PERCEPTION", "ROOM_PROMPT_DELIBERATION", "ROOM_PROMPT_EXPRESSION"):
        secret = os.environ.get(key, "")
        if secret:
            detail = detail.replace(secret, "[redacted]")
    detail = re.sub(r"\s+", " ", detail).strip()
    return detail[:240]


def run(role: str, payload: dict, timeout: int = 30):
    """Private local-model adapter. Prompted live nodes fail closed; no canned fallback."""
    prompt = os.environ.get("ROOM_NODE_PROMPT", "").strip()
    if not prompt:
        return None

    model_url = os.environ.get("ROOM_MODEL_URL", "").strip()
    if not model_url:
        raise RuntimeError(f"private model unavailable for {role}")

    compact = _compact_payload(payload, role)
    combined = (
        prompt
        + "\nINPUT_JSON\n"
        + json.dumps(compact, ensure_ascii=False, separators=(",", ":"))
        + "\nOUTPUT_JSON_ONLY\n"
    )
    n_predict = {"comprehension": 96, "thought": 144, "expression": 220}.get(role, 160)
    temperature = {"comprehension": 0.15, "thought": 0.25, "expression": 0.35}.get(role, 0.25)
    request_body = {
        "prompt": combined,
        "n_predict": n_predict,
        "temperature": temperature,
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
        detail = _safe_http_detail(exc)
        suffix = f": {detail}" if detail else ""
        raise RuntimeError(f"private model request failed for {role}: HTTP {exc.code}{suffix}") from exc
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
