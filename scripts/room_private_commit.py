#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone

import room_engine_v5 as c

BLOCKED_TERMS = {
    "current topic root",
    "current narrow facet",
    "topic root",
    "topic facet",
    "natural public conversational turn",
    "the natural public conversational turn",
}
ALLOWED_MOVES = {
    "answer", "deepen", "disclose", "compare", "disagree",
    "repair", "support", "callback", "bridge", "close_topic",
}


def clean_topic(topic: dict) -> dict:
    topic = dict(topic or {})
    for key in ("facets", "visited_facets", "recent_terms", "shared_references", "unresolved"):
        vals = topic.get(key)
        if isinstance(vals, list):
            topic[key] = [
                str(x).strip().lower() for x in vals
                if str(x or "").strip() and str(x).strip().lower() not in BLOCKED_TERMS
            ]
    if str(topic.get("root") or "").strip().lower() in BLOCKED_TERMS:
        topic["root"] = None
    if str(topic.get("current_facet") or "").strip().lower() in BLOCKED_TERMS:
        topic["current_facet"] = topic.get("root") or (topic.get("facets") or [None])[0]
    return topic


def clean_terms(expr: dict, topic: dict) -> list[str]:
    out: list[str] = []
    for value in (topic.get("root"), topic.get("current_facet")):
        s = str(value or "").strip().lower()
        if s and s not in BLOCKED_TERMS and s not in out:
            out.append(s)
    vals = expr.get("topic_terms") if isinstance(expr, dict) else None
    if isinstance(vals, list):
        for value in vals:
            s = str(value or "").strip().lower()
            if s and s not in BLOCKED_TERMS and s not in out:
                out.append(s)
    return out[:4]


def seed_topic(expressions: dict, order: list[str], cycle: int, prior: dict) -> dict:
    terms: list[str] = []
    for e in order:
        vals = expressions[e].get("topic_terms") if isinstance(expressions.get(e), dict) else None
        if not isinstance(vals, list):
            continue
        for value in vals:
            s = str(value or "").strip().lower()
            if s and s not in BLOCKED_TERMS and s not in terms:
                terms.append(s)
    if not terms:
        raise RuntimeError("private Room clean start produced no semantic topic; regenerate beat")
    return clean_topic(c.new_topic_from_terms(terms[:8], cycle, prior))


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
    for e in c.ORDER:
        expr = (E[e].get("private") or {}).get("expression")
        if not isinstance(expr, dict):
            raise RuntimeError(f"private Room requires model expression for {e}; no public fallback is permitted")
        expressions[e] = expr

    # After sterilization there is no historical topic by design. The first topic may
    # only be seeded from semantic terms independently produced by private model nodes.
    if not topic.get("root"):
        topic = seed_topic(expressions, order, cycle, topic)

    plans = c.plan_actions(order, c.target(q) if q else None, M, topic, cycle)
    spoken: list[dict] = []
    answer_msg = None

    for e in order:
        expr = expressions[e]
        text = c.model_text(expr)
        if not text:
            raise RuntimeError(f"private Room expression invalid for {e}; no public fallback is permitted")
        if c.recent_similarity(V, text, e, 120) > 0.86:
            raise RuntimeError(f"private Room expression too repetitive for {e}; regenerate beat")

        planned = plans[e]
        move = str(expr.get("move") or planned["action"]).strip().lower()
        if move not in ALLOWED_MOVES:
            move = planned["action"] if planned["action"] in ALLOWED_MOVES else "deepen"
        tgt = str(expr.get("target") or planned["target"]).strip().lower()
        if tgt not in c.ORDER or tgt == e:
            tgt = planned["target"]
        if tgt not in c.ORDER or tgt == e:
            raise RuntimeError(f"private Room expression has no valid partner for {e}")

        parent = (q or answer_msg or prev or {}).get("discourse_id")
        terms = clean_terms(expr, topic)
        if not terms:
            raise RuntimeError(f"private Room expression has no semantic terms for {e}")
        msg, node = c.emit(e, move, tgt, parent, None, text, beat, len(spoken), topic, terms)
        c.record(V, T, M, msg, node, cycle)
        spoken.append(msg)
        if move == "answer":
            answer_msg = msg

    speakers = [m["speaker"] for m in spoken]
    if len(spoken) != 4 or set(speakers) != set(c.ORDER):
        raise RuntimeError(f"v5 mandatory speech invariant failed: {speakers}")

    previous_vocabulary = {
        str(x).strip().lower()
        for x in [topic.get("root"), topic.get("current_facet")] + list(topic.get("facets", []))
        if str(x or "").strip()
    }
    topic = clean_topic(c.update_topic(topic, spoken, cycle))

    if c.should_shift_topic(topic):
        declared = c.topic_terms_from_messages(spoken, limit=12, episode_id=topic.get("id"))
        novel = [
            str(x).strip().lower() for x in declared
            if str(x or "").strip()
            and str(x).strip().lower() not in BLOCKED_TERMS
            and str(x).strip().lower() not in previous_vocabulary
        ]
        if novel:
            topic = c.new_topic_from_terms(novel, cycle, topic)

    S["topic_episode"] = topic
    for e in c.ORDER:
        M["entities"][e]["medium"] = {
            "topics": [topic.get("root"), topic.get("current_facet")] + list(topic.get("facets", []))[:8],
            "branch_interest": round(c.clamp(.4 * c.trait(e, "curiosity") + .4 * c.trait(e, "attention_persistence")), 3),
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
        "note": "research-informed v5 private model active; four mandatory unique speakers; no public fallback; directed slow-learning relationships; semantic topic episodes; sequential private cognition",
    })

    c.audit_invariants(M, topic)
    c.save(c.ROOM / "conversation.json", V)
    c.save(c.ROOM / "discourse.json", T)
    c.save(c.ROOM / "cognitive_state.json", M)
    c.save(c.ROOM / "state.json", S)

    cm = {"schema": 5, "entities": {}}
    for e in c.ORDER:
        ent = M["entities"][e]
        cm["entities"][e] = {
            "name": c.N[e],
            "profile": c.P[e],
            "genome": c.P[e]["traits"],
            "development": {
                "turns": cycle,
                "spoken": ent.get("spoken", 0),
                "silences": ent.get("silences", 0),
                "topic_weights": {
                    t: 1 for t in [topic.get("root"), topic.get("current_facet")] + list(topic.get("facets", []))[:8] if t
                },
                "relationships": {
                    o: {
                        k: v for k, v in ent["people"][o].items()
                        if k in {"exposure", "direct_familiarity", "trust", "predictability", "reciprocity", "warmth", "respect", "disclosure_depth", "tension", "direct_turns", "repair_successes"}
                    }
                    for o in ent.get("people", {})
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
        },
    }
    c.save(c.ROOM / "live.json", live)
    c.save(c.ROOT / "society" / "live.json", live)
    print("Room private beat", cycle, ":", ", ".join(c.N[e] for e in speakers), "topic=", topic.get("root"), "/", topic.get("current_facet"))


c.commit = private_commit

if __name__ == "__main__":
    c.main()
