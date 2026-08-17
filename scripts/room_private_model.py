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


def _nullable_string():
    return {"anyOf": [{"type": "string"}, {"type": "null"}]}


def _schema(role: str) -> dict:
    people = ["sarah", "mara", "owen", "jules"]
    if role == "comprehension":
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "participation": {"type": "string", "enum": ["DIRECT_ADDRESSEE", "PARTICIPANT", "OVERHEARER"]},
                "partner": {"anyOf": [{"type": "string", "enum": people}, {"type": "null"}]},
                "move": {"type": "string", "enum": ["answer", "disclosure", "question", "disagreement", "support", "joke", "clarification", "repair", "repair_attempt", "topic_deepening", "topic_bridge", "topic_closing", "other"]},
                "grounding": {"type": "string", "enum": ["understood", "apparently_understood", "ambiguous", "contradicted", "misunderstood", "repair_needed"]},
                "topic_facet": _nullable_string(),
                "new_details": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
                "bids": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
                "relationship_events": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
                "shared_references": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            },
            "required": ["participation", "partner", "move", "grounding", "topic_facet", "new_details", "bids", "relationship_events", "shared_references", "confidence"],
        }
    if role == "thought":
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "action": {"type": "string", "enum": ["ANSWER", "DEEPEN", "DISCLOSE", "COMPARE", "DISAGREE", "REPAIR", "SUPPORT", "CALLBACK", "BRIDGE", "CLOSE_TOPIC"]},
                "preferred_partner": {"type": "string", "enum": people},
                "topic_facet": {"type": "string"},
                "new_information_goal": {"type": "string"},
                "disclosure_depth": {"type": "integer", "minimum": 0, "maximum": 4},
                "interpersonal_risk": {"type": "integer", "minimum": 0, "maximum": 4},
                "shared_reference": _nullable_string(),
                "unresolved_thread": _nullable_string(),
                "reason_summary": {"type": "string", "maxLength": 180},
                "mandatory_speech": {"type": "boolean", "const": True},
            },
            "required": ["action", "preferred_partner", "topic_facet", "new_information_goal", "disclosure_depth", "interpersonal_risk", "shared_reference", "unresolved_thread", "reason_summary", "mandatory_speech"],
        }
    if role == "expression":
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "decision": {"type": "string", "const": "SPEAK"},
                "target": {"type": "string", "enum": people},
                "move": {"type": "string", "enum": ["answer", "deepen", "disclose", "compare", "disagree", "repair", "support", "callback", "bridge", "close_topic"]},
                "utterance": {"type": "string", "minLength": 1, "maxLength": 700},
                "topic_terms": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 4},
            },
            "required": ["decision", "target", "move", "utterance", "topic_terms"],
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


def _chat_url(model_url: str) -> str:
    base = model_url.rstrip("/")
    if base.endswith("/completion"):
        base = base[: -len("/completion")]
    return base + "/v1/chat/completions"


def run(role: str, payload: dict, timeout: int = 30):
    """Private local-model adapter. Prompted live nodes fail closed; no canned fallback."""
    prompt = os.environ.get("ROOM_NODE_PROMPT", "").strip()
    if not prompt:
        # Offline tests and unprompted nodes may continue without the local model.
        return None

    model_url = os.environ.get("ROOM_MODEL_URL", "").strip()
    if not model_url:
        raise RuntimeError(f"private model unavailable for {role}")

    schema = _schema(role)
    user_input = "INPUT_JSON\n" + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\nOUTPUT_JSON_ONLY"
    request_body = {
        "model": "local",
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_input},
        ],
        "temperature": 0.25,
        "max_tokens": 320,
        "response_format": {"type": "json_object", "schema": schema},
    }
    body = json.dumps(request_body, ensure_ascii=False).encode()
    req = urllib.request.Request(_chat_url(model_url), data=body, headers={"Content-Type": "application/json"}, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", "replace"))
    except Exception as exc:
        raise RuntimeError(f"private model request failed for {role}: {type(exc).__name__}") from exc

    try:
        out = str(data["choices"][0]["message"]["content"])
    except Exception as exc:
        raise RuntimeError(f"private model returned unexpected response for {role}") from exc

    if not out:
        raise RuntimeError(f"private model returned empty output for {role}")
    if _looks_like_leak(out):
        raise RuntimeError(f"private model output failed privacy filter for {role}")

    try:
        obj = _extract_json(out)
        return _validate(role, obj)
    except Exception as exc:
        raise RuntimeError(f"private model output rejected for {role}: {type(exc).__name__}") from exc
