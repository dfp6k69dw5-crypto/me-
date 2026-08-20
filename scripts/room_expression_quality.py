from __future__ import annotations

import re

MAX_EXPRESSION_CHARS = 420

_PRONOUN_R = re.compile(r"\b(?:i|we|you|they)\s+r\b", re.I)
_TRAILING_FRAGMENT = re.compile(r"[,;:]\s*$")


def _tokens(value: object) -> list[str]:
    return re.findall(r"[a-z0-9']+", str(value or "").lower())


def _self_address(utterance: str, self_entity: str | None) -> bool:
    name = str(self_entity or "").strip()
    if not name:
        return False
    return bool(re.match(rf"^\s*(?:hey\s*[,!]?\s*)?{re.escape(name)}\b\s*[,!:.-]", utterance, re.I))


def _has_repeated_ngram(utterance: str, n: int = 7) -> bool:
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
        # Long turns should carry genuinely new material. A Jaccard score above
        # roughly one half on 35+ word turns is the live Room's paraphrase loop,
        # not ordinary reuse of a subject name.
        if shortest >= 35 and score >= 0.52:
            return True
        if shortest >= 18 and score >= 0.68:
            return True
    return False


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
    if _has_repeated_ngram(text):
        return "self_repetition"
    if _context_too_similar(text, compact, similarity_fn):
        return "duplicate_context"
    return None
