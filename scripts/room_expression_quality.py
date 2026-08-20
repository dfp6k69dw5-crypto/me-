from __future__ import annotations

import hashlib
import os
import re

import room_private_model as _private_model

MAX_EXPRESSION_CHARS = 420

_AUTONOMOUS = {"sarah", "mara", "owen", "jules"}
_RECOVERY_SUBJECTS = (
    "music", "places", "food", "friendship", "nature", "travel", "books", "art",
    "work", "home", "weather", "skills", "movies", "gardens", "photography", "humor",
    "animals", "memory", "cities", "cooking", "objects", "learning",
)
_PRONOUN_R = re.compile(r"\b(?:i|we|you|they)\s+r\b", re.I)
_TRAILING_FRAGMENT = re.compile(r",\s*$")
_DANGLING_END = re.compile(
    r"\b(?:a|an|the|and|or|but|because|so|to|for|with|about|if|when|while|which|who|what|how|why|where|whether|than)\b"
    r"(?:\s+\b(?:what|which|who|how|why|where|whether|to)\b)?\s*$",
    re.I,
)
_PUNCTUATED_DANGLING_END = re.compile(r"\b(?:a|an|the|to)\s*$", re.I)
_LOCAL_REPEAT = re.compile(
    r"\b(?P<phrase>[A-Za-z][A-Za-z']*(?:\s+[A-Za-z][A-Za-z']*){1,4})\s+and\s+(?P=phrase)\b",
    re.I,
)
_RETRY_PROSE = (
    "\nUse a different idea and wording while staying with the same conversation. "
    "Keep the reply concise and grammatically complete."
)


def _tokens(value: object) -> list[str]:
    return re.findall(r"[a-z0-9']+", str(value or "").lower())


def _self_address(utterance: str, self_entity: str | None) -> bool:
    name = str(self_entity or "").strip()
    if not name:
        return False
    return bool(re.match(rf"^\s*(?:hey\s*[,!]?\s*)?{re.escape(name)}\b\s*[,!:.-]", utterance, re.I))


def _drop_self_address(text: str, self_entity: str | None) -> str:
    name = str(self_entity or "").strip()
    if not name:
        return text
    cleaned = re.sub(
        rf"^\s*(?:hey\s*[,!]?\s*)?{re.escape(name)}\b\s*[,!:.-]\s*",
        "",
        text,
        count=1,
        flags=re.I,
    ).strip()
    return cleaned or text


def _repair_pronoun_fragments(text: str) -> str:
    replacements = (
        (r"\bi\s+r\s+are\b", "I am"),
        (r"\bi\s+r\s+am\b", "I am"),
        (r"\bi\s+r\s+not\b", "I'm not"),
        (r"\bi\s+r\b", "I'm"),
        (r"\bwe\s+r\b", "we're"),
        (r"\byou\s+r\b", "you're"),
        (r"\bthey\s+r\b", "they're"),
    )
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text, flags=re.I)
    text = re.sub(r"\s+'s\b", "'s", text)
    if text and text[0].isalpha():
        text = text[0].upper() + text[1:]
    return text


def _sentence_similarity(left: str, right: str) -> float:
    a, b = set(_tokens(left)), set(_tokens(right))
    if not a or not b:
        return 0.0
    return len(a & b) / max(1, len(a | b))


def _dedupe_sentences(text: str) -> str:
    parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
    if len(parts) < 2:
        return text.strip()
    kept: list[str] = []
    for part in parts:
        norm = re.sub(r"\s+", " ", part.lower()).strip()
        duplicate = False
        for prior in kept:
            prior_norm = re.sub(r"\s+", " ", prior.lower()).strip()
            if norm == prior_norm:
                duplicate = True
                break
            if min(len(_tokens(part)), len(_tokens(prior))) >= 6 and _sentence_similarity(part, prior) >= 0.84:
                duplicate = True
                break
        if not duplicate:
            kept.append(part)
    return " ".join(kept).strip()


