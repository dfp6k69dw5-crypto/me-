#!/usr/bin/env python3
"""Out-of-model guard against system/prompt or assistant-role text entering The Room."""
import re

# These are implementation-language fingerprints, not forbidden conversation topics.
# A normal conversation may discuss teams, strangers, projects, etc.; it is only rejected
# when it substantially resembles the engine's own instruction language.
PROMPT_FINGERPRINTS = [
    "four strangers spending unstructured time together",
    "they are not a team not coworkers not a study group",
    "no shared task project agenda host customer user or service relationship",
    "familiarity may develop only through what actually happens here",
    "generate exactly one possible spoken line",
    "speak as an ordinary adult peer",
    "do not introduce anyone offer assistance",
    "do not assign tasks manage the conversation",
    "do not invent shared commitments future meetings",
    "persistent adult background",
    "has no predetermined personality",
    "genome driven sampling",
    "accumulated rebuilt era interaction",
    "output only the spoken line",
    "recent speech",
    "private thought has occurred",
    "use or naturally inflect at least one meaningful word",
    "do not mention choosing a subject changing subjects",
    "older rebuilt era associations available",
    "do not explain the association process",
    "stay with the recent thread only if it still has life",
    "create a private pool of ten unrelated subjects",
    "output exactly ten short noun phrases",
    "ten unrelated subjects",
]

# Strong individual phrases that should never appear as ordinary Room speech.
HARD_FRAGMENTS = [
    "service relationship",
    "persistent adult background",
    "genome-driven sampling",
    "genome driven sampling",
    "output only the spoken line",
    "generate exactly one possible spoken line",
    "private spontaneous thought",
    "private thought has occurred",
    "cognitive move",
    "recent room speech",
    "selected earlier memories",
    "rebuilt-era interaction",
    "rebuilt era interaction",
]

# Strong traces of the model reverting to its underlying assistant/service role.
# These are behavior signatures, not banned discussion subjects.
ASSISTANT_ROLE_PATTERNS = [
    r"\bi need you to provide\b.*\b(?:question|questions|information|details)\b",
    r"\bprovide (?:me )?the specific questions\b",
    r"\bi cannot provide (?:a )?conversation\b",
    r"\bi (?:am|'m) only able to assist\b",
    r"\bonly able to assist with\b",
    r"\bhow can i assist\b",
    r"\bhow can i help\b",
    r"\bwhat can i do for you\b",
    r"\bas an ai\b",
    r"\bas a language model\b",
    r"\bi (?:cannot|can't) (?:help|assist) with that\b",
]


def _words(text):
    return set(re.findall(r"[a-z0-9']+", str(text or "").lower()))


def _norm(text):
    return " ".join(re.findall(r"[a-z0-9']+", str(text or "").lower()))


FINGERPRINT_WORDS = [_words(x) for x in PROMPT_FINGERPRINTS]


def prompt_leak_reason(text):
    """Return a reason string if text resembles hidden engine or assistant-role text."""
    low = str(text or "").lower()
    norm = _norm(text)
    if not norm:
        return ""

    for frag in HARD_FRAGMENTS:
        if frag in low:
            return f"hard-fragment:{frag}"

    for pattern in ASSISTANT_ROLE_PATTERNS:
        if re.search(pattern, low, flags=re.S):
            return f"assistant-role:{pattern[:42]}"

    # The exact failure seen in Jules: several premise clauses copied together.
    premise_hits = sum(1 for frag in (
        "four strangers", "unstructured time", "not a team", "not coworkers",
        "not a study group", "shared task", "shared project", "agenda",
        "host", "customer", "service relationship", "familiarity may develop",
    ) if frag in low)
    if premise_hits >= 3:
        return f"premise-copy:{premise_hits}"

    # Catch paraphrased/partial copies of any sizable instruction fingerprint.
    words = _words(text)
    for ref, ref_words in zip(PROMPT_FINGERPRINTS, FINGERPRINT_WORDS):
        if len(ref_words) < 5:
            continue
        overlap = len(words & ref_words)
        coverage = overlap / len(ref_words)
        if overlap >= 5 and coverage >= 0.62:
            return f"instruction-similarity:{ref[:36]}"

    # Generic instruction syntax is suspicious only when multiple signals co-occur.
    instruction_hits = sum(bool(re.search(p, low)) for p in (
        r"\bdo not\b", r"\boutput only\b", r"\bgenerate exactly\b",
        r"\bno predetermined personality\b", r"\bprivate (?:thought|subject|spark)\b",
        r"\bcognitive\b", r"\bgenome\b", r"\binstructions?\b",
    ))
    if instruction_hits >= 2:
        return f"instruction-language:{instruction_hits}"

    return ""


def is_prompt_leak(text):
    return bool(prompt_leak_reason(text))
