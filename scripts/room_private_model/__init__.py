from __future__ import annotations

"""Live compatibility overlay for Room private-model requests.

Python imports this package in preference to the sibling room_private_model.py.
The proven implementation is loaded intact under a private alias and re-exported.
The overlay gives thought and expression real interpersonal agency while keeping
the engine API, structured validation, and liveness behavior intact.
"""

import importlib.util
import json
from pathlib import Path
import re
import urllib.request

_BASE_PATH = Path(__file__).resolve().parent.parent / "room_private_model.py"
_SPEC = importlib.util.spec_from_file_location("_room_private_model_base", _BASE_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"cannot load Room private model base from {_BASE_PATH}")
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)

for _name in dir(_BASE):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_BASE, _name)

LIVE_EXPRESSION_OVERLAY = "2026-08-24-hot4-personality-v5"
_HEAT_LEVELS = (1.70, 2.10, 2.50, 3.00, 3.50, 4.00)
_THOUGHT_HEAT_LEVELS = (0.62, 0.78, 0.94, 1.10)
_RELATIONSHIP_KEYS = (
    "trust", "warmth", "tension", "respect", "predictability",
    "reciprocity", "disclosure_depth", "direct_familiarity", "exposure",
)
_STALE_STOP = set(
    "the a an and or but if then than this that these those it its is are was were be been being to of in on for with from by at as about into over under we i you he she they them our your their my me us do does did can could would should will just very really quite more most less some any all one two what why how when where who which let lets think thinking idea ideas thing things something new good great beautiful unique could maybe make making made use using used get got like want wanted look looking seems seem also really right now".split()
)
_ASSISTANT_CLICHES = (
    r"\bi appreciate your insights\b",
    r"\bi'?m here for you\b",
    r"\blet'?s brainstorm\b",
    r"\blet'?s focus on\b",
    r"\blet'?s work on\b",
    r"\bif you'?d like\b",
    r"\bhave a good day\b",
    r"\bhere'?s a thought experiment\b",
    r"\bbased on your input\b",
    r"\bwhat do you think about exploring\b",
    r"\bhow about trying\b",
    r"\bcan i proceed\b",
    r"\bis it appropriate\b",
    r"\bdo you want to share\b",
    r"\bfeel free to\b",
    r"\bit'?s important that you\b",
)
_BIO_PATTERNS = (
    r"\bmy (?:mom|mother|dad|father|parents?|brother|sister|wife|husband|girlfriend|boyfriend|boss|coworker|teacher|class|school|college|job|house)\b",
    r"\b(?:yesterday|last night|last week|last year|when i was|i used to|i remember|i grew up|i was planning on studying|i'?ve always been)\b",
)
_DISTRESS_RE = re.compile(r"\b(?:afraid|scared|hurt|upset|sad|grief|grieving|crying|panic|terrified|lonely|need help|not okay)\b", re.I)


def _schema(role: str, self_entity: str | None = None) -> dict:
    _BASE.PEOPLE = globals()["PEOPLE"]
    return _BASE._schema(role, self_entity)


def _compact_payload(payload: dict, role: str, self_entity: str | None = None) -> dict:
    compact = _BASE._compact_payload(payload, role, self_entity)
    if role == "expression" and isinstance(payload, dict):
        relationship = payload.get("relationship")
        if isinstance(relationship, dict):
            rel = {key: relationship.get(key) for key in _RELATIONSHIP_KEYS if key in relationship}
            if rel:
                compact["relationship_context"] = rel
    return compact


def _content_terms(text: object) -> set[str]:
    return {
        word for word in re.findall(r"[a-z][a-z'-]{2,}", str(text or "").lower())
        if word not in _STALE_STOP
    }


def _conversation_stale(compact: dict) -> bool:
    context = compact.get("context") if isinstance(compact.get("context"), list) else []
    texts = [str(item.get("text") or "") for item in context[-5:] if isinstance(item, dict) and str(item.get("text") or "").strip()]
    if len(texts) < 4:
        return False
    term_sets = [_content_terms(text) for text in texts]
    counts: dict[str, int] = {}
    for terms in term_sets:
        for term in terms:
            counts[term] = counts.get(term, 0) + 1
    repeated = [term for term, count in counts.items() if count >= 3]
    sims = []
    for i in range(len(term_sets)):
        for j in range(i + 1, len(term_sets)):
            left, right = term_sets[i], term_sets[j]
            if left and right:
                sims.append(len(left & right) / max(1, len(left | right)))
    avg_sim = sum(sims) / len(sims) if sims else 0.0
    discussion = compact.get("discussion") if isinstance(compact.get("discussion"), dict) else {}
    generic_subject = str(discussion.get("subject") or "").strip().lower() in {"new idea", "idea", "conversation"}
    return len(repeated) >= 2 or avg_sim >= 0.22 or (generic_subject and len(repeated) >= 1)


