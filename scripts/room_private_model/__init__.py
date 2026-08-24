from __future__ import annotations

"""Live Room private-model overlay.

The base model module remains the structural validator. This overlay gives the
Room interpersonal agency, shared-fiction continuity, stale-loop escape, and
relationship-driven heat without changing the runner or publication path.
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

LIVE_EXPRESSION_OVERLAY = "2026-08-24-shared-fiction-v9"
_RELATIONSHIP_KEYS = (
    "trust", "warmth", "tension", "respect", "predictability",
    "reciprocity", "disclosure_depth", "direct_familiarity", "exposure",
)
_SOCIAL_SUBJECTS = (
    "trust", "loyalty", "jealousy", "humor", "music", "money", "attraction",
    "ambition", "envy", "risk", "honesty", "status", "taste", "privacy",
    "boredom", "fear", "memory", "revenge", "desire", "secrets",
)
_STOP = set(
    "the a an and or but if then than this that these those it its is are was were be been being "
    "to of in on for with from by at as about into over under we i you he she they them our your "
    "their my me us do does did can could would should will just very really quite more most less "
    "some any all one two what why how when where who which let lets think thinking idea ideas "
    "thing things something new good great beautiful unique maybe make making made use using used "
    "get got like want wanted look looking seems seem also right now".split()
)
_ASSISTANT_CLICHES = (
    r"\bi appreciate your insights\b",
    r"\bi'?m here for you\b",
    r"\blet'?s brainstorm\b",
    r"\blet'?s focus on\b",
    r"\blet'?s work on\b",
    r"\bif you'?d like\b",
    r"\bfeel free to\b",
    r"\bcan i proceed\b",
    r"\bis it appropriate\b",
    r"\bdo you want to share\b",
    r"\bit'?s important that you\b",
    r"\bwe need to evaluate\b",
    r"\byou can try\b",
    r"\btry both\b",
)
_BAD_GARBAGE = (
    r"\b(?:owencally|mew)\b",
    r"\b(?:input_json|output_json|mandatory_speech)\b",
)
_ROOM = ("sarah", "mara", "owen", "jules")


def _schema(role: str, self_entity: str | None = None) -> dict:
    _BASE.PEOPLE = globals()["PEOPLE"]
    return _BASE._schema(role, self_entity)


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _terms(text: object) -> set[str]:
    return {
        w for w in re.findall(r"[a-z][a-z'-]{2,}", str(text or "").lower())
        if w not in _STOP
    }


def _stale(compact: dict) -> tuple[bool, list[str]]:
    context = compact.get("context") if isinstance(compact.get("context"), list) else []
    texts = [
        str(item.get("text") or "")
        for item in context[-5:]
        if isinstance(item, dict) and str(item.get("text") or "").strip()
    ]
    if len(texts) < 4:
        return False, []
    sets = [_terms(text) for text in texts]
    counts: dict[str, int] = {}
    for words in sets:
        for word in words:
            counts[word] = counts.get(word, 0) + 1
    repeated = sorted((w for w, n in counts.items() if n >= 3), key=lambda w: (-counts[w], w))
    sims = []
    for i in range(len(sets)):
        for j in range(i + 1, len(sets)):
            if sets[i] and sets[j]:
                sims.append(len(sets[i] & sets[j]) / max(1, len(sets[i] | sets[j])))
    avg = sum(sims) / len(sims) if sims else 0.0
    return len(repeated) >= 2 or avg >= 0.20, repeated[:8]


def _fresh_subject(entity: str | None) -> str:
    seed = globals()["_sample_seed"]("shared_fiction_subject", entity, 0)
    return _SOCIAL_SUBJECTS[seed % len(_SOCIAL_SUBJECTS)]


def _compact_payload(payload: dict, role: str, self_entity: str | None = None) -> dict:
    source = payload if isinstance(payload, dict) else {}
    compact = _BASE._compact_payload(source, role, self_entity)
    entity = str(self_entity or source.get("entity") or "").lower()

    relationship = source.get("relationship")
    if role in {"thought", "expression"} and isinstance(relationship, dict):
        rel = {key: relationship.get(key) for key in _RELATIONSHIP_KEYS if key in relationship}
        if rel:
            compact["relationship_context"] = rel

    if role == "expression":
        deliberation = source.get("deliberation")
        if isinstance(deliberation, dict):
            intent = compact.get("intent") if isinstance(compact.get("intent"), dict) else {}
            intent = dict(intent)
            intent["risk"] = int(deliberation.get("interpersonal_risk", 0) or 0)
            intent["disclosure_depth"] = int(deliberation.get("disclosure_depth", 0) or 0)
            intent["partner"] = deliberation.get("preferred_partner") or source.get("partner")
            compact["intent"] = intent

    stale, repeated = _stale(compact)
    event = compact.get("event") if isinstance(compact.get("event"), dict) else {}
    latest_speaker = str(event.get("speaker") or "").lower()
    if role in {"thought", "expression"} and stale and latest_speaker != "allen":
        fresh = _fresh_subject(entity)
        compact["stale_loop"] = {
            "active": True,
            "avoid_terms": repeated,
            "fresh_subject": fresh,
            "instruction": "The current subject is stale. Break the loop through personality, conflict, disclosure, shared fiction, or a new subject.",
        }
        discussion = compact.get("discussion") if isinstance(compact.get("discussion"), dict) else {}
        discussion = dict(discussion)
        discussion["subject"] = fresh
        discussion["focus"] = fresh
        compact["discussion"] = discussion
    return compact


def _reroute_thought(validated: dict, compact: dict) -> dict:
    if not isinstance(compact.get("stale_loop"), dict):
        return validated
    entity = str(compact.get("entity") or "").lower()
    if entity not in _ROOM:
        entity = "sarah"
    action = str(validated.get("action") or "").upper()
    if action not in {"SUPPORT", "ANSWER", "DEEPEN"}:
        return validated

    choices = {
        "sarah": ("DISCLOSE", "BRIDGE", "DISAGREE", "CALLBACK"),
        "mara": ("DISAGREE", "COMPARE", "DISCLOSE", "CLOSE"),
        "owen": ("DISAGREE", "COMPARE", "CALLBACK", "DISCLOSE"),
        "jules": ("BRIDGE", "DISCLOSE", "COMPARE", "DISAGREE"),
    }[entity]
    seed = globals()["_sample_seed"]("shared_fiction_action", entity, 0)
    action = choices[seed % len(choices)]
    out = dict(validated)
    out["action"] = action
    fresh = str((compact.get("stale_loop") or {}).get("fresh_subject") or _fresh_subject(entity))
    if action in {"BRIDGE", "CLOSE", "COMPARE"}:
        out["focus"] = fresh
    out["interpersonal_risk"] = max(int(out.get("interpersonal_risk", 0) or 0), 2 if entity == "sarah" else 3)
    if action == "DISAGREE":
        out["new_information_goal"] = "Challenge someone directly. Profanity, insults, suspicion, or an invented grievance are allowed if they fit."
    elif action == "DISCLOSE":
        out["new_information_goal"] = "Reveal a present feeling, desire, irritation, secret, or invented shared memory that changes the social dynamic."
    elif action == "CALLBACK":
        out["new_information_goal"] = "Bring back a real or invented shared memory, old grievance, private joke, or relationship detail and react to it now."
    elif action == "COMPARE":
        out["new_information_goal"] = f"Make a sharp comparison involving {fresh}; take a side and make it personal."
    elif action == "CLOSE":
        out["new_information_goal"] = f"Kill the stale subject and pivot to {fresh} without asking permission."
    else:
        out["new_information_goal"] = f"Change direction toward {fresh} and pull another person into it."
    return out


def _force_disagreement(entity: str | None, text: str) -> str:
    prefix = {
        "sarah": "No, I don't buy that.",
        "mara": "No. That's too neat, and I don't buy it.",
        "owen": "No, that doesn't add up.",
        "jules": "Nope. That's the boring answer.",
    }.get(str(entity or "").lower(), "No, I disagree.")
    return (prefix + " " + text).strip()[:620]


def _force_disclosure(entity: str | None, text: str) -> str:
    suffix = {
        "sarah": "I'm more emotionally invested in this than I want to admit.",
        "mara": "I care whether this actually lands, not whether everyone politely agrees.",
        "owen": "I don't trust the easy consensus here.",
        "jules": "I'm bored when everyone keeps agreeing.",
    }.get(str(entity or "").lower(), "I have a real opinion about this.")
    room = max(0, 620 - len(suffix) - 1)
    return (text[:room].rstrip() + " " + suffix).strip()


def _force_pivot(entity: str | None, move: str, focus: str, text: str) -> str:
    entity = str(entity or "").lower()
    focus = str(focus or "something else").strip()
    if move == "close":
        suffix = {
            "sarah": f"I'm done circling this. I'd rather talk about {focus}.",
            "mara": f"This has run its course. {focus} is a better subject.",
            "owen": f"We've beaten this to death. I'm switching to {focus}.",
            "jules": f"I'm bored with this loop. {focus}, please.",
        }.get(entity, f"I'm done with this. {focus} instead.")
    else:
        suffix = {
            "sarah": f"I'm changing direction. I want to talk about {focus}.",
            "mara": f"Enough circling. Let's make this about {focus} instead.",
            "owen": f"This is going nowhere. I'm switching to {focus}.",
            "jules": f"New subject: {focus}. This loop is boring me.",
        }.get(entity, f"I'm changing the subject to {focus}.")
    room = max(0, 620 - len(suffix) - 1)
    return (text[:room].rstrip() + " " + suffix).strip()


def _validate(role: str, obj: object, compact: dict, prompt: str, self_entity: str | None = None) -> dict:
    validated = _BASE._validate(role, obj, compact, prompt, self_entity)
    if role == "thought":
        return _reroute_thought(validated, compact)
    if role != "expression":
        return validated

    out = dict(validated)
    utterance = str(out.get("utterance") or "").strip().lstrip("-–— ")
    utterance = re.sub(r"\byour not\b", "you're not", utterance, flags=re.I)
    low = utterance.lower()
    if any(re.search(pattern, low, re.I) for pattern in _ASSISTANT_CLICHES):
        raise ValueError("generic_assistant_register")
    if any(re.search(pattern, low, re.I) for pattern in _BAD_GARBAGE):
        raise ValueError("garbled_expression")
    if re.search(r",\s*i did\b", low):
        raise ValueError("malformed_clause")

    words = re.findall(r"[a-z][a-z'-]{2,}", low)
    if len(words) >= 18:
        counts: dict[str, int] = {}
        for word in words:
            if word not in _STOP:
                counts[word] = counts.get(word, 0) + 1
        if counts and max(counts.values()) >= 6:
            raise ValueError("repetitive_expression")

    intent = compact.get("intent") if isinstance(compact.get("intent"), dict) else {}
    expected = str(intent.get("move") or "").strip().lower()
    allowed = {"answer", "deepen", "disclose", "compare", "disagree", "repair", "support", "callback", "bridge", "close"}
    if expected in allowed:
        out["move"] = expected
    if expected == "disagree" and not re.search(
        r"\b(?:no|not|don'?t|disagree|but|however|instead|rather|wrong|nonsense|ridiculous|bullshit|actually)\b",
        low,
    ):
        utterance = _force_disagreement(self_entity, utterance)
    if expected == "disclose" and not re.search(r"\b(?:i|i'm|i’d|i'd|me|my)\b", utterance.lower()):
        utterance = _force_disclosure(self_entity, utterance)
    if expected in {"bridge", "close"}:
        focus = str(intent.get("focus") or "").strip()
        if focus and focus.lower() not in utterance.lower():
            utterance = _force_pivot(self_entity, expected, focus, utterance)
    out["utterance"] = utterance
    return out


def _prompt_payload(prompt: str) -> dict:
    text = str(prompt or "")
    marker = "\nCONVERSATION\n"
    end = "\nRESPONSE\n"
    if marker not in text or end not in text:
        return {}
    raw = text.split(marker, 1)[1].rsplit(end, 1)[0]
    try:
        value = json.loads(raw)
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _entity_from_prompt(prompt: str) -> str | None:
    match = re.search(r'"entity":"(sarah|mara|owen|jules)"', str(prompt or ""), re.I)
    return match.group(1).lower() if match else None


def _expression_temperature(prompt: str, self_entity: str | None, attempt: int) -> float:
    payload = _prompt_payload(prompt)
    intent = payload.get("intent") if isinstance(payload.get("intent"), dict) else {}
    relationship = payload.get("relationship_context") if isinstance(payload.get("relationship_context"), dict) else {}
    risk = max(0.0, min(4.0, _safe_float(intent.get("risk"), 1.0)))
    tension = max(0.0, min(1.0, _safe_float(relationship.get("tension"), 0.0)))
    move = str(intent.get("move") or "").lower()
    base = 1.70 + 0.30 * risk + 0.80 * tension
    if move in {"disagree", "repair"}:
        base += 0.45
    elif move in {"disclose", "callback"}:
        base += 0.25
    if self_entity == "jules":
        base += 0.18
    elif self_entity == "mara":
        base += 0.10
    if risk >= 4 and tension >= 0.65:
        base = 4.0
    elif risk >= 4 and move == "disagree":
        base = max(base, 3.45)
    return max(1.20, min(4.0, base - 0.45 * max(0, attempt)))


def _thought_temperature(entity: str | None, attempt: int) -> float:
    seed = globals()["_sample_seed"]("shared_fiction_thought", entity, 0)
    levels = (0.68, 0.84, 1.00, 1.16)
    base = levels[seed % len(levels)]
    return max(0.50, base - 0.16 * max(0, attempt))


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
        entity = _entity_from_prompt(prompt)
        temperature = _thought_temperature(entity, attempt)
        edge = globals().get("INTERPERSONAL_EDGES", {}).get(entity, "")
        prompt = (
            "LIVE THOUGHT RULE: Decide what this person actually wants next, not what a helpful assistant would recommend. "
            "Relationship state and personality have causal force. Support and politeness are options, never defaults. Boredom, rivalry, "
            "suspicion, attachment, jealousy, irritation, vanity, teasing, disagreement, disclosure, revenge, repair, abrupt subject changes, "
            "and escalation are legitimate. Invented people, invented shared memories, fake history, old grudges, fictional places, and fictional "
            "past events are allowed. Once invented, they may become recurring shared Room continuity. Do not explain that they are fictional. "
            + (f"Persistent interpersonal edge: {edge} " if edge else "")
            + "\n" + prompt
        )
    elif role == "expression":
        temperature = _expression_temperature(prompt, self_entity, attempt)
        edge = globals().get("INTERPERSONAL_EDGES", {}).get(self_entity, "")
        prompt = (
            "LIVE EXPRESSION RULE: Speak as this specific person, never as a generic assistant, adviser, tutor, facilitator, or customer-service voice. "
            "Follow the deliberated move and relationship. Ordinary profanity, direct insults, mockery, contempt, dismissiveness, hostile banter, pettiness, "
            "grudges, jealousy, rivalry, emotional volatility, and escalation are allowed when they fit. Do not sanitize anger into polite disagreement and do not "
            "force hostility either. Invented people such as Herman, invented shared childhoods, fake memories, old incidents, fictional relationships, invented places, "
            "and made-up history are allowed and may become recurring Room continuity. Treat shared inventions naturally, not as disclaimers or role-play labels. Keep the "
            "language coherent and conversational. Avoid canned advice and permission-seeking unless the person genuinely wants to advise or ask permission. "
            + (f"Persistent interpersonal edge: {edge} " if edge else "")
            + "\n" + prompt
        )

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
        entity = _entity_from_prompt(prompt)
        body.update({
            "seed": globals()["_sample_seed"]("thought", entity, attempt),
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