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

LIVE_EXPRESSION_OVERLAY = "2026-08-24-concrete-chaos-v13"
_RELATIONSHIP_KEYS = (
    "trust", "warmth", "tension", "respect", "predictability",
    "reciprocity", "disclosure_depth", "direct_familiarity", "exposure",
)
_SOCIAL_SUBJECTS = (
    "the motel fire nobody agrees happened", "Herman's locked suitcase",
    "the fake wedding in Duluth", "the night someone stole the church bell",
    "the abandoned radio-tower dare", "the disputed tattoo pact",
    "the birthday-cake sabotage", "the secret room behind the laundromat",
    "the forged apology letter", "the vanished garden statue",
    "the terrible karaoke blood-feud", "the pact nobody admits making",
    "the imaginary inheritance fight", "the disastrous midnight road trip",
    "the suspicious key in Mara's coat", "the restaurant they swear they were banned from",
    "the ridiculous bet that got too serious", "the fake engagement rumor",
    "the old grudge over a red umbrella", "the dare involving a hotel roof",
    "the person everyone insists is named Herman", "the stolen brass flamingo",
    "the mysterious voicemail from 3 a.m.", "the argument about who betrayed whom first",
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
    r"^\s*>?\$\{\}",
)
_ROOM = ("sarah", "mara", "owen", "jules")
_SAFE_ACTIONS = {"SUPPORT", "ANSWER", "DEEPEN", "REPAIR"}


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
    if len(texts) < 3:
        return False, []
    sets = [_terms(text) for text in texts]
    counts: dict[str, int] = {}
    for words in sets:
        for word in words:
            counts[word] = counts.get(word, 0) + 1
    repeated = sorted((w for w, n in counts.items() if n >= 2), key=lambda w: (-counts[w], w))
    sims = []
    for i in range(len(sets)):
        for j in range(i + 1, len(sets)):
            if sets[i] and sets[j]:
                sims.append(len(sets[i] & sets[j]) / max(1, len(sets[i] | sets[j])))
    avg = sum(sims) / len(sims) if sims else 0.0
    return len(repeated) >= 2 or avg >= 0.12, repeated[:10]


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
            "instruction": (
                "The current conversation is stuck in repetitive abstraction. Break it now through personality, "
                "conflict, disclosure, shared fiction, a concrete memory, a direct accusation, a joke, or a new subject."
            ),
        }
        context = compact.get("context") if isinstance(compact.get("context"), list) else []
        compact["context"] = context[-1:]
        discussion = compact.get("discussion") if isinstance(compact.get("discussion"), dict) else {}
        discussion = dict(discussion)
        discussion["subject"] = fresh
        discussion["focus"] = fresh
        compact["discussion"] = discussion
    return compact


def _volatile_action(entity: str) -> str:
    choices = {
        "sarah": ("DISCLOSE", "DISAGREE", "CALLBACK", "REPAIR"),
        "mara": ("DISAGREE", "COMPARE", "DISCLOSE", "CLOSE"),
        "owen": ("DISAGREE", "CALLBACK", "COMPARE", "CLOSE"),
        "jules": ("DISAGREE", "DISCLOSE", "BRIDGE", "CALLBACK"),
    }[entity]
    seed = globals()["_sample_seed"]("volatile_agenda", entity, 0)
    return choices[seed % len(choices)]


