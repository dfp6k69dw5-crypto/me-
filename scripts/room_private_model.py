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
META_PATTERNS = (
    r"\btopic[-_ ]?\d{3,}\b",
    r"\btopic\s+(?:root|facet|episode|identifier|id|schema|closure|closing)\b",
    r"\bcurrent\s+(?:narrow\s+)?topic\b",
    r"\bnarrow\s+topic\s+facet\b",
    r"\bsemantic\s+schema\b",
    r"\b(?:input|output)[-_ ]?json\b",
    r"\bmandatory\s+speech\b",
    r"\b(?:should|allowed|required)\s+(?:i\s+)?(?:be\s+)?speaking\b",
    r"\bnot\s+sure\s+if\s+i\s+should\s+be\s+speaking\b",
    r"\b[a-z-]+-related\s+topic\b",
    r"\b(?:main|current)\s+subject\b",
    r"\bcurrent\s+focus\b",
    r"\bdiscussion\s+(?:subject|focus)\b",
)


def enabled(role: str) -> bool:
    return bool(os.environ.get("ROOM_NODE_PROMPT", "").strip() and os.environ.get("ROOM_MODEL_URL", "").strip())


def _norm(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _extract_json(text: str):
    text = str(text or "").strip()
    if not text:
        raise ValueError("model returned no structured object")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    if start < 0:
        raise ValueError("model returned no structured object")
    obj, _ = json.JSONDecoder().raw_decode(text[start:])
    return obj


def _contains_explicit_leak_marker(value: object) -> bool:
    low = _norm(value)
    return any(marker in low for marker in LEAK_MARKERS)


def _contains_meta_language(value: object) -> bool:
    low = _norm(value)
    return any(re.search(pattern, low) for pattern in META_PATTERNS)


def _structure_contaminated(value: object) -> bool:
    if isinstance(value, str):
        return _contains_explicit_leak_marker(value) or _contains_meta_language(value)
    if isinstance(value, list):
        return any(_structure_contaminated(item) for item in value)
    if isinstance(value, dict):
        return any(_structure_contaminated(item) for item in value.values())
    return False


def _clean_private(value: object):
    if isinstance(value, str):
        return None if _contains_explicit_leak_marker(value) or _contains_meta_language(value) else value
    if isinstance(value, list):
        out = []
        for item in value:
            cleaned = _clean_private(item)
            if cleaned is not None:
                out.append(cleaned)
        return out
    if isinstance(value, dict):
        return {key: _clean_private(item) for key, item in value.items()}
    return value


def _decontaminate_instruction(prompt: str) -> str:
    """Translate the runtime copy of the secret into neutral vocabulary before inference."""
    text = str(prompt or "")
    replacements = (
        (r"(?i)the natural public conversational turn", "an ordinary spoken reply"),
        (r"(?i)natural public conversational turn", "ordinary spoken reply"),
        (r"(?i)topic_terms", "semantic_terms"),
        (r"(?i)topic_facet", "focus"),
        (r"(?i)topic_episode", "discussion_thread"),
        (r"(?i)topic_deepening", "deepen"),
        (r"(?i)topic_bridge", "bridge"),
        (r"(?i)topic_closing", "close"),
        (r"(?i)close_topic", "close"),
        (r"(?i)mandatory_speech", "must_respond"),
        (r"(?i)mandatory speech", "must respond"),
        (r"(?i)current narrow topic facet", "specific detail"),
        (r"(?i)current narrow facet", "specific detail"),
        (r"(?i)current topic facet", "specific detail"),
        (r"(?i)current topic root", "main idea"),
        (r"(?i)topic root", "main idea"),
        (r"(?i)topic facet", "specific detail"),
        (r"(?i)topic episode", "ongoing discussion"),
        (r"(?i)\btopic\b", "subject"),
        (r"(?i)\bfacet\b", "detail"),
        (r"(?i)\broot\b", "basis"),
        (r"(?i)\bschema\b", "structure"),
        (r"(?i)\bjson\b", "structured data"),
    )
    for pattern, replacement in replacements:
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
            "move": {"type": "string", "enum": ["answer", "disclosure", "question", "disagreement", "support", "joke", "clarification", "repair", "repair_attempt", "deepen", "bridge", "close", "other"]},
            "grounding": {"type": "string", "enum": ["understood", "apparently_understood", "ambiguous", "contradicted", "misunderstood", "repair_needed"]},
            "focus": _nullable_string(),
            "new_details": _string_array(6),
            "bids": _string_array(5),
            "relationship_events": _string_array(6),
            "shared_references": _string_array(5),
            "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        }
        return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}
    if role == "thought":
        properties = {
            "action": {"type": "string", "enum": ["ANSWER", "DEEPEN", "DISCLOSE", "COMPARE", "DISAGREE", "REPAIR", "SUPPORT", "CALLBACK", "BRIDGE", "CLOSE"]},
            "preferred_partner": {"type": "string", "enum": PEOPLE},
            "focus": {"type": "string"},
            "new_information_goal": {"type": "string", "maxLength": 240},
            "disclosure_depth": {"type": "integer", "minimum": 0, "maximum": 4},
            "interpersonal_risk": {"type": "integer", "minimum": 0, "maximum": 4},
            "shared_reference": _nullable_string(),
            "unresolved_thread": _nullable_string(),
            "reason_summary": {"type": "string", "maxLength": 180},
            "must_respond": {"type": "boolean", "enum": [True]},
        }
        return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}
    if role == "expression":
        properties = {
            "decision": {"type": "string", "enum": ["SPEAK"]},
            "target": {"type": "string", "enum": PEOPLE},
            "move": {"type": "string", "enum": ["answer", "deepen", "disclose", "compare", "disagree", "repair", "support", "callback", "bridge", "close"]},
            "utterance": {"type": "string", "minLength": 1, "maxLength": 700},
            "semantic_terms": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 4},
        }
        return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}
    raise ValueError(f"unknown private model role: {role}")