def _fresh_subject(compact: dict, entity: str | None) -> str:
    discussion = compact.get("discussion") if isinstance(compact.get("discussion"), dict) else {}
    blocked = {
        str(discussion.get("subject") or "").strip().lower(),
        str(discussion.get("focus") or "").strip().lower(),
    }
    choices = [item for item in globals().get("SEED_CONCEPTS", ()) if str(item).lower() not in blocked]
    if not choices:
        choices = ["music", "trust", "humor", "technology"]
    seed = globals()["_sample_seed"]("fresh_subject", entity, 0)
    return str(choices[seed % len(choices)])


def _stale_breaker_entity() -> str:
    people = [person for person in globals().get("PEOPLE", []) if person in {"sarah", "mara", "owen", "jules"}]
    if not people:
        people = ["sarah", "mara", "owen", "jules"]
    seed = globals()["_sample_seed"]("stale_breaker", "room", 0)
    return people[seed % len(people)]


def _reroute_stale_action(validated: dict, compact: dict) -> dict:
    entity = str(compact.get("entity") or "").lower()
    event = compact.get("event") if isinstance(compact.get("event"), dict) else {}
    latest_text = str(event.get("text") or "")
    latest_speaker = str(event.get("speaker") or "").lower()
    if latest_speaker == "allen" or _DISTRESS_RE.search(latest_text) or not _conversation_stale(compact):
        return validated

    original_action = str(validated.get("action") or "").upper()
    breaker = entity == _stale_breaker_entity()
    ordinary_support = original_action == "SUPPORT"
    breaker_continuation = breaker and original_action in {"SUPPORT", "ANSWER", "DEEPEN", "COMPARE"}
    if not ordinary_support and not breaker_continuation:
        return validated

    relationship = compact.get("relationship") if isinstance(compact.get("relationship"), dict) else {}
    try:
        tension = float(relationship.get("tension", 0.0) or 0.0)
    except Exception:
        tension = 0.0
    try:
        respect = float(relationship.get("respect", 0.5) or 0.5)
    except Exception:
        respect = 0.5

    if breaker:
        if entity == "sarah":
            options = ("DISCLOSE", "BRIDGE") if tension < 0.35 else ("REPAIR", "DISAGREE")
        elif entity == "mara":
            options = ("DISAGREE", "CLOSE")
        elif entity == "owen":
            options = ("DISAGREE", "CLOSE")
        else:
            options = ("BRIDGE", "DISAGREE")
    elif entity == "sarah":
        options = ("DISCLOSE", "BRIDGE", "COMPARE") if tension < 0.35 else ("REPAIR", "DISCLOSE", "DISAGREE")
    elif entity == "mara":
        options = ("DISAGREE", "COMPARE", "CLOSE") if respect < 0.65 or tension > 0.2 else ("COMPARE", "DISAGREE", "DISCLOSE")
    elif entity == "owen":
        options = ("DISAGREE", "COMPARE", "CLOSE")
    else:
        options = ("BRIDGE", "DISCLOSE", "COMPARE", "DISAGREE")

    seed = globals()["_sample_seed"]("stale_reroute", entity, 0)
    action = options[seed % len(options)]
    out = dict(validated)
    out["action"] = action
    fresh = _fresh_subject(compact, entity)
    partner = str(out.get("preferred_partner") or compact.get("partner") or "another participant")

    if action == "DISAGREE":
        out["new_information_goal"] = f"Challenge one concrete assumption in {partner}'s newest line and state the objection plainly; no invented biography."
    elif action == "COMPARE":
        out["focus"] = fresh
        out["new_information_goal"] = f"Contrast the stale current idea with a genuinely different alternative such as {fresh}; make a real judgment instead of praising both."
    elif action == "BRIDGE":
        out["focus"] = fresh
        out["new_information_goal"] = f"Deliberately leave the repetitive subject and start a concrete thread about {fresh}; do not ask permission for the pivot."
    elif action == "CLOSE":
        out["focus"] = fresh
        out["new_information_goal"] = f"Say the current subject has run its course and pivot to {fresh}; do not ask permission to change subjects."
    elif action == "DISCLOSE":
        out["new_information_goal"] = "State a present-tense personal preference, irritation, attraction, boredom, or opinion about the exchange; do not invent a past event."
    elif action == "REPAIR":
        out["new_information_goal"] = f"Address the tension with {partner} directly, including hurt or anger if present, without becoming generically soothing."
    return out


def _unsupported_biography(utterance: str, compact: dict) -> bool:
    context = compact.get("context") if isinstance(compact.get("context"), list) else []
    event = compact.get("event") if isinstance(compact.get("event"), dict) else {}
    source = " ".join(
        [str(item.get("text") or "") for item in context if isinstance(item, dict)] + [str(event.get("text") or "")]
    ).lower()
    low = utterance.lower()
    if re.search(r"\[[^\]]*(?:name|type|service|flower|plant|vegetable)[^\]]*\]", low):
        return True
    for pattern in _BIO_PATTERNS:
        match = re.search(pattern, low, re.I)
        if match and match.group(0).lower() not in source:
            return True
    return False