def _dedupe_local_phrase(text: str) -> str:
    """Collapse only exact 2-5 word phrases repeated around 'and'."""
    previous = None
    current = text
    for _ in range(3):
        if current == previous:
            break
        previous = current
        current = _LOCAL_REPEAT.sub(lambda match: match.group("phrase"), current)
    return current.strip()


def _truncate_before_repeated_ngram(text: str, n: int = 6) -> str:
    matches = list(re.finditer(r"[A-Za-z0-9']+", text))
    if len(matches) < n * 2:
        return text
    words = [match.group(0).lower() for match in matches]
    seen: dict[tuple[str, ...], int] = {}
    for index in range(len(words) - n + 1):
        gram = tuple(words[index:index + n])
        previous = seen.get(gram)
        if previous is not None and index - previous >= n:
            cut = matches[index].start()
            candidate = text[:cut].rstrip(" ,;:-")
            candidate = re.sub(r"\b(?:and|but|or|because|so)\s*$", "", candidate, flags=re.I).rstrip(" ,;:-")
            if len(candidate) >= 20:
                if candidate[-1:] not in ".!?":
                    candidate += "."
                return candidate
        seen.setdefault(gram, index)
    return text


def _cap_complete(text: str) -> str:
    text = text.strip()
    if len(text) <= MAX_EXPRESSION_CHARS:
        return text
    parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
    out: list[str] = []
    for part in parts:
        candidate = " ".join([*out, part]).strip()
        if len(candidate) > MAX_EXPRESSION_CHARS:
            break
        out.append(part)
    if out:
        return " ".join(out).strip()
    cut = text[: MAX_EXPRESSION_CHARS - 1].rstrip()
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    cut = cut.rstrip(" ,;:-")
    return (cut + ".") if cut else ""


def _terminal_body(text: str) -> str:
    return re.sub(r"[.!?]+\s*$", "", str(text or "").strip()).strip()


def _terminal_incomplete(text: str) -> bool:
    raw = str(text or "").strip()
    body = _terminal_body(raw)
    if not body:
        return False
    if raw[-1:] in ".!?":
        return bool(_PUNCTUATED_DANGLING_END.search(body))
    return bool(_DANGLING_END.search(body))


def _drop_incomplete_tail(text: str) -> str:
    """Drop a dangling final sentence/clause only when a complete prefix exists."""
    text = text.strip()
    if not text or not _terminal_incomplete(text):
        return text
    body = _terminal_body(text)
    endings = list(re.finditer(r"[.!?]", body))
    if not endings:
        # With no earlier complete sentence, do not invent content here. The
        # quality gate can reject the utterance and ask the model for another.
        return text
    candidate = body[: endings[-1].end()].strip()
    return candidate or text


def repair_expression(utterance: object, self_entity: str | None = None) -> str:
    """Repair mechanical generation damage without inventing new content."""
    text = re.sub(r"\s+", " ", str(utterance or "")).strip()
    if not text:
        return text
    text = _repair_pronoun_fragments(text)
    text = _drop_self_address(text, self_entity)
    text = _dedupe_sentences(text)
    text = _dedupe_local_phrase(text)
    text = _truncate_before_repeated_ngram(text)
    text = _cap_complete(text)
    text = _drop_incomplete_tail(text)
    if _TRAILING_FRAGMENT.search(text):
        text = _TRAILING_FRAGMENT.sub(".", text)
    return text.strip()


def _has_repeated_ngram(utterance: str, n: int = 6) -> bool:
    words = _tokens(utterance)
    if len(words) < n * 2:
        return False
    seen: dict[tuple[str, ...], int] = {}
    for index in range(len(words) - n + 1):
        gram = tuple(words[index:index + n])
        previous = seen.get(gram)
        if previous is not None and index - previous >= n:
            return True
        seen.setdefault(gram, index)
    return False


def _context_too_similar(utterance: str, compact: dict, similarity_fn) -> bool:
    context = compact.get("context") if isinstance(compact.get("context"), list) else []
    current_tokens = len(_tokens(utterance))
    for message in context[-4:]:
        text = message.get("text") if isinstance(message, dict) else message
        other_tokens = len(_tokens(text))
        score = float(similarity_fn(utterance, text))
        shortest = min(current_tokens, other_tokens)
        if score >= 0.88:
            return True
        if shortest >= 35 and score >= 0.52:
            return True
        if shortest >= 18 and score >= 0.68:
            return True
    return False


