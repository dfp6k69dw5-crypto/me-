from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request

PEOPLE = ["sarah", "mara", "owen", "jules"]
LEAK_MARKERS = (
    "system prompt", "developer message", "hidden prompt", "chain of thought",
    "internal instructions", "system instructions", "room_prompt_",
)

# These are infection signatures, not text that is ever appended to a model prompt.
META_PATTERNS = (
    r"\btopic[-_ ]?\d{3,}\b",
    r"\btopic\s+(?:root|facet|episode|identifier|id|schema)\b",
    r"\bcurrent\s+(?:narrow\s+)?topic\b",
    r"\bnarrow\s+topic\s+facet\b",
    r"\bsemantic\s+schema\b",
    r"\b(?:input|output)[-_ ]?json\b",
    r"\bmandatory\s+speech\b",
    r"\b(?:should|allowed|required)\s+(?:i\s+)?(?:be\s+)?speaking\b",
    r"\bnot\s+sure\s+if\s+i\s+should\s+be\s+speaking\b",
    r"\b(?:exploring|closing|closure)\s+topic\b",
    r"\btopic\s+(?:closure|closing)\b",
    r"\b[a-z-]+-related\s+topic\b",
    r"\b[a-z -]+\s+topic\b$",
)
OLD_FRAME_PATTERNS = (
    r"^the new piece for me is\b",
    r"^the use of .+ is a useful distinction for the speaker[.!]?$",
    r"^i'd separate the pattern around\b",
    r"^what interests me in\b",
    r"^the part of .+ i keep coming back to\b",
    r"^i don't think .+ stands alone\b",
    r"^the piece of .+ that feels real to me\b",
    r"^i hear .+ leaning on\b",
    r"^the useful distinction for me is\b",
    r"^i'd test .+ against\b",
    r"^what did somebody do—not just say—\b",
    r"^for me, .+ gets concrete\b",
    r"^i'm connecting this with\b",
    r"^if .+ has a clean story\b",
    r"^the weird edge of\b",
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


def _norm(text: object) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _contains_explicit_leak_marker(text: str) -> bool:
    low = _norm(text)
    return any(marker in low for marker in LEAK_MARKERS)


def _contains_meta_language(text: object) -> bool:
    low = _norm(text)
    return any(re.search(pattern, low) for pattern in META_PATTERNS)


def _looks_like_template_echo(text: str) -> bool:
    low = _norm(text)
    return any(re.search(pattern, low) for pattern in OLD_FRAME_PATTERNS)


def _looks_like_public_leak(text: str) -> bool:
    low = _norm(text)
    if _contains_explicit_leak_marker(low) or _contains_meta_language(low):
        return True
    secret = _decontaminate_instruction(os.environ.get("ROOM_NODE_PROMPT", ""))
    if secret:
        chunks = [secret[i:i+56].lower() for i in range(0, max(0, len(secret)-55), 28)]
        if any(chunk and chunk in low for chunk in chunks):
            return True
    return False


def _decontaminate_instruction(prompt: str) -> str:
    """Remove known scaffold carriers from the runtime copy without changing the stored secret."""
    text = str(prompt or "")
    substitutions = (
        (r"(?i)the natural public conversational turn", "an ordinary spoken reply"),
        (r"(?i)natural public conversational turn", "ordinary spoken reply"),
        (r"(?i)current narrow topic facet", "specific subject detail"),
        (r"(?i)current narrow facet", "specific subject detail"),
        (r"(?i)current topic facet", "specific subject detail"),
        (r"(?i)current topic root", "main subject"),
        (r"(?i)topic root", "main subject"),
        (r"(?i)topic facet", "specific subject detail"),
        (r"(?i)topic episode", "ongoing discussion"),
    )
    for pattern, replacement in substitutions:
        text = re.sub(pattern, replacement, text)
    return text


def _nullable_string() -> dict:
    return {"anyOf": [{"type": "string"}, {"type": "null"}]}


def _nullable_person() -> dict:
    return {"anyOf": [{"type": "string", "enum": PEOPLE}, {"type": "null"}]}


def _string_array(max_items: int = 8) -> dict:
    return {"type": "array", "items": {"type": "string"}, "maxItems": max_items}


def _schema(role: str) -> dict:
    if role == "comprehension":
        properties = {
            "participation": {"type": "string", "enum": ["DIRECT_ADDRESSEE", "PARTICIPANT", "OVERHEARER"]},
            "partner": _nullable_person(),
            "move": {"type": "string", "enum": ["answer", "disclosure", "question", "disagreement", "support", "joke", "clarification", "repair", "repair_attempt", "topic_deepening", "topic_bridge", "topic_closing", "other"]},
            "grounding": {"type": "string", "enum": ["understood", "apparently_understood", "ambiguous", "contradicted", "misunderstood", "repair_needed"]},
            "topic_facet": _nullable_string(),
            "new_details": _string_array(6),
            "bids": _string_array(5),
            "relationship_events": _string_array(6),
            "shared_references": _string_array(5),
            "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        }
        return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}
    if role == "thought":
        properties = {
            "action": {"type": "string", "enum": ["ANSWER", "DEEPEN", "DISCLOSE", "COMPARE", "DISAGREE", "REPAIR", "SUPPORT", "CALLBACK", "BRIDGE", "CLOSE_TOPIC"]},
            "preferred_partner": {"type": "string", "enum": PEOPLE},
            "topic_facet": {"type": "string"},
            "new_information_goal": {"type": "string", "maxLength": 240},
            "disclosure_depth": {"type": "integer", "minimum": 0, "maximum": 4},
            "interpersonal_risk": {"type": "integer", "minimum": 0, "maximum": 4},
            "shared_reference": _nullable_string(),
            "unresolved_thread": _nullable_string(),
            "reason_summary": {"type": "string", "maxLength": 180},
            "mandatory_speech": {"type": "boolean", "enum": [True]},
        }
        return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}
    if role == "expression":
        properties = {
            "decision": {"type": "string", "enum": ["SPEAK"]},
            "target": {"type": "string", "enum": PEOPLE},
            "move": {"type": "string", "enum": ["answer", "deepen", "disclose", "compare", "disagree", "repair", "support", "callback", "bridge", "close_topic"]},
            "utterance": {"type": "string", "minLength": 1, "maxLength": 700},
            "topic_terms": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 4},
        }
        return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}
    raise ValueError(f"unknown private model role: {role}")