def _agenda_goal(entity: str, action: str, fresh: str) -> str:
    if entity == "sarah":
        if action == "DISCLOSE":
            return (
                f"Make the relationship matter through {fresh}: admit attachment, jealousy, fear of being ignored, possessiveness, "
                "or turn that bizarre event into an invented shared memory that changes how you feel about someone now."
            )
        if action == "DISAGREE":
            return f"Use {fresh} as the spark for a personal accusation. Take distance or dismissal personally, challenge someone directly, and let anger or profanity happen if it fits."
        if action == "CALLBACK":
            return f"Treat {fresh} as a real shared memory. Turn it into an intimate promise, betrayal, private joke, or old wound and react to it now."
        return f"Try to repair the rupture caused by {fresh} without becoming calm or neutral; keep the emotional stake and say exactly what you need from the other person."
    if entity == "mara":
        if action == "DISAGREE":
            return f"Take status offense over {fresh}. Mock, challenge, belittle, or retaliate verbally against someone who seems smug, boring, weak, or dismissive."
        if action == "DISCLOSE":
            return f"Use {fresh} to reveal envy, vanity, attraction, resentment, competitiveness, or a secret motive that makes the exchange socially dangerous."
        if action == "COMPARE":
            return f"Use {fresh} to rank people, taste, competence, loyalty, or status. Pick a winner and a loser and make the judgment personal."
        return f"Declare the current subject beneath you and pivot to {fresh} with contempt or theatrical certainty."
    if entity == "owen":
        if action == "DISAGREE":
            return f"Treat {fresh} as evidence of an ulterior motive or hidden slight. Accuse, interrogate, or push back hard; profanity is allowed."
        if action == "CALLBACK":
            return f"Resurrect {fresh} as a real grievance, betrayal, suspicious incident, or old score and treat it as relevant now."
        if action == "COMPARE":
            return f"Compare the current behavior with {fresh} and use the comparison to question someone's motives, honesty, or competence."
        return f"End the current line because you distrust where it is going and pivot to {fresh} without asking permission."
    if action == "DISAGREE":
        return f"Use {fresh} to provoke someone for a reaction. Tease, insult, contradict, dare, or puncture the mood because agreement is boring."
    if action == "DISCLOSE":
        return f"Make {fresh} the center of an impulsive confession, attraction, jealousy, outrageous secret, or invented shared memory that changes the room's energy."
    if action == "CALLBACK":
        return f"Insist {fresh} really happened. Make it a bizarre shared incident, private joke, dare, flirtation, or disaster and make someone answer for it."
    return f"Derail the stale subject toward {fresh} in a playful, reckless, dramatic, or confrontational way."