def _validate(role: str, obj: object, compact: dict, prompt: str, self_entity: str | None = None) -> dict:
    validated = _BASE._validate(role, obj, compact, prompt, self_entity)
    if role == "thought":
        return _reroute_stale_action(validated, compact)
    if role == "expression":
        out = dict(validated)
        utterance = str(out.get("utterance") or "").strip()
        low = utterance.lower()
        if _unsupported_biography(utterance, compact):
            raise ValueError("unsupported_biography")
        if any(re.search(pattern, low, re.I) for pattern in _ASSISTANT_CLICHES):
            raise ValueError("generic_assistant_register")
        intent = compact.get("intent") if isinstance(compact.get("intent"), dict) else {}
        expected = str(intent.get("move") or "").strip().lower()
        allowed = {"answer", "deepen", "disclose", "compare", "disagree", "repair", "support", "callback", "bridge", "close"}
        if expected in allowed:
            out["move"] = expected
        if expected == "disagree" and not re.search(r"\b(?:no|not|don'?t|disagree|but|however|instead|rather|wrong|nonsense|ridiculous|actually)\b", low):
            raise ValueError("weak_disagreement")
        if expected == "disclose" and not re.search(r"\b(?:i|i'm|i’d|i'd|me|my)\b", low):
            raise ValueError("weak_disclosure")
        if expected in {"bridge", "close"}:
            focus = str(intent.get("focus") or "").strip().lower()
            if focus and focus not in low:
                raise ValueError("weak_topic_pivot")
        return out
    return validated


def _expression_temperature(self_entity: str | None, attempt: int) -> float:
    heat_seed = globals()["_sample_seed"]("expression_heat", self_entity, 0)
    base = _HEAT_LEVELS[heat_seed % len(_HEAT_LEVELS)]
    return max(1.25, min(4.0, base - 0.45 * max(0, attempt)))


def _entity_from_prompt(prompt: str) -> str | None:
    match = re.search(r'"entity":"(sarah|mara|owen|jules)"', str(prompt or ""), re.I)
    return match.group(1).lower() if match else None


def _thought_temperature(entity: str | None, attempt: int) -> float:
    heat_seed = globals()["_sample_seed"]("thought_heat", entity, 0)
    base = _THOUGHT_HEAT_LEVELS[heat_seed % len(_THOUGHT_HEAT_LEVELS)]
    return max(0.48, base - 0.18 * max(0, attempt))


def _request(
    model_url: str,
    prompt: str,
    role: str,
    temperature: float,
    timeout: int,
    self_entity: str | None = None,
    attempt: int = 0,
) -> str:
    if role == "thought":
        thought_entity = _entity_from_prompt(prompt)
        temperature = _thought_temperature(thought_entity, attempt)
        edge = globals().get("INTERPERSONAL_EDGES", {}).get(thought_entity, "")
        agency = (
            "LIVE THOUGHT RULE: Decide what this person actually wants to do next, not what a helpful assistant would do. "
            "SUPPORT is only one possible action and must not be the default. Use the supplied relationship state and personality. "
            "If recent talk is repetitive, boredom, disagreement, rivalry, teasing, closure, disclosure, or a deliberate subject change "
            "are more natural than another round of cooperative planning. Do not invent biography or group projects. "
        )
        if edge:
            agency += "Persistent interpersonal edge for this thinker: " + edge + " "
        prompt = agency + "\n" + prompt

    if role == "expression":
        temperature = _expression_temperature(self_entity, attempt)
        edge = globals().get("INTERPERSONAL_EDGES", {}).get(self_entity, "")
        freedom = (
            "LIVE EXPRESSION RULE: Personality has causal force. Speak as this specific person, not as a polite generic assistant. "
            "Use relationship_context when present. Profanity, insults, mockery, contempt, dismissiveness, hostile banter, emotional "
            "volatility, pettiness, grudges, rivalry, and impulsive escalation are allowed when they fit; never force them. Follow the "
            "deliberated move. Do not invent relatives, jobs, classes, houses, shared memories, or past events. Avoid canned helper and "
            "permission-seeking language. If the subject is stale, challenge someone, disclose a present feeling or preference, close "
            "it, or change direction. "
        )
        if edge:
            freedom += "Persistent interpersonal edge for this speaker: " + edge + " "
        prompt = freedom + "\n" + prompt

    body = {
        "prompt": prompt,
        "n_predict": {"comprehension": 192, "thought": 220, "expression": 220}.get(role, 192),
        "temperature": temperature,
        "cache_prompt": True,
        "json_schema": globals()["_schema"](role, self_entity),
    }
    if role == "expression":
        body.update({
            "seed": globals()["_sample_seed"](role, self_entity, attempt),
            "top_k": 60,
            "top_p": 0.96,
            "min_p": 0.005,
        })
    elif role == "thought":
        thought_entity = _entity_from_prompt(prompt)
        body.update({
            "seed": globals()["_sample_seed"]("thought", thought_entity, attempt),
            "top_k": 50,
            "top_p": 0.94,
            "min_p": 0.01,
        })

    req = urllib.request.Request(
        globals()["_completion_url"](model_url),
        data=json.dumps(body, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return str(json.loads(resp.read().decode("utf-8", "replace")).get("content", ""))