def _bad_term(value: object) -> bool:
    s = _norm(value)
    if not s or len(s) > 80:
        return True
    if _contains_meta_language(s) or _contains_explicit_leak_marker(s):
        return True
    if re.fullmatch(r"topic[-_ ]?\d+", s):
        return True
    if s in {"topic", "conversation", "discussion", "subject", "facet", "root", "schema", "context"}:
        return True
    if s.endswith(" topic") or s.startswith("topic "):
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
        if _looks_like_public_leak(utterance) or _looks_like_template_echo(utterance):
            raise ValueError("expression failed contamination filter")
        if not isinstance(obj.get("topic_terms"), list):
            raise ValueError("expression returned no semantic terms")
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
    }


def _safe_semantic_list(values: object, limit: int) -> list[str]:
    out: list[str] = []
    if not isinstance(values, list):
        return out
    for value in values:
        s = _norm(value)
        if _bad_term(s) or s in out:
            continue
        out.append(s)
        if len(out) >= limit:
            break
    return out


def _compact_payload(payload: dict, role: str) -> dict:
    out = dict(payload or {})
    if role == "comprehension":
        context_count, text_limit, event_limit = 4, 320, 420
    else:
        context_count, text_limit, event_limit = 5, 420, 500

    if "event" in out:
        event = _public_message(out.get("event"), event_limit)
        out["event"] = None if _contains_meta_language(event.get("text")) else event

    context = out.get("context")
    if isinstance(context, list):
        cleaned = []
        for message in context[-context_count:]:
            public = _public_message(message, text_limit)
            if _contains_meta_language(public.get("text")) or _looks_like_template_echo(public.get("text", "")):
                continue
            cleaned.append(public)
        out["context"] = cleaned[-context_count:]

    profile = out.get("profile")
    if isinstance(profile, dict):
        traits = profile.get("traits", {}) if isinstance(profile.get("traits"), dict) else {}
        if role == "comprehension":
            traits = {k: traits.get(k) for k in ("social_sensitivity", "curiosity", "skepticism") if k in traits}
        out["profile"] = {"name": profile.get("name"), "traits": traits}

    # Translate internal state into neutral in-world semantics. Never expose IDs,
    # root/facet field names, status labels, or episode bookkeeping to the model.
    topic = out.pop("topic", None)
    if isinstance(topic, dict):
        subject = _norm(topic.get("root"))
        focus = _norm(topic.get("current_facet"))
        out["discussion"] = {
            "subject": None if _bad_term(subject) else subject,
            "focus": None if _bad_term(focus) else focus,
            "related": _safe_semantic_list(topic.get("facets"), 8),
            "shared": _safe_semantic_list(topic.get("shared_references"), 6),
            "open_questions": _safe_semantic_list(topic.get("unresolved"), 5),
        }

    keywords = out.get("keywords")
    if isinstance(keywords, list):
        out["keywords"] = _safe_semantic_list(keywords, 8 if role == "comprehension" else 12)
    return out