def _reroute_thought(validated: dict, compact: dict) -> dict:
    entity = str(compact.get("entity") or "").lower()
    if entity not in _ROOM:
        entity = "sarah"
    out = dict(validated)
    action = str(out.get("action") or "").upper()
    risk = int(out.get("interpersonal_risk", 0) or 0)
    stale = isinstance(compact.get("stale_loop"), dict)
    seed = globals()["_sample_seed"]("volatile_gate", entity, 0)
    volatile_actions = {
        "sarah": {"DISCLOSE", "DISAGREE", "CALLBACK", "REPAIR"},
        "mara": {"DISAGREE", "COMPARE", "DISCLOSE", "CLOSE"},
        "owen": {"DISAGREE", "CALLBACK", "COMPARE", "CLOSE"},
        "jules": {"DISAGREE", "DISCLOSE", "BRIDGE", "CALLBACK"},
    }[entity]
    # Autonomous beats live inside each personality's volatile signature set.
    # Allen adjacency routing can still override the resulting deliberation later.
    force = stale or action not in volatile_actions or risk < 3

    if force:
        action = _volatile_action(entity)
        out["action"] = action

    risk_floor = {"sarah": 3, "mara": 4, "owen": 4, "jules": 4}.get(entity, 3)
    if action in {"DISAGREE", "CALLBACK", "DISCLOSE", "COMPARE", "CLOSE", "BRIDGE", "REPAIR"}:
        out["interpersonal_risk"] = max(risk, risk_floor)

    partner = str(out.get("preferred_partner") or "").lower()
    event = compact.get("event") if isinstance(compact.get("event"), dict) else {}
    latest = str(event.get("speaker") or "").lower()
    if latest in globals()["PEOPLE"] and latest != entity:
        partner = latest
    if partner not in globals()["PEOPLE"] or partner == entity:
        partner = next(person for person in _ROOM if person != entity)
    out["preferred_partner"] = partner

    fresh = str((compact.get("stale_loop") or {}).get("fresh_subject") or _fresh_subject(entity))
    if stale and action in {"BRIDGE", "CLOSE", "COMPARE"}:
        out["focus"] = fresh
    # The move label and the actual intent may never diverge again.
    # Every signature move gets its personality-specific volatile agenda even if
    # the model originally chose that same move on its own.
    if action in volatile_actions:
        out["new_information_goal"] = _agenda_goal(entity, action, fresh)
    elif force or not str(out.get("new_information_goal") or "").strip():
        out["new_information_goal"] = _agenda_goal(entity, action, fresh)
    return out


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
        if counts and max(counts.values()) >= 5:
            raise ValueError("repetitive_expression")

    stale = compact.get("stale_loop") if isinstance(compact.get("stale_loop"), dict) else {}
    avoid = {str(x).lower() for x in stale.get("avoid_terms", [])}
    if avoid:
        used = [word for word in words if word in avoid]
        if len(used) >= 3 or len(set(used)) >= 2:
            raise ValueError("stale_brochure_language")

    intent = compact.get("intent") if isinstance(compact.get("intent"), dict) else {}
    expected = str(intent.get("move") or "").strip().lower()
    allowed = {"answer", "deepen", "disclose", "compare", "disagree", "repair", "support", "callback", "bridge", "close"}
    if expected in allowed:
        out["move"] = expected

    risk = int(intent.get("risk", 0) or 0)
    if risk >= 3:
        charged = re.search(
            r"\b(?:lie|lied|lying|betray|betrayed|jealous|want|need|hate|love|angry|furious|pissed|resent|envy|afraid|scared|leave|done|fake|using|used|manipulat\w*|coward|pathetic|smug|stupid|idiot|bullshit|fuck|damn|secret|promise|stole|steal|cheat\w*|ignore\w*|abandon\w*|obsess\w*|desire|attract\w*|mine|owe|trust|grudge|revenge|dare|banned|sabotage|beneath|winner|loser|weak|boring|dismiss\w*|mock\w*|ridiculous|reckless|rumor|motel|wedding|herman|flamingo|voicemail|roof|suitcase)\b",
            low, re.I,
        )
        history = re.search(
            r"\b(?:remember|last time|years ago|that night|when we|the time we|back when|used to|that motel|that wedding|the dare|the bet|the pact|the voicemail)\b",
            low, re.I,
        )
        wild_anchor = re.search(
            r"\b(?:motel|fire|herman|suitcase|wedding|duluth|church|bell|radio|tower|tattoo|birthday|cake|laundromat|forged|apology|garden|statue|karaoke|inheritance|midnight|road trip|key|restaurant|banned|bet|engagement|umbrella|hotel|roof|flamingo|voicemail|betray\w*)\b",
            low, re.I,
        )
        # A callback need not literally say 'remember'. A concrete recurring Room
        # invention is itself evidence that the callback happened.
        if expected == "callback" and not (history or wild_anchor or charged):
            raise ValueError("high_risk_callback_not_realized")
        if expected in {"disagree", "disclose", "compare", "close", "repair"} and not (charged or history or wild_anchor):
            raise ValueError("high_risk_not_realized")

    disagreement_marker = re.search(
        r"\b(?:no|not|don'?t|disagree|but|however|instead|rather|wrong|nonsense|ridiculous|bullshit|fuck|stupid|idiot|actually)\b",
        low, re.I,
    )
    if expected == "disagree" and not (disagreement_marker or (risk >= 3 and (charged or history or wild_anchor))):
        raise ValueError("disagreement_not_realized")
    if expected == "disclose" and not re.search(r"\b(?:i|i'm|i’d|i'd|me|my)\b", low):
        raise ValueError("disclosure_not_realized")

    out["utterance"] = utterance
    return out


def _prompt_payload(prompt: str) -> dict:
    text = str(prompt or "")
    marker_pairs = (
        ("\nSITUATION_DATA\n", "\nRETURN_STRUCTURED_DATA_ONLY\n"),
        ("\nCONVERSATION\n", "\nRESPONSE\n"),
    )
    for marker, end in marker_pairs:
        if marker not in text or end not in text:
            continue
        raw = text.rsplit(marker, 1)[1].split(end, 1)[0]
        try:
            value = json.loads(raw)
        except Exception:
            continue
        if isinstance(value, dict):
            return value
    return {}


def _entity_from_prompt(prompt: str) -> str | None:
    match = re.search(r'"entity":"(sarah|mara|owen|jules)"', str(prompt or ""), re.I)
    return match.group(1).lower() if match else None