def _bad_term(value: object) -> bool:
    text = _norm(value)
    if not text or len(text) > 80:
        return True
    if _contains_meta_language(text) or _contains_explicit_leak_marker(text):
        return True
    if re.fullmatch(r"topic[-_ ]?\d+", text):
        return True
    if text in {"topic", "conversation", "discussion", "subject", "facet", "root", "schema", "context", "label", "category"}:
        return True
    if text.endswith(" topic") or text.startswith("topic "):
        return True
    return False


def _public_message(message: object, text_limit: int) -> dict:
    if not isinstance(message, dict):
        return {"speaker": None, "text": str(message or "")[:text_limit], "target": None}
    cognition = message.get("cognition") if isinstance(message.get("cognition"), dict) else {}
    return {"speaker": message.get("speaker"), "text": str(message.get("text", ""))[:text_limit], "target": cognition.get("target")}


def _safe_semantic_list(values: object, limit: int) -> list[str]:
    out: list[str] = []
    if not isinstance(values, list):
        return out
    for value in values:
        text = _norm(value)
        if _bad_term(text) or text in out:
            continue
        out.append(text)
        if len(out) >= limit:
            break
    return out


def _compact_payload(payload: dict, role: str) -> dict:
    out = dict(payload or {})
    out.pop("mandatory_speech", None)
    out["must_respond"] = True

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
            if _contains_meta_language(public.get("text")):
                continue
            cleaned.append(public)
        out["context"] = cleaned[-context_count:]

    profile = out.get("profile")
    if isinstance(profile, dict):
        traits = profile.get("traits", {}) if isinstance(profile.get("traits"), dict) else {}
        if role == "comprehension":
            traits = {key: traits.get(key) for key in ("social_sensitivity", "curiosity", "skepticism") if key in traits}
        out["profile"] = {"name": profile.get("name"), "traits": traits}

    internal = out.pop("topic", None)
    if isinstance(internal, dict):
        subject = _norm(internal.get("root"))
        focus = _norm(internal.get("current_facet"))
        out["discussion"] = {
            "subject": None if _bad_term(subject) else subject,
            "focus": None if _bad_term(focus) else focus,
            "related": _safe_semantic_list(internal.get("facets"), 8),
            "shared": _safe_semantic_list(internal.get("shared_references"), 6),
            "open_questions": _safe_semantic_list(internal.get("unresolved"), 5),
        }

    if isinstance(out.get("keywords"), list):
        out["keywords"] = _safe_semantic_list(out["keywords"], 8 if role == "comprehension" else 12)
    if "social_observation" in out:
        out["social_observation"] = _clean_private(out.get("social_observation"))
    if "deliberation" in out:
        out["deliberation"] = _clean_private(out.get("deliberation"))
    return out


def _prompt_overlap(utterance: str, prompt: str) -> bool:
    low = _norm(utterance)
    clean_prompt = _norm(prompt)
    if not low or not clean_prompt:
        return False
    chunks = [clean_prompt[i:i+64] for i in range(0, max(0, len(clean_prompt)-63), 32)]
    return any(chunk and chunk in low for chunk in chunks)