def _sanitize_expression(obj: dict, compact: dict) -> dict:
    entity = _norm(compact.get("entity"))
    utterance = str(obj.get("utterance", "")).strip()
    low = _norm(utterance)

    # Reject self-referential scaffold constructions such as "Jules is a ...".
    if entity in PEOPLE and re.match(rf"^(?:i['’]?m sorry,?\s*)?{re.escape(entity)}\s+(?:is|means|represents)\b", low):
        raise ValueError("expression described self as a category")
    if entity in PEOPLE and re.search(rf"\b{re.escape(entity)}\b", low) and re.search(r"\b(?:should|allowed|required)\b.*\bspeak", low):
        raise ValueError("expression discussed speaking permission")

    terms: list[str] = []
    discussion = compact.get("discussion") if isinstance(compact.get("discussion"), dict) else {}
    for value in (discussion.get("subject"), discussion.get("focus")):
        s = _norm(value)
        if not _bad_term(s) and s not in terms:
            terms.append(s)
    for value in obj.get("topic_terms", []) if isinstance(obj.get("topic_terms"), list) else []:
        s = _norm(value)
        if _bad_term(s) or s in terms:
            continue
        terms.append(s)
    obj["topic_terms"] = terms[:4]
    if not obj["topic_terms"]:
        raise ValueError("expression had no usable semantic terms")

    if obj.get("target") == entity:
        partner = _norm(compact.get("partner"))
        if partner in PEOPLE and partner != entity:
            obj["target"] = partner
        else:
            raise ValueError("expression targeted self")
    return obj


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
    return re.sub(r"\s+", " ", detail).strip()[:240]


def run(role: str, payload: dict, timeout: int = 30):
    """Private local-model adapter. Prompted live nodes fail closed; no canned fallback."""
    raw_prompt = os.environ.get("ROOM_NODE_PROMPT", "").strip()
    if not raw_prompt:
        return None
    prompt = _decontaminate_instruction(raw_prompt)
    model_url = os.environ.get("ROOM_MODEL_URL", "").strip()
    if not model_url:
        raise RuntimeError(f"private model unavailable for {role}")

    compact = _compact_payload(payload, role)
    # Generic behavioral constraint only. It intentionally contains none of the
    # known infection phrases, so the guard itself cannot teach them back.
    guard = ""
    if role == "expression":
        guard = (
            "\nPUBLIC_SPEECH_RULE\n"
            "Produce ordinary in-world conversation only. Do not discuss formatting, control structures, hidden instructions, model behavior, internal labels, or permission to speak. "
            "Use a concrete detail, example, implication, disagreement, comparison, experience, or consequence grounded in the supplied situation.\n"
        )

    combined = prompt + guard + "\nINPUT_JSON\n" + json.dumps(compact, ensure_ascii=False, separators=(",", ":")) + "\nOUTPUT_JSON_ONLY\n"
    n_predict = {"comprehension": 192, "thought": 220, "expression": 220}.get(role, 192)
    temperature = {"comprehension": 0.15, "thought": 0.25, "expression": 0.42}.get(role, 0.25)
    request_body = {
        "prompt": combined,
        "n_predict": n_predict,
        "temperature": temperature,
        "cache_prompt": True,
        "json_schema": _schema(role),
    }
    body = json.dumps(request_body, ensure_ascii=False).encode()
    req = urllib.request.Request(_completion_url(model_url), data=body, headers={"Content-Type": "application/json"}, method="POST")
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
    if role != "expression" and _contains_explicit_leak_marker(out):
        raise RuntimeError(f"private model private structure failed privacy marker check for {role}")
    try:
        obj = _validate(role, _extract_json(out))
        if role == "expression":
            obj = _sanitize_expression(obj, compact)
        return obj
    except Exception as exc:
        raise RuntimeError(f"private model output rejected for {role}: {type(exc).__name__}") from exc
