from __future__ import annotations

import re
from collections import Counter

ORDER = ("sarah", "mara", "owen", "jules")
REL_KEYS = (
    "exposure", "direct_familiarity", "trust", "predictability",
    "reciprocity", "warmth", "respect", "disclosure_depth", "tension",
)

GENERIC_WORDS = {
    "the","and","but","for","not","was","are","you","your","our","out","too","did","can","got","one","once","that","this","with","from","have","has","had","just","what","when","where","there","they","them","then","than","about","would","could","should","into","only","because","been","being","does","doing","done","will","well","yeah","okay","also","still","maybe","kind","sort","thing","things","something","anything","someone","everyone","say","saying","think","thinking","thought","know","knowing","mean","means","seem","seems","want","wants","wanted","make","making","made","start","starting","started","try","trying","tried","good","great","nice","sure","right","actually","probably","pretty","little","much","many","few","around","again","already","even","ever","never","always","often","sometimes","today","tonight","tomorrow","yesterday","different","together","interesting","going","everything",
    "really","people","person","conversation","talk","feel","feeling","answer","question","makes","like","their","which","while","more","very","usually",
}


def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, float(x)))


def words(text):
    out = []
    for w in re.findall(r"[a-z][a-z'-]{2,}", str(text or "").lower()):
        w = w.strip("'-")
        if w.endswith("'s"):
            w = w[:-2]
        if w and w not in GENERIC_WORDS and w not in out:
            out.append(w)
    return out


def rel_template(legacy_familiarity=0.02):
    legacy = clamp(legacy_familiarity)
    return {
        "legacy_familiarity": legacy,
        "exposure": min(0.75, 0.05 + 0.70 * legacy),
        "direct_familiarity": 0.08,
        "trust": 0.10,
        "predictability": 0.12,
        "reciprocity": 0.08,
        "warmth": 0.12,
        "respect": 0.12,
        "disclosure_depth": 0.0,
        "tension": 0.0,
        "direct_turns": 0,
        "observed_turns": 0,
        "repair_attempts": 0,
        "repair_successes": 0,
        "last_direct_cycle": None,
        "shared_references": [],
        "events": [],
        "reports": [],
    }


def migrate_minds(minds):
    minds = minds or {"entities": {}}
    entities = minds.setdefault("entities", {})
    for e in ORDER:
        ent = entities.setdefault(e, {})
        people = ent.setdefault("people", {})
        for o in ORDER:
            if o == e:
                continue
            old = people.get(o) or {}
            if "trust" not in old or "direct_familiarity" not in old:
                new = rel_template(old.get("familiarity", 0.02))
                new["reports"] = list(old.get("reports", []))[-90:]
                people[o] = new
            else:
                for k, v in rel_template(old.get("legacy_familiarity", old.get("familiarity", 0.02))).items():
                    old.setdefault(k, v)
                old["events"] = list(old.get("events", []))[-120:]
                old["shared_references"] = list(old.get("shared_references", []))[-40:]
                old["reports"] = list(old.get("reports", []))[-90:]
    return minds


def topic_template(cycle=0):
    return {
        "id": f"topic-{cycle:06d}",
        "root": None,
        "current_facet": None,
        "facets": [],
        "unresolved": [],
        "examples": [],
        "disagreements": [],
        "shared_references": [],
        "participants": list(ORDER),
        "turns": 0,
        "low_novelty_beats": 0,
        "recent_terms": [],
        "last_shift_cycle": cycle,
        "status": "forming",
    }


def migrate_state(state):
    state = state or {}
    state.setdefault("topic_episode", topic_template(int(state.get("cycle", 0))))
    topic = state["topic_episode"]
    for k, v in topic_template(int(state.get("cycle", 0))).items():
        topic.setdefault(k, v)
    return state


def _message_target(msg, discourse_by_id=None):
    c = (msg or {}).get("cognition") or {}
    tgt = c.get("target")
    if tgt in ORDER:
        return tgt
    parent = (msg or {}).get("parent_discourse_id")
    if parent and discourse_by_id and parent in discourse_by_id:
        speaker = discourse_by_id[parent].get("speaker")
        if speaker in ORDER:
            return speaker
    return None


