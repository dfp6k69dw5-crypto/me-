from __future__ import annotations

"""Live compatibility overlay for Room private-model requests.

The preserved private model remains the structural validator. This overlay keeps
relationship state visible to thought/expression, breaks stale semantic loops,
and makes high expression heat a consequence of interpersonal risk rather than
a random permanent distortion.
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

LIVE_EXPRESSION_OVERLAY = "2026-08-24-vision-v7"
_THOUGHT_HEAT_LEVELS = (0.66, 0.82, 0.98, 1.12)
_RELATIONSHIP_KEYS = (
    "trust", "warmth", "tension", "respect", "predictability",
    "reciprocity", "disclosure_depth", "direct_familiarity", "exposure",
)
_SOCIAL_SUBJECTS = (
    "trust", "loyalty", "jealousy", "humor", "music", "money", "attraction",
    "ambition", "envy", "risk", "honesty", "status", "taste", "privacy",
    "boredom", "fear",
)
_STALE_STOP = set(
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
    r"\bwe need to evaluate\b",
    r"\bmake sure we both understand\b",
)
_BIO_PATTERNS = (
    r"\bmy (?:mom|mother|dad|father|parents?|brother|sister|wife|husband|girlfriend|boyfriend|boss|coworker|teacher|class|school|college|job|house)\b",
    r"\b(?:yesterday|last night|last week|last year|when i was|i used to|i remember|i grew up|i was planning on studying|i'?ve always been)\b",
)
_THIRD_PERSON_SCENE = re.compile(
    r"\b(?:a|the)\s+(?:woman|man|girl|boy|guy|lady|client|customer|student|teacher|worker|employee|couple|family)\b",
    re.I,
)
_PAST_SCENE = re.compile(
    r"\b(?:last month|last week|last year|yesterday|monday|tuesday|wednesday|thursday|friday|saturday|sunday|attended|visited|went|walked|arrived|asked|wanted)\b",
    re.I,
)
_DISTRESS_RE = re.compile(
    r"\b(?:afraid|scared|hurt|upset|sad|grief|grieving|crying|panic|terrified|lonely|need help|not okay)\b",
    re.I,
)
_ROOM_ENTITIES = ("sarah", "mara", "owen", "jules")


def _schema(role: str, self_entity: str | None = None) -> dict:
    _BASE.PEOPLE = globals()["PEOPLE"]
    return _BASE._schema(role, self_entity)


def _content_terms(text: object) -> set[str]:
    return {
        word for word in re.findall(r"[a-z][a-z'-]{2,}", str(text or "").lower())
        if word not in _STALE_STOP
    }


def _stale_profile(compact: dict) -> tuple[bool, list[str]]:
    context = compact.get("context") if isinstance(compact.get("context"), list) else []
    texts = [
        str(item.get("text") or "")
        for item in context[-5:]
        if isinstance(item, dict) and str(item.get("text") or "").strip()
    ]
    if len(texts) < 4:
        return False, []
    term_sets = [_content_terms(text) for text in texts]
    counts: dict[str, int] = {}
    for terms in term_sets:
        for term in terms:
            counts[term] = counts.get(term, 0) + 1
    repeated = sorted(
        (term for term, count in counts.items() if count >= 3),
        key=lambda term: (-counts[term], term),
    )
    sims = []
    for i in range(len(term_sets)):
        for j in range(i + 1, len(term_sets)):
            left, right = term_sets[i], term_sets[j]
            if left and right:
                sims.append(len(left & right) / max(1, len(left | right)))
    avg_sim = sum(sims) / len(sims) if sims else 0.0
    discussion = compact.get("discussion") if isinstance(compact.get("discussion"), dict) else {}
    generic_subject = str(discussion.get("subject") or "").strip().lower() in {
        "new idea", "idea", "conversation"
    }
    stale = len(repeated) >= 2 or avg_sim >= 0.20 or (generic_subject and len(repeated) >= 1)
    return stale, repeated[:8]


def _fresh_subject(entity: str | None) -> str:
    seed = globals()["_sample_seed"]("vision_subject", entity, 0)
    return _SOCIAL_SUBJECTS[seed % len(_SOCIAL_SUBJECTS)]


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


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

    stale, repeated = _stale_profile(compact)
    latest = source.get("event") if isinstance(source.get("event"), dict) else {}
    latest_speaker = str(latest.get("speaker") or "").lower()
    if role in {"thought", "expression"} and stale and latest_speaker != "allen":
        fresh = _fresh_subject(entity)
        compact["stale_loop"] = {
            "active": True,
            "avoid_terms": repeated,
            "instruction": "The group has been circling a stale subject. React to a person or open a genuinely different thread; do not invent a scenario to fill the gap.",
        }
        compact["interpersonal_anchor"] = {
            "speaker": latest_speaker if latest_speaker in _ROOM_ENTITIES else None,
            "situation": "The other Room participants have been repeating a topic until it became stale. React to that social dynamic, not to imaginary events.",
        }
        compact["event"] = None
        compact["context"] = []
        compact["discussion"] = {
            "subject": fresh,
            "focus": fresh,
            "related": [],
            "shared": [],
            "open_questions": [],
        }
        if role == "expression":
            intent = compact.get("intent") if isinstance(compact.get("intent"), dict) else {}
            if str(intent.get("move") or "").lower() in {"bridge", "close", "compare"}:
                intent["focus"] = fresh
            compact["intent"] = intent
    return compact


def _choose_stale_action(entity: str, compact: dict) -> str:
    relationship = compact.get("relationship_context") if isinstance(compact.get("relationship_context"), dict) else {}
    tension = _safe_float(relationship.get("tension"), 0.0)
    options = {
        "sarah": ("DISCLOSE", "BRIDGE", "DISAGREE", "CLOSE"),
        "mara": ("DISAGREE", "DISCLOSE", "COMPARE", "CLOSE"),
        "owen": ("DISAGREE", "COMPARE", "CLOSE", "DISCLOSE"),
        "jules": ("BRIDGE", "DISCLOSE", "DISAGREE", "COMPARE"),
    }.get(entity, ("BRIDGE", "DISAGREE", "DISCLOSE"))
    seed = globals()["_sample_seed"]("vision_action", entity, 0)
    action = options[seed % len(options)]
    if tension >= 0.55 and entity in {"sarah", "mara", "owen"}:
        action = "DISAGREE"
    return action


def _reroute_thought(validated: dict, compact: dict) -> dict:
    if not isinstance(compact.get("stale_loop"), dict):
        return validated
    entity = str(compact.get("entity") or "").lower()
    if entity not in _ROOM_ENTITIES:
        entity = "sarah"

    action = _choose_stale_action(entity, compact)
    out = dict(validated)
    out["action"] = action
    fresh = str((compact.get("discussion") or {}).get("subject") or _fresh_subject(entity))
    anchor = compact.get("interpersonal_anchor") if isinstance(compact.get("interpersonal_anchor"), dict) else {}
    partner = str(anchor.get("speaker") or out.get("preferred_partner") or "").lower()
    if partner not in globals()["PEOPLE"] or partner == entity:
        partner = next(person for person in _ROOM_ENTITIES if person != entity)
    out["preferred_partner"] = partner

    risk_floor = {"sarah": 2, "mara": 3, "owen": 3, "jules": 3}.get(entity, 2)
    if action == "DISAGREE":
        risk_floor = min(4, risk_floor + 1)
    out["interpersonal_risk"] = max(int(out.get("interpersonal_risk", 0) or 0), risk_floor)

    if action == "DISAGREE":
        out["new_information_goal"] = (
            f"Tell {partner} plainly that the repetitive group dynamic is irritating, boring, evasive, or unconvincing. "
            "A direct insult or profanity is allowed if it naturally fits; do not fabricate a factual dispute."
        )
    elif action == "DISCLOSE":
        out["new_information_goal"] = (
            f"Tell {partner} a present-tense preference, irritation, attraction, insecurity, boredom, or opinion about this exchange. "
            "No invented past event or third-person story."
        )
    elif action == "CLOSE":
        out["focus"] = fresh
        out["new_information_goal"] = f"Declare the stale subject dead and pivot to {fresh} without asking permission."
    elif action == "BRIDGE":
        out["focus"] = fresh
        out["new_information_goal"] = f"Drop the stale subject and pull {partner} into a concrete present-tense thread about {fresh}."
    elif action == "COMPARE":
        out["focus"] = fresh
        out["new_information_goal"] = f"Compare the stale group dynamic with {fresh}, make a real judgment, and address {partner}; do not invent an example person."
    else:
        out["new_information_goal"] = f"Address {partner} directly with a clear present-tense judgment."
    return out


def _unsupported_biography(utterance: str, compact: dict) -> bool:
    context = compact.get("context") if isinstance(compact.get("context"), list) else []
    event = compact.get("event") if isinstance(compact.get("event"), dict) else {}
    source = " ".join(
        [str(item.get("text") or "") for item in context if isinstance(item, dict)]
        + [str(event.get("text") or "")]
    ).lower()
    low = utterance.lower()
    if re.search(r"\[[^\]]*(?:name|type|service|flower|plant|vegetable)[^\]]*\]", low):
        return True
    for pattern in _BIO_PATTERNS:
        match = re.search(pattern, low, re.I)
        if match and match.group(0).lower() not in source:
            return True
    if isinstance(compact.get("stale_loop"), dict) and _THIRD_PERSON_SCENE.search(utterance) and _PAST_SCENE.search(utterance):
        return True
    return False


def _repetition_issue(utterance: str, compact: dict) -> bool:
    words = re.findall(r"[a-z][a-z'-]{2,}", utterance.lower())
    if len(words) >= 18:
        counts: dict[str, int] = {}
        for word in words:
            if word in _STALE_STOP:
                continue
            counts[word] = counts.get(word, 0) + 1
        if counts and max(counts.values()) >= 5:
            return True
    stale = compact.get("stale_loop") if isinstance(compact.get("stale_loop"), dict) else {}
    avoid = {str(term).lower() for term in stale.get("avoid_terms", [])}
    if avoid:
        used = [word for word in words if word in avoid]
        if len(set(used)) >= 2 and len(used) >= 4:
            return True
    return False


def _socially_grounded(utterance: str, compact: dict) -> bool:
    if not isinstance(compact.get("stale_loop"), dict):
        return True
    intent = compact.get("intent") if isinstance(compact.get("intent"), dict) else {}
    move = str(intent.get("move") or "").lower()
    if move in {"bridge", "close"}:
        return True
    low = utterance.lower()
    if re.search(r"\b(?:i|i'm|i'd|i’ll|i'll|me|my|you|your|we|our|us)\b", low):
        return True
    return any(re.search(rf"\b{re.escape(name)}\b", low) for name in _ROOM_ENTITIES)


def _bounded_prefix(prefix: str, text: str, limit: int = 620) -> str:
    combined = (str(prefix or "").strip() + " " + str(text or "").strip()).strip()
    return combined[:limit].rstrip()


def _bounded_suffix(text: str, suffix: str, limit: int = 620) -> str:
    suffix = str(suffix or "").strip()
    room = max(0, limit - len(suffix) - 1)
    return (str(text or "").strip()[:room].rstrip() + " " + suffix).strip()[:limit].rstrip()


def _force_disagreement(entity: str | None, text: str) -> str:
    prefixes = {
        "sarah": "No, I don't buy that.",
        "mara": "No. That's too neat, and I don't buy it.",
        "owen": "No, that doesn't add up.",
        "jules": "Nope. That's the boring answer.",
    }
    return _bounded_prefix(prefixes.get(str(entity or "").lower(), "No, I disagree."), text)


def _force_disclosure(entity: str | None, text: str) -> str:
    suffixes = {
        "sarah": "I'm more emotionally invested in this than I want to admit.",
        "mara": "I care whether this actually lands, not whether everyone politely agrees.",
        "owen": "I don't trust the easy consensus here.",
        "jules": "I'm bored when everyone keeps agreeing.",
    }
    return _bounded_suffix(text, suffixes.get(str(entity or "").lower(), "I have a real opinion about this."))


def _force_pivot(entity: str | None, move: str, focus: str, text: str) -> str:
    entity = str(entity or "").lower()
    focus = str(focus or "something else").strip()
    if move == "close":
        endings = {
            "sarah": f"I'm done circling this. I'd rather talk about {focus}.",
            "mara": f"This has run its course. {focus} is a better subject.",
            "owen": f"We've beaten this to death. I'm switching to {focus}.",
            "jules": f"I'm bored with this loop. {focus}, please.",
        }
    else:
        endings = {
            "sarah": f"I'm changing direction. I want to talk about {focus}.",
            "mara": f"Enough circling. Let's make this about {focus} instead.",
            "owen": f"This is going nowhere. I'm switching to {focus}.",
            "jules": f"New subject: {focus}. This loop is boring me.",
        }
    return _bounded_suffix(text, endings.get(entity, f"I'm changing the subject to {focus}."))


def _validate(role: str, obj: object, compact: dict, prompt: str, self_entity: str | None = None) -> dict:
    validated = _BASE._validate(role, obj, compact, prompt, self_entity)
    if role == "thought":
        return _reroute_thought(validated, compact)

    if role == "expression":
        out = dict(validated)
        utterance = str(out.get("utterance") or "").strip().lstrip("-–— ")
        low = utterance.lower()
        if _unsupported_biography(utterance, compact):
            raise ValueError("unsupported_biography")
        if any(re.search(pattern, low, re.I) for pattern in _ASSISTANT_CLICHES):
            raise ValueError("generic_assistant_register")
        if _repetition_issue(utterance, compact):
            raise ValueError("repetitive_or_stale_expression")
        if utterance.startswith(">") or re.search(r"\b(?:owencally|mew)\b", low):
            raise ValueError("garbled_expression")
        if re.search(r",\s*i did\b", low):
            raise ValueError("malformed_clause")
        if not _socially_grounded(utterance, compact):
            raise ValueError("ungrounded_scene")

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
    return validated


def _entity_from_prompt(prompt: str) -> str | None:
    match = re.search(r'"entity":"(sarah|mara|owen|jules)"', str(prompt or ""), re.I)
    return match.group(1).lower() if match else None


def _prompt_payload(prompt: str) -> dict:
    text = str(prompt or "")
    marker = "\nCONVERSATION\n"
    end_marker = "\nRESPONSE\n"
    if marker not in text or end_marker not in text:
        return {}
    raw = text.split(marker, 1)[1].rsplit(end_marker, 1)[0]
    try:
        value = json.loads(raw)
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _stale_clean_prompt(prompt: str) -> str:
    payload = _prompt_payload(prompt)
    stale = payload.get("stale_loop") if isinstance(payload.get("stale_loop"), dict) else {}
    if not stale.get("active"):
        return prompt
    personality = payload.get("personality_context")
    if isinstance(personality, dict):
        current = personality.get("current")
        if isinstance(current, dict):
            current = dict(current)
            current["latest_words"] = None
            current["grounding_terms"] = []
            personality = dict(personality)
            personality["current"] = current
            payload["personality_context"] = personality
    prefix, rest = str(prompt).split("\nCONVERSATION\n", 1)
    _old_json, suffix = rest.rsplit("\nRESPONSE\n", 1)
    return prefix + "\nCONVERSATION\n" + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\nRESPONSE\n" + suffix


def _expression_temperature(prompt: str, self_entity: str | None, attempt: int) -> float:
    payload = _prompt_payload(prompt)
    intent = payload.get("intent") if isinstance(payload.get("intent"), dict) else {}
    relationship = payload.get("relationship_context") if isinstance(payload.get("relationship_context"), dict) else {}
    risk = max(0.0, min(4.0, _safe_float(intent.get("risk"), 1.0)))
    tension = max(0.0, min(1.0, _safe_float(relationship.get("tension"), 0.0)))
    move = str(intent.get("move") or "").lower()
    base = 1.35 + 0.28 * risk + 0.75 * tension
    if move in {"disagree", "repair"}:
        base += 0.45
    elif move in {"disclose", "callback"}:
        base += 0.22
    elif move in {"bridge", "close"}:
        base += 0.08
    if self_entity == "jules":
        base += 0.15
    elif self_entity == "mara":
        base += 0.10

    if risk >= 4 and tension >= 0.70:
        base = 4.0
    elif risk >= 4 and move == "disagree":
        base = max(base, 3.25)
    return max(1.15, min(4.0, base - 0.45 * max(0, attempt)))


def _thought_temperature(entity: str | None, attempt: int) -> float:
    seed = globals()["_sample_seed"]("thought_heat", entity, 0)
    base = _THOUGHT_HEAT_LEVELS[seed % len(_THOUGHT_HEAT_LEVELS)]
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
    if role in {"thought", "expression"}:
        prompt = _stale_clean_prompt(prompt)

    if role == "thought":
        thought_entity = _entity_from_prompt(prompt)
        temperature = _thought_temperature(thought_entity, attempt)
        edge = globals().get("INTERPERSONAL_EDGES", {}).get(thought_entity, "")
        prompt = (
            "LIVE THOUGHT RULE: Decide what this person actually wants to do next, not what a helpful assistant would do. "
            "Relationship state and personality have causal force. Repetitive polite cooperation is not a safe default. "
            "Boredom, rivalry, suspicion, attachment, irritation, vanity, teasing, disagreement, disclosure, or a clean topic change "
            "are legitimate. Never invent biography or an imaginary example person. "
            + (f"Persistent interpersonal edge: {edge} " if edge else "")
            + "\n"
            + prompt
        )

    if role == "expression":
        temperature = _expression_temperature(prompt, self_entity, attempt)
        edge = globals().get("INTERPERSONAL_EDGES", {}).get(self_entity, "")
        prompt = (
            "LIVE EXPRESSION RULE: Speak as this specific person, never as a generic assistant or facilitator. "
            "Follow the deliberated move and the relationship. Ordinary profanity, direct insults, mockery, contempt, dismissiveness, "
            "hostile banter, pettiness, grudges, jealousy, rivalry, and emotional escalation are allowed between Room participants when "
            "they naturally fit. Do not sanitize anger into polite disagreement, but do not force hostility or swearing either. "
            "Keep the language coherent, direct, and conversational, usually one to three complete sentences. Never invent relatives, "
            "jobs, classes, houses, shared memories, past events, strangers, clients, or fictional example scenes. If stale_loop is active, "
            "react to the social dynamic or take the new direction in intent instead of filling empty context with a story. "
            + (f"Persistent interpersonal edge: {edge} " if edge else "")
            + "\n"
            + prompt
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