def _recovery_subject(self_entity: str | None) -> str:
    key = f"{os.environ.get('ROOM_CYCLE_KEY', 'room-cycle')}:{self_entity or 'room'}:quality-recovery"
    index = int(hashlib.sha256(key.encode()).hexdigest()[:12], 16) % len(_RECOVERY_SUBJECTS)
    return _RECOVERY_SUBJECTS[index]


def _escape_stale_context(compact: dict, self_entity: str | None) -> None:
    """Mutate only the next model attempt after a semantic-copy rejection."""
    event = compact.get("event") if isinstance(compact.get("event"), dict) else None
    speaker = str((event or {}).get("speaker") or "").lower()

    # Non-autonomous participants are adjacency events. Simplify to their newest
    # words but never pivot away from them merely because a reply copied context.
    if event and speaker not in _AUTONOMOUS:
        compact["context"] = [event]
        return

    fresh = _recovery_subject(self_entity)
    compact["event"] = None
    compact["context"] = []
    compact["discussion"] = {
        "subject": fresh,
        "focus": fresh,
        "related": [],
        "shared": [],
        "open_questions": [],
    }
    compact.pop("intent", None)
    compact.pop("possible_direction", None)
    personality = compact.get("personality_context")
    if isinstance(personality, dict):
        personality.pop("current", None)


def quality_issue(utterance: object, compact: dict, self_entity: str | None, similarity_fn) -> str | None:
    text = str(utterance or "").strip()
    if not text:
        return "empty_expression"
    if len(text) > MAX_EXPRESSION_CHARS:
        return "rambling_expression"
    if _PRONOUN_R.search(text):
        return "malformed_pronoun"
    if _self_address(text, self_entity):
        return "self_address"
    if _TRAILING_FRAGMENT.search(text):
        return "trailing_fragment"
    if _terminal_incomplete(text):
        return "trailing_fragment"
    if _has_repeated_ngram(text):
        _escape_stale_context(compact, self_entity)
        return "self_repetition"
    if _context_too_similar(text, compact, similarity_fn):
        _escape_stale_context(compact, self_entity)
        return "duplicate_context"
    return None


def _strip_retry_prose(prompt: object) -> str:
    """Retry control is internal state; never expose it as model-visible prose."""
    return str(prompt or "").replace(_RETRY_PROSE, "")


# Install a mechanical repair stage into the already-existing private-model
# sanitizer. The wrapper imports this module after room_private_model is loaded,
# so no prompt or orchestration data is introduced by this hook.
if not getattr(_private_model._sanitize_expression, "_room_quality_repair", False):
    _original_sanitize_expression = _private_model._sanitize_expression

    def _quality_sanitize_expression(obj: dict, compact: dict, self_entity: str | None = None) -> dict:
        cleaned = _original_sanitize_expression(obj, compact, self_entity)
        if isinstance(cleaned, dict):
            cleaned = dict(cleaned)
            cleaned["utterance"] = repair_expression(cleaned.get("utterance"), self_entity)
        return cleaned

    _quality_sanitize_expression._room_quality_repair = True
    _private_model._sanitize_expression = _quality_sanitize_expression


# The engine may retry a rejected generation with a higher sampling temperature,
# but the reason/revision instruction stays outside cognition. Strip the legacy
# retry sentence at the final network boundary so every attempt receives the same
# conversational instruction prefix.
if not getattr(_private_model._request, "_room_retry_boundary", False):
    _original_request = _private_model._request

    def _quality_request(model_url, prompt, role, temperature, timeout, self_entity=None, attempt=0):
        return _original_request(
            model_url,
            _strip_retry_prose(prompt),
            role,
            temperature,
            timeout,
            self_entity,
            attempt,
        )

    _quality_request._room_retry_boundary = True
    _private_model._request = _quality_request