def classify_event(listener, msg, discourse_by_id=None):
    speaker = (msg or {}).get("speaker")
    if speaker not in ORDER or speaker == listener:
        return None
    c = (msg or {}).get("cognition") or {}
    move = c.get("move_type") or "other"
    tgt = _message_target(msg, discourse_by_id)
    direct = tgt == listener
    text = str((msg or {}).get("text", ""))
    low = text.lower()
    risk = 1 if move in {"self_disclosure", "disclosure"} else 0
    if any(w in low for w in ("afraid", "ashamed", "regret", "hurt", "vulnerable", "trust you", "scared")):
        risk = max(risk, 2)
    repair = any(w in low for w in ("sorry", "misunderstood", "what i meant", "i was wrong", "let me correct"))
    disagreement = move in {"disagree", "disagreement"} or bool(re.search(r"\b(i don't agree|i disagree|not sure i agree|but i think)\b", low))
    support = bool(re.search(r"\b(that makes sense|i can see why|i get why|i'm with you|i understand)\b", low))
    callback = move == "callback" or bool(c.get("shared_reference"))
    return {
        "speaker": speaker,
        "listener": listener,
        "direct": direct,
        "participation": "DIRECT_ADDRESSEE" if direct else "OVERHEARER",
        "move": move,
        "risk": risk,
        "repair_attempt": repair,
        "disagreement": disagreement,
        "support": support,
        "callback": callback,
        "terms": words(text)[:8],
        "message_id": (msg or {}).get("id"),
    }


def apply_event(rel, event, cycle):
    if not event:
        return rel
    rel["observed_turns"] = int(rel.get("observed_turns", 0)) + 1
    rel["exposure"] = clamp(rel.get("exposure", 0) + 0.003)
    if not event.get("direct"):
        return rel

    rel["direct_turns"] = int(rel.get("direct_turns", 0)) + 1
    rel["last_direct_cycle"] = cycle
    rel["direct_familiarity"] = clamp(rel.get("direct_familiarity", 0) + 0.008)
    rel["reciprocity"] = clamp(rel.get("reciprocity", 0) + 0.004)
    rel["predictability"] = clamp(rel.get("predictability", 0) + 0.002)

    move = event.get("move")
    if move in {"answer", "follow_up", "deepen", "compare", "support", "callback", "repair"}:
        rel["warmth"] = clamp(rel.get("warmth", 0) + 0.002)
    if move in {"answer", "deepen", "compare", "disagree", "callback"}:
        rel["respect"] = clamp(rel.get("respect", 0) + 0.0015)
    if event.get("disagreement"):
        rel["tension"] = clamp(rel.get("tension", 0) + 0.012)
        rel["predictability"] = clamp(rel.get("predictability", 0) - 0.002)
    if event.get("support"):
        rel["warmth"] = clamp(rel.get("warmth", 0) + 0.006)
    if event.get("repair_attempt"):
        rel["repair_attempts"] = int(rel.get("repair_attempts", 0)) + 1
        rel["tension"] = clamp(rel.get("tension", 0) - 0.010)
    if move == "repair_success":
        rel["repair_successes"] = int(rel.get("repair_successes", 0)) + 1
        rel["tension"] = clamp(rel.get("tension", 0) - 0.040)
        rel["trust"] = clamp(rel.get("trust", 0) + 0.010)
    if int(event.get("risk", 0)) >= 1 and (event.get("support") or move in {"answer", "repair_success", "callback"}):
        rel["trust"] = clamp(rel.get("trust", 0) + 0.006 * int(event.get("risk", 0)))
        rel["disclosure_depth"] = clamp(rel.get("disclosure_depth", 0) + 0.008 * int(event.get("risk", 0)))
    if event.get("callback"):
        rel["predictability"] = clamp(rel.get("predictability", 0) + 0.005)
        rel["reciprocity"] = clamp(rel.get("reciprocity", 0) + 0.005)

    rel.setdefault("events", []).append({
        "cycle": cycle,
        "kind": move,
        "direct": True,
        "message_id": event.get("message_id"),
        "risk": event.get("risk", 0),
        "repair": bool(event.get("repair_attempt")),
        "disagreement": bool(event.get("disagreement")),
    })
    rel["events"] = rel["events"][-120:]
    return rel


def observe_message(minds, msg, cycle, discourse_by_id=None):
    migrate_minds(minds)
    for listener in ORDER:
        if listener == msg.get("speaker"):
            continue
        event = classify_event(listener, msg, discourse_by_id)
        if not event:
            continue
        rel = minds["entities"][listener]["people"][msg["speaker"]]
        apply_event(rel, event, cycle)
        if event.get("direct") and event.get("terms"):
            refs = rel.setdefault("shared_references", [])
            for term in event["terms"][:3]:
                if term not in refs:
                    refs.append(term)
            rel["shared_references"] = refs[-40:]
    return minds