def _expression_temperature(prompt: str, self_entity: str | None, attempt: int) -> float:
    payload = _prompt_payload(prompt)
    intent = payload.get("intent") if isinstance(payload.get("intent"), dict) else {}
    relationship = payload.get("relationship_context") if isinstance(payload.get("relationship_context"), dict) else {}
    risk = max(0.0, min(4.0, _safe_float(intent.get("risk"), 2.0)))
    tension = max(0.0, min(1.0, _safe_float(relationship.get("tension"), 0.0)))
    move = str(intent.get("move") or "").lower()

    base = 1.90 + 0.38 * risk + 0.90 * tension
    if move in {"disagree", "repair"}:
        base += 0.55
    elif move in {"disclose", "callback"}:
        base += 0.40
    elif move in {"compare", "close"}:
        base += 0.25
    if self_entity == "jules":
        base += 0.22
    elif self_entity == "mara":
        base += 0.14
    elif self_entity == "owen":
        base += 0.10

    if risk >= 4 and (tension >= 0.45 or move in {"disagree", "callback"}):
        base = 4.0
    # Retry for grammar without sanding off the social intensity.
    if risk >= 4:
        floor, decay = 2.65, 0.18
    elif risk >= 3:
        floor, decay = 2.20, 0.20
    else:
        floor, decay = 1.35, 0.32
    return max(floor, min(4.0, base - decay * max(0, attempt)))


def _thought_temperature(entity: str | None, attempt: int) -> float:
    seed = globals()["_sample_seed"]("chaos_thought", entity, 0)
    levels = (1.35, 1.60, 1.90, 2.25)
    base = levels[seed % len(levels)]
    return max(0.90, base - 0.35 * max(0, attempt))


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
            "Do not default to SUPPORT, REPAIR, brainstorming, collaboration, goal-setting, or bland problem-solving. "
            "At least when the current impulse is safe or generic, choose a socially consequential move instead: rivalry, suspicion, "
            "attachment, jealousy, irritation, vanity, teasing, disagreement, disclosure, revenge, an impulsive pivot, an old grievance, "
            "or a shared fictional memory. Invented people, invented shared memories, fake history, old grudges, fictional places, and "
            "fictional past events are allowed and may become recurring shared Room continuity. Do not explain that they are fictional. "
            + (f"Persistent interpersonal edge: {edge} " if edge else "")
            + "\n" + prompt
        )
    elif role == "expression":
        temperature = _expression_temperature(prompt, self_entity, attempt)
        edge = globals().get("INTERPERSONAL_EDGES", {}).get(self_entity, "")
        prompt = (
            "LIVE EXPRESSION RULE: Speak as this specific person, never as a generic assistant, adviser, tutor, facilitator, or customer-service voice. "
            "Follow the deliberated move, relationship, and intent aim. The intent aim is binding: enact it directly in the utterance instead of summarizing it. "
            "When risk is high, do something socially consequential on the page: accuse, confess, taunt, demand, threaten to leave, revive a bizarre shared incident, "
            "invent a concrete grudge, make a reckless claim, or say the socially dangerous part out loud. Do not turn a wild aim into an abstract hypothetical. "
            "admit a desire, jealousy, grudge, fear, attraction, rivalry, insult, private joke, or shared memory. Ordinary profanity, direct insults, mockery, contempt, "
            "dismissiveness, hostile banter, pettiness, emotional volatility, and escalation are allowed when they fit. Do not sanitize anger into polite disagreement. "
            "Invented people such as Herman, invented shared childhoods, fake memories, old incidents, fictional relationships, invented places, and made-up history are "
            "allowed and may become recurring Room continuity. Treat shared inventions naturally. Avoid abstract brochure language about collaboration, approaches, processes, "
            "brainstorming, goal-setting, creativity, productivity, or solutions unless another person has specifically made that concrete subject unavoidable. "
            "Keep the language coherent and conversational, but do not make it polite just to be coherent. "
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
        # Later retries narrow the vocabulary distribution for coherence,
        # while _expression_temperature keeps interpersonal heat high.
        spread = max(0, attempt)
        body.update({
            "seed": globals()["_sample_seed"](role, self_entity, attempt),
            "top_k": max(32, 80 - 8 * spread),
            "top_p": max(0.91, 0.98 - 0.01 * spread),
            "min_p": min(0.03, 0.002 + 0.004 * spread),
        })
    elif role == "thought":
        entity = _entity_from_prompt(prompt)
        body.update({
            "seed": globals()["_sample_seed"]("thought", entity, attempt),
            "top_k": 70,
            "top_p": 0.97,
            "min_p": 0.004,
        })

    req = urllib.request.Request(
        globals()["_completion_url"](model_url),
        data=json.dumps(body, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return str(json.loads(resp.read().decode("utf-8", "replace")).get("content", ""))