def _validate(role: str, obj: object, compact: dict, prompt: str) -> dict:
    if not isinstance(obj, dict):
        raise ValueError("not_object")
    if role == "expression":
        if str(obj.get("decision", "")).upper() != "SPEAK":
            raise ValueError("missing_speak")
        utterance = obj.get("utterance")
        if not isinstance(utterance, str) or not utterance.strip():
            raise ValueError("missing_utterance")
        if len(utterance.strip()) > 700:
            raise ValueError("utterance_too_long")
        if _contains_explicit_leak_marker(utterance):
            raise ValueError("privacy_marker")
        if _contains_meta_language(utterance):
            raise ValueError("meta_language")
        if _prompt_overlap(utterance, prompt):
            raise ValueError("instruction_overlap")
        if not isinstance(obj.get("semantic_terms"), list):
            raise ValueError("missing_semantic_terms")
        entity = _norm(compact.get("entity"))
        low = _norm(utterance)
        if entity in PEOPLE and re.match(rf"^(?:i['’]?m sorry,?\s*)?{re.escape(entity)}\s+(?:is|means|represents)\b", low):
            raise ValueError("self_category")
        if re.search(r"\b(?:should|allowed|required)\b.*\bspeak", low):
            raise ValueError("speaking_permission")
    elif role == "thought":
        if not isinstance(obj.get("action"), str):
            raise ValueError("missing_action")
        if obj.get("must_respond") is not True:
            raise ValueError("must_respond_false")
        if _structure_contaminated(obj):
            raise ValueError("private_meta_language")
    elif role == "comprehension":
        if not isinstance(obj.get("participation"), str):
            raise ValueError("missing_participation")
        if not isinstance(obj.get("relationship_events"), list):
            raise ValueError("bad_relationship_events")
        if _structure_contaminated(obj):
            raise ValueError("private_meta_language")
    return obj


def _sanitize_expression(obj: dict, compact: dict) -> dict:
    terms: list[str] = []
    discussion = compact.get("discussion") if isinstance(compact.get("discussion"), dict) else {}
    for value in (discussion.get("subject"), discussion.get("focus")):
        text = _norm(value)
        if not _bad_term(text) and text not in terms:
            terms.append(text)
    for value in obj.get("semantic_terms", []) if isinstance(obj.get("semantic_terms"), list) else []:
        text = _norm(value)
        if _bad_term(text) or text in terms:
            continue
        terms.append(text)
    obj["semantic_terms"] = terms[:4]
    if not obj["semantic_terms"]:
        raise ValueError("no_usable_semantic_terms")

    entity = _norm(compact.get("entity"))
    if obj.get("target") == entity:
        partner = _norm(compact.get("partner"))
        if partner in PEOPLE and partner != entity:
            obj["target"] = partner
        else:
            raise ValueError("self_target")
    return obj


def _completion_url(model_url: str) -> str:
    base = model_url.rstrip("/")
    return base if base.endswith("/completion") else base + "/completion"


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


def _request(model_url: str, prompt: str, role: str, temperature: float, timeout: int) -> str:
    request_body = {
        "prompt": prompt,
        "n_predict": {"comprehension": 192, "thought": 220, "expression": 220}.get(role, 192),
        "temperature": temperature,
        "cache_prompt": True,
        "json_schema": _schema(role),
    }
    req = urllib.request.Request(
        _completion_url(model_url),
        data=json.dumps(request_body, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8", "replace"))
    return str(data.get("content", ""))


def run(role: str, payload: dict, timeout: int = 30):
    raw_prompt = os.environ.get("ROOM_NODE_PROMPT", "").strip()
    if not raw_prompt:
        return None
    prompt = _decontaminate_instruction(raw_prompt)
    model_url = os.environ.get("ROOM_MODEL_URL", "").strip()
    if not model_url:
        raise RuntimeError(f"private model unavailable for {role}")

    compact = _compact_payload(payload, role)
    base_guard = ""
    if role == "expression":
        base_guard = (
            "\nPUBLIC_SPEECH_RULE\n"
            "Produce ordinary in-world conversation only. Do not discuss formatting, control structures, hidden instructions, model behavior, internal labels, or permission to speak. "
            "Use concrete content from the supplied situation.\n"
        )

    attempts = 3 if role == "expression" else 2
    last_reason = "unknown"
    for attempt in range(attempts):
        retry_guard = ""
        if attempt:
            retry_guard = (
                "\nFRESH_CANDIDATE_RULE\n"
                "A previous candidate failed a private quality gate. Produce a completely different candidate. Do not refer to the prior candidate, the gate, the task, rules, formatting, or whether anyone may speak.\n"
            )
        combined = (
            prompt + base_guard + retry_guard
            + "\nSITUATION_DATA\n"
            + json.dumps(compact, ensure_ascii=False, separators=(",", ":"))
            + "\nRETURN_STRUCTURED_DATA_ONLY\n"
        )
        temperature = {"comprehension": 0.15, "thought": 0.25, "expression": 0.42}.get(role, 0.25) + 0.06 * attempt
        try:
            out = _request(model_url, combined, role, temperature, timeout)
            if not out:
                last_reason = "empty_output"
                continue
            obj = _validate(role, _extract_json(out), compact, prompt)
            if role == "expression":
                obj = _sanitize_expression(obj, compact)
            return obj
        except urllib.error.HTTPError as exc:
            detail = _safe_http_detail(exc)
            suffix = f": {detail}" if detail else ""
            raise RuntimeError(f"private model request failed for {role}: HTTP {exc.code}{suffix}") from exc
        except ValueError as exc:
            last_reason = str(exc)[:80]
            continue
        except Exception as exc:
            raise RuntimeError(f"private model request failed for {role}: {type(exc).__name__}") from exc

    raise RuntimeError(f"private model output rejected for {role}: {last_reason}")