def topic_terms_from_messages(messages, limit=12):
    c = Counter()
    recency = []
    for m in messages[-16:]:
        ws = words(m.get("text", ""))
        recency.extend(ws[:6])
        c.update(ws)
    ranked = sorted(c, key=lambda w: (-c[w], -(len(recency) - 1 - recency[::-1].index(w) if w in recency else 0), w))
    return ranked[:limit]


def update_topic(topic, messages, cycle):
    topic = topic or topic_template(cycle)
    terms = topic_terms_from_messages(messages)
    previous = set(topic.get("recent_terms", []))
    novel = [w for w in terms if w not in previous]

    if topic.get("root") is None and terms:
        topic["root"] = terms[0]
        topic["current_facet"] = terms[0]
        topic["status"] = "active"
        topic["last_shift_cycle"] = cycle

    if terms:
        candidates = [w for w in terms if w != topic.get("root")]
        if candidates:
            facet = candidates[0]
            if facet != topic.get("current_facet"):
                topic["current_facet"] = facet
                if facet not in topic.setdefault("facets", []):
                    topic["facets"].append(facet)

    topic["turns"] = int(topic.get("turns", 0)) + 1
    topic["recent_terms"] = terms
    if len(novel) <= 1:
        topic["low_novelty_beats"] = int(topic.get("low_novelty_beats", 0)) + 1
    else:
        topic["low_novelty_beats"] = 0
    topic["facets"] = list(dict.fromkeys(topic.get("facets", [])))[-20:]
    if topic["low_novelty_beats"] >= 4 and topic["turns"] >= 6:
        topic["status"] = "ready_to_bridge"
    return topic


def should_shift_topic(topic):
    return bool(topic and topic.get("status") == "ready_to_bridge")


def new_topic_from_terms(terms, cycle, prior=None):
    t = topic_template(cycle)
    if terms:
        t["root"] = terms[0]
        t["current_facet"] = terms[0]
        t["status"] = "active"
    if prior and prior.get("current_facet"):
        t["shared_references"] = [prior["current_facet"]]
    return t


def choose_partner(entity, minds, topic, cycle):
    ent = minds["entities"][entity]
    scores = []
    for other in ORDER:
        if other == entity:
            continue
        r = ent["people"][other]
        strength = (
            0.20 * r.get("direct_familiarity", 0)
            + 0.15 * r.get("trust", 0)
            + 0.12 * r.get("reciprocity", 0)
            + 0.10 * r.get("respect", 0)
            + 0.08 * r.get("warmth", 0)
            - 0.10 * r.get("tension", 0)
        )
        gap = max(0, cycle - int(r.get("last_direct_cycle") or 0))
        weak_tie_novelty = min(0.18, gap / 4000.0)
        scores.append((strength + weak_tie_novelty, other))
    scores.sort(reverse=True)
    return scores[0][1]


def relationship_view(minds, entity, other):
    r = minds["entities"][entity]["people"][other]
    return {k: r.get(k) for k in REL_KEYS} | {
        "direct_turns": r.get("direct_turns", 0),
        "repair_successes": r.get("repair_successes", 0),
        "shared_references": list(r.get("shared_references", []))[-8:],
    }


def deepest_available_detail(topic, recent_messages):
    facet = (topic or {}).get("current_facet")
    if facet:
        return facet
    terms = topic_terms_from_messages(recent_messages)
    return terms[0] if terms else "that"


def plan_actions(order, target_of_question, minds, topic, cycle):
    roles = ["answer", "deepen", "compare", "callback"]
    plans = {}
    used = set()
    for idx, entity in enumerate(order):
        if entity == target_of_question:
            action = "answer"
        else:
            action = roles[idx % len(roles)]
            if action in used:
                action = next((x for x in roles if x not in used), "deepen")
        used.add(action)
        partner = target_of_question if target_of_question in ORDER and target_of_question != entity else choose_partner(entity, minds, topic, cycle)
        plans[entity] = {
            "action": action,
            "target": partner,
            "topic_facet": (topic or {}).get("current_facet"),
            "relationship": relationship_view(minds, entity, partner),
            "mandatory_speech": True,
        }
    return plans


def audit_invariants(minds, topic):
    migrate_minds(minds)
    for e in ORDER:
        for o in ORDER:
            if e == o:
                continue
            r = minds["entities"][e]["people"][o]
            for k in REL_KEYS:
                if not (0.0 <= float(r.get(k, 0)) <= 1.0):
                    raise AssertionError(f"relationship {e}->{o} {k} out of range")
    if topic is not None and not isinstance(topic.get("facets", []), list):
        raise AssertionError("topic facets must be a list")
    return True
