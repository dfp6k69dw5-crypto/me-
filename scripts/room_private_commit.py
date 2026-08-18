#!/usr/bin/env python3
from __future__ import annotations

import re
from datetime import datetime, timezone

import room_engine_v5 as c

ALLOWED_MOVES = {
    "answer", "deepen", "disclose", "compare", "disagree",
    "repair", "support", "callback", "bridge", "close",
}
META_WORDS = {
    "topic", "facet", "root", "schema", "prompt", "json",
    "process", "output", "generation", "expression",
}
META_PATTERNS = (
    r"\btopic[-_ ]?\d{3,}\b",
    r"\bcurrent\s+(?:narrow\s+)?topic\b",
    r"\btopic\s+(?:root|facet|episode|identifier|id|schema|closure|closing)\b",
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
    r"\bpublic[- ]?expression\b",
    r"\b(?:cognitive|language|generation|output|expression)\s+process\b",
    r"\b(?:right|wrong)\s+person\s+to\s+express\b",
    r"\bregular\s+person\b.*\bnot\b",
)


def norm(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def infected_text(value) -> bool:
    text = norm(value)
    if not text:
        return True
    if any(re.search(pattern, text) for pattern in META_PATTERNS):
        return True
    words = set(re.findall(r"[a-z]+", text))
    if words & META_WORDS:
        return True
    if any(marker in text for marker in (
        "system prompt", "hidden prompt", "developer message",
        "internal instructions", "chain of thought",
    )):
        return True
    return False


def bad_term(value) -> bool:
    text = norm(value)
    if not text or len(text) > 80 or infected_text(text):
        return True
    if re.fullmatch(r"topic[-_ ]?\d+", text):
        return True
    if text in {
        "conversation", "discussion", "subject", "context", "label",
        "category", "process", "expression", "output", "generation",
    }:
        return True
    return False


def clean_topic(topic: dict) -> dict:
    topic = dict(topic or {})
    for key in ("facets", "visited_facets", "recent_terms", "shared_references", "unresolved"):
        vals = topic.get(key)
        if isinstance(vals, list):
            cleaned = []
            for value in vals:
                s = norm(value)
                if not bad_term(s) and s not in cleaned:
                    cleaned.append(s)
            topic[key] = cleaned
    root = norm(topic.get("root"))
    facet = norm(topic.get("current_facet"))
    topic["root"] = None if bad_term(root) else root
    if bad_term(facet):
        choices = [x for x in topic.get("facets", []) if not bad_term(x)]
        topic["current_facet"] = topic.get("root") or (choices[0] if choices else None)
    else:
        topic["current_facet"] = facet
    return topic


def semantic_values(expr: dict) -> list:
    return expr.get("semantic_terms") if isinstance(expr, dict) and isinstance(expr.get("semantic_terms"), list) else []


def clean_terms(expr: dict, topic: dict) -> list[str]:
    out: list[str] = []
    for value in (topic.get("root"), topic.get("current_facet")):
        s = norm(value)
        if not bad_term(s) and s not in out:
            out.append(s)
    for value in semantic_values(expr):
        s = norm(value)
        if not bad_term(s) and s not in out:
            out.append(s)
    return out[:4]


def seed_topic(expressions: dict, order: list[str], cycle: int, prior: dict) -> dict:
    terms: list[str] = []
    for entity in order:
        for value in semantic_values(expressions.get(entity, {})):
            s = norm(value)
            if not bad_term(s) and s not in terms:
                terms.append(s)
    if not terms:
        raise RuntimeError("private Room clean start produced no safe semantic terms; regenerate beat")
    seeded = clean_topic(c.new_topic_from_terms(terms[:8], cycle, prior))
    if not seeded.get("root"):
        raise RuntimeError("private Room clean start could not establish a safe subject; regenerate beat")
    return seeded


def grounded(text: str, terms: list[str]) -> bool:
    words = set(re.findall(r"[a-z][a-z'-]{2,}", norm(text)))
    for term in terms:
        significant = [word for word in re.findall(r"[a-z][a-z'-]{2,}", norm(term)) if len(word) >= 4]
        if any(word in words for word in significant):
            return True
    return False


def validate_public_expression(entity: str, text: str, terms: list[str]) -> None:
    low = norm(text)
    if infected_text(low):
        raise RuntimeError(f"private Room expression contaminated for {entity}; regenerate beat")
    if len(re.findall(r"\b\w+\b", low)) < 4:
        raise RuntimeError(f"private Room expression too thin for {entity}; regenerate beat")
    if re.search(rf"\b{re.escape(entity)}\b", low):
        raise RuntimeError(f"private Room expression self-named for {entity}; regenerate beat")
    if re.search(r"\b(?:should|allowed|required)\b.*\bspeak", low):
        raise RuntimeError(f"private Room expression discussed speaking permission for {entity}; regenerate beat")
    if not grounded(text, terms):
        raise RuntimeError(f"private Room expression ungrounded for {entity}; regenerate beat")


def private_commit(parts: list[dict], key: str):
    S = c.state()
    M = c.minds()
    T = c.tree()
    V = c.conv()
    prev = c.event()
    cycle = int(S.get("cycle", 0)) + 1
    topic = clean_topic(S.get("topic_episode") or {})
    if topic.get("root"):
        topic = clean_topic(c.update_topic(topic, V[-24:], cycle))

    q = prev if c.isq(prev) and topic.get("root") else None
    order, E = c.order4(parts, prev, cycle)
    beat = f"beat-{c.BOOT}-{cycle:06d}"

    expressions = {}
    for entity in c.ORDER:
        expr = (E[entity].get("private") or {}).get("expression")
        if not isinstance(expr, dict):
            raise RuntimeError(f"private Room requires model expression for {entity}; no public fallback is permitted")
        if not semantic_values(expr):
            raise RuntimeError(f"private Room expression lacks neutral semantic fields for {entity}; regenerate beat")
        expressions[entity] = expr

    if not topic.get("root"):
        topic = seed_topic(expressions, order, cycle, topic)

    plans = c.plan_actions(order, c.target(q) if q else None, M, topic, cycle)
    staged: list[tuple[str, str, str, str, list[str]]] = []

    # Nothing touches memory until all four public turns pass every gate.
    for entity in order:
        expr = expressions[entity]
        text = c.model_text(expr)
        if not text:
            raise RuntimeError(f"private Room expression invalid for {entity}; no public fallback is permitted")

        terms = clean_terms(expr, topic)
        if not terms:
            raise RuntimeError(f"private Room expression has no safe semantic terms for {entity}")
        validate_public_expression(entity, text, terms)
        if c.recent_similarity(V, text, entity, 120) > 0.86:
            raise RuntimeError(f"private Room expression too repetitive for {entity}; regenerate beat")

        planned = plans[entity]
        move = norm(expr.get("move") or planned["action"])
        if move not in ALLOWED_MOVES:
            move = planned["action"] if planned["action"] in ALLOWED_MOVES else "deepen"
        target = norm(expr.get("target") or planned["target"])
        if target not in c.ORDER or target == entity:
            target = planned["target"]
        if target not in c.ORDER or target == entity:
            raise RuntimeError(f"private Room expression has no valid partner for {entity}")
        staged.append((entity, move, target, text, terms))

    spoken: list[dict] = []
    answer_msg = None
    for entity, move, target, text, terms in staged:
        parent = (q or answer_msg or prev or {}).get("discourse_id")
        msg, node = c.emit(entity, move, target, parent, None, text, beat, len(spoken), topic, terms)
        c.record(V, T, M, msg, node, cycle)
        spoken.append(msg)
        if move == "answer":
            answer_msg = msg

    speakers = [m["speaker"] for m in spoken]
    if len(spoken) != 4 or set(speakers) != set(c.ORDER):
        raise RuntimeError(f"v5 mandatory speech invariant failed: {speakers}")

    previous_vocabulary = {
        norm(x)
        for x in [topic.get("root"), topic.get("current_facet")] + list(topic.get("facets", []))
        if not bad_term(x)
    }
    topic = clean_topic(c.update_topic(topic, spoken, cycle))
    if not topic.get("root") or bad_term(topic.get("root")):
        raise RuntimeError("private Room subject state failed contamination check")

    if c.should_shift_topic(topic):
        declared = c.topic_terms_from_messages(spoken, limit=12, episode_id=topic.get("id"))
        novel = [norm(x) for x in declared if not bad_term(x) and norm(x) not in previous_vocabulary]
        if novel:
            candidate = clean_topic(c.new_topic_from_terms(novel, cycle, topic))
            if candidate.get("root") and not bad_term(candidate.get("root")):
                topic = candidate

    S["topic_episode"] = topic
    for entity in c.ORDER:
        M["entities"][entity]["medium"] = {
            "topics": [
                x for x in [topic.get("root"), topic.get("current_facet")] + list(topic.get("facets", []))[:8]
                if x and not bad_term(x)
            ],
            "branch_interest": round(c.clamp(.4 * c.trait(entity, "curiosity") + .4 * c.trait(entity, "attention_persistence")), 3),
        }

    T["nodes"] = T.get("nodes", [])[-1200:]
    T["roots"] = T.get("roots", [])[-300:]
    V = V[-1000:]
    stamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    S.update({
        "version": c.VERSION,
        "boot_id": c.BOOT,
        "cycle": cycle,
        "last_run": stamp,
        "messages": len(V),
        "last_public_event": spoken[-1]["id"],
        "last_speaker": spoken[-1]["speaker"],
        "last_beat_id": beat,
        "beat_contributors": speakers,
        "beat_message_count": 4,
        "silence_cycles": 0,
        "note": "research-informed v5 private model active; four mandatory unique speakers; no public fallback; contamination-gated memory; sequential private cognition",
    })

    c.audit_invariants(M, topic)
    c.save(c.ROOM / "conversation.json", V)
    c.save(c.ROOM / "discourse.json", T)
    c.save(c.ROOM / "cognitive_state.json", M)
    c.save(c.ROOM / "state.json", S)

    cm = {"schema": 5, "entities": {}}
    for entity in c.ORDER:
        ent = M["entities"][entity]
        cm["entities"][entity] = {
            "name": c.N[entity],
            "profile": c.P[entity],
            "genome": c.P[entity]["traits"],
            "development": {
                "turns": cycle,
                "spoken": ent.get("spoken", 0),
                "silences": ent.get("silences", 0),
                "topic_weights": {t: 1 for t in M["entities"][entity]["medium"]["topics"] if t},
                "relationships": {
                    other: {
                        k: v for k, v in ent["people"][other].items()
                        if k in {"exposure", "direct_familiarity", "trust", "predictability", "reciprocity", "warmth", "respect", "disclosure_depth", "tension", "direct_turns", "repair_successes"}
                    }
                    for other in ent.get("people", {})
                },
            },
            "memory": [{"text": x.get("text", "")} for x in ent.get("room_memories", [])[-12:]],
        }

    live = {
        "generated_at": stamp,
        "architecture_version": c.VERSION,
        "boot_id": c.BOOT,
        "minds": cm,
        "profiles": c.P,
        "state": S,
        "conversation": V,
        "discourse": T,
        "topic_episode": topic,
        "network": {
            "compute_nodes": 12,
            "entities": 4,
            "nodes_per_entity": 3,
            "tasks_per_node": 4,
            "active_processes": 48,
            "voting": False,
            "public_bus": True,
            "private_scope": "same_entity",
            "beat_output": "4 mandatory unique speakers",
            "private_pipeline": "perception->deliberation->expression",
            "public_fallback": False,
            "history_generation": c.BOOT,
            "contamination_gate": True,
        },
    }
    c.save(c.ROOM / "live.json", live)
    c.save(c.ROOT / "society" / "live.json", live)
    print("Room private beat", cycle, ":", ", ".join(c.N[e] for e in speakers), "subject=", topic.get("root"))


c.commit = private_commit

if __name__ == "__main__":
    c.main()
