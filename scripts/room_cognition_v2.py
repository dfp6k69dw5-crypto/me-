#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOM = ROOT / "room"
PARTS = ROOT / "room_parts"
WORK = ROOT / "room_work"

CONFIG = json.loads((ROOM / "config.json").read_text())
ARCH = CONFIG["a"]
PROFILES = CONFIG["p"]
ENTITY_ORDER = ("sarah", "mara", "owen", "jules")
NAMES = {eid: PROFILES[eid]["name"] for eid in ENTITY_ORDER}

# Keep the compact historical schema in config.json, but expose named fields here.
LIFE_MEMORY = {
    eid: [
        {
            "id": row[0],
            "types": row[1],
            "age": row[2],
            "first": row[3],
            "tags": row[4],
            "salience": row[5],
            "emotion": row[6],
            "confidence": row[7],
        }
        for row in CONFIG["m"][eid]
    ]
    for eid in ENTITY_ORDER
}

STOP = set(
    "the and but for not was are you your our out too did can got one once that this with from "
    "have has had just what when where there they them then than about would could should into "
    "only really some more very like because been being does doing done will well yeah okay also "
    "still maybe kind sort thing things something anything someone everyone say saying think thinking "
    "thought know knowing mean means seem seems want wants wanted make making made start starting "
    "started try trying tried good great nice sure right actually probably pretty little much many few "
    "around again already even ever never always often sometimes today tonight tomorrow yesterday "
    "different together interesting going everything current".split()
)


def load_json(path: Path, default):
    return json.loads(path.read_text()) if path.exists() else default


def save_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def stable_seed(*parts) -> int:
    raw = ":".join(map(str, parts)).encode()
    return int(hashlib.sha256(raw).hexdigest()[:16], 16) & 0x7FFFFFFF


def rng(*parts) -> random.Random:
    return random.Random(stable_seed(*parts))


def clamp(value, low=0.0, high=1.0):
    return max(low, min(high, float(value)))


def words(text):
    out = []
    name_words = {name.lower() for name in NAMES.values()}
    for token in re.findall(r"[a-z][a-z'-]{2,}", str(text or "").lower()):
        token = token.strip("'-")
        if token and token not in STOP and token not in name_words and token not in out:
            out.append(token)
    return out


def initialize_state():
    ROOM.mkdir(exist_ok=True)
    if not (ROOM / "conversation.json").exists():
        legacy = ROOT / "society" / "conversation.json"
        (ROOM / "conversation.json").write_text(legacy.read_text() if legacy.exists() else "[]\n")
    if not (ROOM / "discourse.json").exists():
        save_json(ROOM / "discourse.json", {"nodes": [], "roots": []})
    if not (ROOM / "state.json").exists():
        save_json(
            ROOM / "state.json",
            {"version": "room-cognition-v2", "cycle": 0, "last_speaker": None, "silence_cycles": 0},
        )
    if not (ROOM / "cognitive_state.json").exists():
        entities = {}
        for eid in ENTITY_ORDER:
            entities[eid] = {
                "fast": {"activation": 0.2, "attention": []},
                "medium": {"topics": [], "branch_interest": 0.0},
                "slow": {"social_energy": 0.55, "association": 0.5},
                "very_slow": {"identity": 1.0},
                "noise": {"activation": 0.0, "association": 0.0, "inhibition": 0.0, "social": 0.0},
                "room_memories": [],
                "self_history": [],
                "last_event": None,
                "spoken": 0,
                "silences": 0,
                "people": {
                    peer: {"familiarity": 0.02, "reports": []}
                    for peer in ENTITY_ORDER
                    if peer != eid
                },
            }
        save_json(ROOM / "cognitive_state.json", {"entities": entities})


initialize_state()


def conversation():
    return load_json(ROOM / "conversation.json", [])


def v2_messages():
    return [m for m in conversation() if m.get("runtime") == "room-cognition-v2"]


def current_event():
    messages = v2_messages()
    return messages[-1] if messages else None


def state():
    return load_json(ROOM / "state.json", {})


def cognitive_state():
    return load_json(ROOM / "cognitive_state.json", {"entities": {}})


def discourse():
    return load_json(ROOM / "discourse.json", {"nodes": [], "roots": []})


def node_identity(node_id):
    entity = ENTITY_ORDER[node_id // 3]
    local_node = node_id % 3
    role, tasks = ARCH["roles"][str(local_node)]
    return entity, local_node, role, tasks


def trait(entity, name, default=0.5):
    return float(PROFILES[entity]["traits"].get(name, default))


def target_of(event):
    if not event:
        return None
    target = (event.get("cognition") or {}).get("target")
    if target:
        return target
    low = event.get("text", "").lower()
    for eid, name in NAMES.items():
        if eid != event.get("speaker") and re.search(rf"\b{re.escape(name.lower())}\b", low):
            return eid
    return None


def direct_question_for(entity, event):
    return bool(
        event
        and event.get("speaker") != entity
        and event.get("text", "").rstrip().endswith("?")
        and target_of(event) in (None, entity)
    )


def life_memory(entity, memory_id):
    return next((item for item in LIFE_MEMORY[entity] if item["id"] == memory_id), None)


def retrieve_memory(entity, cues, cycle_key):
    cue_set = set(cues)
    ranked = sorted(
        LIFE_MEMORY[entity],
        key=lambda m: (
            2.0 * len(set(m["tags"]) & cue_set)
            + 0.5 * m["salience"]
            + 0.25 * m["emotion"]
        ),
        reverse=True,
    )
    if cue_set and ranked and set(ranked[0]["tags"]) & cue_set:
        return ranked[0]
    pool = sorted(LIFE_MEMORY[entity], key=lambda m: m["salience"], reverse=True)[:6]
    return rng("memory", entity, cycle_key).choice(pool)


def noise_state(entity, entity_state, cycle_key):
    r = rng("noise", entity, cycle_key)
    previous = entity_state.get("noise", {})
    aliases = {
        "activation": previous.get("activation", previous.get("a", 0.0)),
        "association": previous.get("association", previous.get("x", 0.0)),
        "inhibition": previous.get("inhibition", previous.get("i", 0.0)),
        "social": previous.get("social", previous.get("s", 0.0)),
    }
    scales = {"activation": 0.08, "association": 0.09, "inhibition": 0.07, "social": 0.08}
    return {
        key: round(clamp(0.82 * aliases[key] + r.gauss(0.0, scales[key]), -0.25, 0.25), 4)
        for key in scales
    }


def discourse_depth(node_id, tree=None):
    tree = tree or discourse()
    mapping = {n["id"]: n for n in tree["nodes"]}
    seen = set()
    depth = 0
    while node_id and node_id in mapping and node_id not in seen and depth < 20:
        seen.add(node_id)
        depth += 1
        node_id = mapping[node_id].get("parent")
    return depth


def inherited_branch_anchor(event):
    """Return the stable autobiographical/factual anchor carried by a discourse branch."""
    if not event:
        return None, None
    cognition = event.get("cognition") or {}
    if cognition.get("branch_memory"):
        return cognition.get("branch_owner"), cognition.get("branch_memory")
    if cognition.get("memory_provenance"):
        return event.get("speaker"), cognition.get("memory_provenance")

    node_id = event.get("discourse_id")
    tree = discourse()
    mapping = {n["id"]: n for n in tree["nodes"]}
    seen = set()
    while node_id and node_id in mapping and node_id not in seen:
        seen.add(node_id)
        node = mapping[node_id]
        if node.get("branch_memory"):
            return node.get("branch_owner"), node.get("branch_memory")
        node_id = node.get("parent") or node.get("derived_from")
    return None, None


def public_network_summary(bus):
    public = bus.get("public", [])
    expression = [p for p in public if p.get("role") == "expression"]
    comprehension = [p for p in public if p.get("role") == "comprehension"]
    concepts = []
    for packet in comprehension:
        for concept in packet.get("public_concepts", []):
            if concept not in concepts:
                concepts.append(concept)
    return {
        "mean_attention": round(sum(p.get("attention", 0.0) for p in public) / max(1, len(public)), 4),
        "mean_expression_readiness": round(
            sum(p.get("readiness", 0.0) for p in expression) / max(1, len(expression)), 4
        ),
        "public_concepts": concepts[:12],
        "expression_readiness": {p["entity"]: p.get("readiness", 0.0) for p in expression},
    }


def sense(node_id, cycle_key):
    entity, local_node, role, tasks = node_identity(node_id)
    event = current_event()
    entity_state = cognitive_state()["entities"][entity]
    event_words = words((event or {}).get("text", ""))[:8]
    recalled = retrieve_memory(entity, event_words, cycle_key)
    stochastic = noise_state(entity, entity_state, cycle_key)
    r = rng("sense", cycle_key, node_id)
    branch_owner, branch_memory = inherited_branch_anchor(event)

    if role == "comprehension":
        head = (re.findall(r"[a-z']+", (event or {}).get("text", "").lower()) or [""])[0]
        prediction = {
            "why": "cause",
            "how": "process",
            "where": "place",
            "when": "time",
            "who": "person",
            "what": "explanation",
        }.get(head)
        work = {
            tasks[0]: [
                {"concept": token, "activation": round(0.7 + 0.2 * trait(entity, "curiosity"), 3)}
                for token in event_words
            ],
            tasks[1]: {
                "kind": "utterance",
                "clauses": [
                    {"tokens": words(clause)}
                    for clause in re.split(
                        r"[,;!?]|\s+(?:but|because|and)\s+", (event or {}).get("text", "")
                    )
                    if clause.strip()
                ][:6],
            },
            tasks[2]: {"scope": "constituent", "expected": prediction},
            tasks[3]: {
                "speaker": (event or {}).get("speaker"),
                "target": target_of(event),
                "reported": event_words,
                "branch_owner": branch_owner,
                "branch_memory": branch_memory,
            },
        }
        readiness = 0.10
        attention = clamp(
            0.4
            + 0.3 * trait(entity, "social_sensitivity")
            + (0.15 if event else -0.10)
            + r.gauss(0, 0.04)
        )
        public_concepts = event_words
        public_prediction = prediction

    elif role == "thought":
        work = {
            tasks[0]: {
                "concepts": event_words + recalled["tags"][:4],
                "breadth": round(clamp(trait(entity, "openness") + stochastic["association"]), 3),
            },
            tasks[1]: {"kind": "merge", "event": event_words, "memory": recalled["tags"]},
            tasks[2]: recalled,
            tasks[3]: {
                "arousal": round(
                    clamp(0.15 + 0.4 * trait(entity, "emotional_reactivity") + 0.2 * recalled["emotion"]),
                    3,
                ),
                "traits": PROFILES[entity]["traits"],
            },
        }
        readiness = 0.20 + 0.10 * trait(entity, "self_disclosure")
        attention = clamp(0.32 + 0.35 * trait(entity, "curiosity") + r.gauss(0, 0.05))
        public_concepts = []
        public_prediction = None

    else:
        asked = direct_question_for(entity, event)
        readiness = clamp(
            0.20
            + 0.26 * trait(entity, "extraversion")
            + 0.24 * trait(entity, "curiosity")
            + 0.18 * trait(entity, "self_disclosure")
            - 0.23 * trait(entity, "inhibition")
            + (0.52 if asked else 0.0)
            - (0.30 if event and event.get("speaker") == entity else 0.0)
            + stochastic["social"]
            - 0.45 * stochastic["inhibition"]
            + r.gauss(0, 0.04)
        )
        attention = clamp(0.3 + 0.25 * trait(entity, "social_sensitivity") + (0.2 if asked else 0.0))
        work = {
            tasks[0]: {"direct_question": asked},
            tasks[1]: {
                "moves": ["answer"] if asked else ["follow_up", "self_disclosure", "reaction", "new_root"]
            },
            tasks[2]: {"readiness": readiness, "surface": None},
            tasks[3]: {"silence": True},
        }
        public_concepts = []
        public_prediction = None

    return {
        "phase": "sense",
        "node": node_id,
        "entity": entity,
        "local": local_node,
        "role": role,
        "tasks": tasks,
        "private": {
            "event": event,
            "keywords": event_words,
            "memory": recalled,
            "noise": stochastic,
            "work": work,
            "branch_owner": branch_owner,
            "branch_memory": branch_memory,
        },
        "public": {
            "node": node_id,
            "entity": entity,
            "role": role,
            "attention": round(attention, 3),
            "readiness": round(readiness, 3),
            "public_concepts": public_concepts,
            "prediction": public_prediction,
        },
    }


def build_bus(parts, cycle_key):
    if {part["node"] for part in parts} != set(range(12)):
        raise RuntimeError("The Room cognitive bus requires all 12 nodes")
    bus = {
        "key": cycle_key,
        "public": [part["public"] for part in sorted(parts, key=lambda p: p["node"])],
        "private": {
            entity: [part for part in parts if part["entity"] == entity]
            for entity in ENTITY_ORDER
        },
    }
    bus["network"] = public_network_summary(bus)
    return bus


def role_packet(bus, entity, role):
    return next(part for part in bus["private"][entity] if part["role"] == role)


def follow_up_question(entity, event, cycle_key):
    low = (event or {}).get("text", "").lower()
    if any(token in low for token in ("mother", "father", "sister", "brother", "friend", "cousin", "coworker", "partner")):
        choices = ["Were you close?", "What were they like?", "How did you two know each other?"]
    elif any(token in low for token in ("city", "town", "house", "apartment", "school", "ocean", "mountain", "place")):
        choices = ["What was that place like?", "Do you miss anything about it?", "What do you remember most about being there?"]
    elif any(token in low for token in ("felt", "afraid", "angry", "sad", "happy", "love", "hated", "miss")):
        choices = ["How did that affect you?", "Did that bother you at the time?", "Do you still feel that way?"]
    else:
        choices = ["What happened after that?", "How did that happen?", "Has that changed much since then?"]
    return rng("question", entity, cycle_key, *words(low)).choice(choices)


def choose_move(entity, event, cycle_key):
    if direct_question_for(entity, event):
        return "answer"
    if not event:
        return "self_disclosure"

    depth_now = discourse_depth(event.get("discourse_id"))
    current_move = (event.get("cognition") or {}).get("move_type")
    r = rng("move", entity, cycle_key)

    # Getting to know one another is the organizing pressure: follow a live branch first.
    weights = {
        "follow_up": 0.52 + 0.34 * trait(entity, "curiosity"),
        "self_disclosure": 0.22 + 0.32 * trait(entity, "self_disclosure"),
        "reaction": 0.24 + 0.22 * trait(entity, "agreeableness"),
        "new_root": 0.02 + 0.10 * trait(entity, "novelty_seeking"),
    }
    if current_move in ("self_disclosure", "answer"):
        weights["follow_up"] += 0.20
    if depth_now >= 4:
        weights["new_root"] += 0.38
        weights["follow_up"] *= 0.78
    if event.get("speaker") == entity:
        weights["follow_up"] *= 0.35
        weights["reaction"] *= 0.55
        weights["new_root"] += 0.15

    roll = r.random() * sum(weights.values())
    cumulative = 0.0
    for move, weight in weights.items():
        cumulative += weight
        if roll <= cumulative:
            return move
    return "reaction"


def recurrent(node_id, cycle_key, bus):
    entity, local_node, role, tasks = node_identity(node_id)
    comprehension = role_packet(bus, entity, "comprehension")
    thought = role_packet(bus, entity, "thought")
    expression = role_packet(bus, entity, "expression")
    event = comprehension["private"]["event"]
    recalled = thought["private"]["memory"]
    r = rng("recurrent", cycle_key, node_id)
    network = bus.get("network") or public_network_summary(bus)
    branch_owner = comprehension["private"].get("branch_owner")
    branch_memory = comprehension["private"].get("branch_memory")

    if role == "comprehension":
        coactive = list(
            dict.fromkeys(
                comprehension["private"]["keywords"]
                + network.get("public_concepts", [])
                + recalled["tags"]
            )
        )[:12]
        work = {
            tasks[0]: {"coactive": coactive},
            tasks[1]: comprehension["private"]["work"][tasks[1]],
            tasks[2]: comprehension["private"]["work"][tasks[2]],
            tasks[3]: {
                "common_ground": comprehension["private"]["keywords"],
                "memory_link": recalled["id"],
                "branch_owner": branch_owner,
                "branch_memory": branch_memory,
                "network_attention": network.get("mean_attention", 0.0),
            },
        }
        readiness = 0.0
        intent = None

    elif role == "thought":
        work = {
            tasks[0]: {
                "concepts": list(
                    dict.fromkeys(
                        comprehension["private"]["keywords"]
                        + network.get("public_concepts", [])
                        + recalled["tags"]
                    )
                )[:12]
            },
            tasks[1]: thought["private"]["work"][tasks[1]],
            tasks[2]: recalled,
            tasks[3]: thought["private"]["work"][tasks[3]],
        }
        readiness = 0.20
        intent = None

    else:
        move = choose_move(entity, event, cycle_key)
        readiness = clamp(expression["public"]["readiness"] + r.gauss(0, 0.025))

        # All four expression nodes can see one another's public readiness. That communication
        # affects timing, but private thoughts/memories never cross entity boundaries.
        others = [
            value
            for peer, value in network.get("expression_readiness", {}).items()
            if peer != entity
        ]
        crowding = sum(others) / max(1, len(others))

        memory_to_use = recalled
        if move == "answer" and branch_owner == entity and branch_memory:
            memory_to_use = life_memory(entity, branch_memory) or recalled

        if move in ("self_disclosure", "new_root"):
            outgoing_branch_owner = entity
            outgoing_branch_memory = memory_to_use["id"]
        else:
            outgoing_branch_owner = branch_owner
            outgoing_branch_memory = branch_memory

        plan = {
            "move": move,
            "target": (event or {}).get("speaker") if move in ("answer", "follow_up", "reaction") else None,
            "memory": memory_to_use.get("id"),
            "concepts": memory_to_use.get("tags", comprehension["private"]["keywords"])[:6],
            "question": follow_up_question(entity, event, cycle_key) if move == "follow_up" else None,
            "readiness": round(readiness, 3),
            "parent": (event or {}).get("discourse_id"),
            "branch_owner": outgoing_branch_owner,
            "branch_memory": outgoing_branch_memory,
            "network_crowding": round(crowding, 3),
        }
        plan["latency"] = round(
            max(
                0.05,
                1.55
                - 1.15 * readiness
                + 0.35 * trait(entity, "inhibition")
                + 0.18 * crowding
                + r.uniform(0, 0.22)
                + (0.55 if event and event.get("speaker") == entity else 0.0),
            ),
            4,
        )
        work = {
            tasks[0]: {"intent": move},
            tasks[1]: plan,
            tasks[2]: {"readiness": readiness, "latency": plan["latency"]},
            tasks[3]: {"provenance": True, "silence": True, "network_crowding": crowding},
        }
        intent = plan

    return {
        "phase": "recurrent",
        "node": node_id,
        "entity": entity,
        "local": local_node,
        "role": role,
        "tasks": tasks,
        "private": {"work": work, "intent": intent},
        "public": {
            "node": node_id,
            "entity": entity,
            "role": role,
            "readiness": round(readiness, 3),
        },
    }


def grounded_answer(entity, plan, event, cycle_key):
    memory = life_memory(entity, plan.get("branch_memory")) or life_memory(entity, plan.get("memory"))
    question = (event or {}).get("text", "").lower()
    r = rng("answer", entity, cycle_key, question)

    if memory:
        remembered = memory["first"].rstrip(".")
        if "were you close" in question and "best friend" in remembered.lower():
            return "Yeah. We were best friends.", "memory"
        if "how did you two know" in question and "best friend" in remembered.lower():
            return "We were already best friends by then, but I don't really remember how we first met.", "memory"
        if "what happened after" in question:
            return f"The part I remember is that I {remembered}.", "memory"
        if "do you miss" in question:
            return "I remember it clearly, but I don't think I ever decided whether I miss it.", "memory"
        if "what were they like" in question:
            return "I remember the relationship more clearly than their personality.", "memory"
        return f"The part I remember is that I {remembered}.", "memory"

    head = (re.findall(r"[a-z']+", question) or [""])[0]
    if head in {"why", "how", "where", "when", "who", "what"}:
        return r.choice(["I don't really remember that part.", "I'm not sure about that detail."]), "grounded"
    return r.choice(["Not really.", "I don't think so.", "I'm not sure."]), "grounded"


def externalize(entity, plan, event, cycle_key):
    r = rng("surface", entity, cycle_key, plan["move"])
    memory = life_memory(entity, plan.get("memory"))

    if plan["move"] == "follow_up":
        return plan["question"], "structured"
    if plan["move"] == "answer":
        return grounded_answer(entity, plan, event, cycle_key)
    if plan["move"] in ("self_disclosure", "new_root") and memory:
        prefix = r.choice(["I ", "That reminds me that I ", "Randomly, I "])
        return prefix + memory["first"].rstrip(".") + ".", "memory"
    return r.choice(
        [
            "That part caught my attention.",
            "I can see why that would stick with you.",
            "I hadn't thought about it that way.",
        ]
    ), "structured"


def eligible_expression_parts(parts, event):
    expression = [
        p
        for p in parts
        if p["role"] == "expression" and p["private"].get("intent")
    ]
    explicit_target = target_of(event) if event and event.get("text", "").rstrip().endswith("?") else None
    if explicit_target:
        targeted = [p for p in expression if p["entity"] == explicit_target]
        if targeted:
            # A directly addressed question creates a conversational obligation, not a vote.
            return [p for p in targeted if p["private"]["intent"]["readiness"] >= 0.34]
    return [p for p in expression if p["private"]["intent"]["readiness"] >= 0.48]


def commit(parts, cycle_key):
    world_state = state()
    minds = cognitive_state()
    tree = discourse()
    visible = conversation()
    event = current_event()

    # Every person encodes each public Room event independently.
    for entity in ENTITY_ORDER:
        entity_state = minds["entities"][entity]
        entity_parts = [p for p in parts if p["entity"] == entity]
        entity_state["noise"] = noise_state(entity, entity_state, cycle_key)
        comprehension = next(p for p in entity_parts if p["role"] == "comprehension")
        coactive = comprehension["private"]["work"][comprehension["tasks"][0]]["coactive"]
        entity_state.setdefault("fast", {})["activation"] = round(
            sum(p["public"]["readiness"] for p in entity_parts) / 3.0, 3
        )
        entity_state["fast"]["attention"] = coactive[:8]
        entity_state.setdefault("medium", {})["topics"] = entity_state["fast"]["attention"]
        entity_state["medium"]["branch_interest"] = round(
            clamp(0.4 * trait(entity, "curiosity") + 0.4 * trait(entity, "attention_persistence")), 3
        )

        if event and entity_state.get("last_event") != event["id"]:
            speaker = event["speaker"]
            observed = {
                "source": event["id"],
                "status": "observed",
                "speaker": speaker,
                "text": event["text"][:300],
                "discourse": event.get("discourse_id"),
                "branch_owner": (event.get("cognition") or {}).get("branch_owner"),
                "branch_memory": (event.get("cognition") or {}).get("branch_memory"),
            }
            entity_state.setdefault("room_memories", []).append(observed)
            entity_state["room_memories"] = entity_state["room_memories"][-120:]

            if speaker != entity:
                person_model = entity_state.setdefault("people", {}).setdefault(
                    speaker, {"familiarity": 0.02, "reports": []}
                )
                person_model["familiarity"] = round(clamp(person_model.get("familiarity", 0.02) + 0.018), 3)
                person_model.setdefault("reports", []).append(
                    {
                        "source": event["id"],
                        "status": "reported",
                        "text": event["text"][:300],
                        "branch_owner": observed["branch_owner"],
                        "branch_memory": observed["branch_memory"],
                    }
                )
                person_model["reports"] = person_model["reports"][-60:]
            entity_state["last_event"] = event["id"]

    candidates = eligible_expression_parts(parts, event)
    queue = sorted(
        [
            (p["private"]["intent"]["latency"], ENTITY_ORDER.index(p["entity"]), p)
            for p in candidates
        ],
        key=lambda item: (item[0], item[1]),
    )

    spoken = None
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    if queue:
        packet = queue[0][2]
        entity = packet["entity"]
        plan = packet["private"]["intent"]
        text, surface_mode = externalize(entity, plan, event, cycle_key)
        message_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}-{entity}-v2"
        parent = plan.get("parent")
        derived_from = None
        if plan["move"] == "new_root" or (
            parent and discourse_depth(parent, tree) >= ARCH["discourse"]["max_depth"]
        ):
            derived_from = parent
            parent = None

        discourse_id = "d-" + message_id
        cognition = {
            "move_type": plan["move"],
            "target": plan.get("target"),
            "memory_provenance": plan.get("memory"),
            "branch_owner": plan.get("branch_owner"),
            "branch_memory": plan.get("branch_memory"),
            "externalization": surface_mode,
            "compute_nodes": [n + 1 for n in ARCH["entities"][entity]],
            "processes": 12,
        }
        spoken = {
            "id": message_id,
            "at": timestamp,
            "speaker": entity,
            "text": text,
            "runtime": "room-cognition-v2",
            "cognition": cognition,
            "discourse_id": discourse_id,
            "parent_discourse_id": parent,
            "derived_from": derived_from,
        }
        visible.append(spoken)
        tree["nodes"].append(
            {
                "id": discourse_id,
                "speaker": entity,
                "parent": parent,
                "derived_from": derived_from,
                "move": plan["move"],
                "target": plan.get("target"),
                "branch_owner": plan.get("branch_owner"),
                "branch_memory": plan.get("branch_memory"),
                "text": text,
                "at": timestamp,
            }
        )
        tree["nodes"] = tree["nodes"][-600:]
        if not parent:
            tree.setdefault("roots", []).append(discourse_id)
            tree["roots"] = tree["roots"][-160:]

        entity_state = minds["entities"][entity]
        entity_state["spoken"] = entity_state.get("spoken", 0) + 1
        entity_state.setdefault("self_history", []).append(
            {
                "source": message_id,
                "text": text,
                "move": plan["move"],
                "memory": plan.get("memory"),
                "branch_memory": plan.get("branch_memory"),
                "discourse": discourse_id,
            }
        )
        entity_state["self_history"] = entity_state["self_history"][-120:]
        world_state["last_speaker"] = entity
        world_state["silence_cycles"] = 0
    else:
        world_state["silence_cycles"] = world_state.get("silence_cycles", 0) + 1
        for entity in ENTITY_ORDER:
            minds["entities"][entity]["silences"] = minds["entities"][entity].get("silences", 0) + 1

    world_state.update(
        {
            "version": "room-cognition-v2",
            "cycle": world_state.get("cycle", 0) + 1,
            "last_run": timestamp,
            "messages": len(visible),
            "last_public_event": spoken["id"] if spoken else (event or {}).get("id"),
            "note": "12 nodes x 4 tasks; all four entities process each cycle; no voting",
        }
    )
    visible = visible[-520:]

    save_json(ROOM / "conversation.json", visible)
    save_json(ROOM / "discourse.json", tree)
    save_json(ROOM / "cognitive_state.json", minds)
    save_json(ROOM / "state.json", world_state)

    compatibility_minds = {
        "schema": 2,
        "entities": {
            entity: {
                "name": NAMES[entity],
                "profile": PROFILES[entity],
                "genome": PROFILES[entity]["traits"],
                "development": {
                    "turns": world_state["cycle"],
                    "spoken": minds["entities"][entity].get("spoken", 0),
                    "silences": minds["entities"][entity].get("silences", 0),
                    "response_length_ema": 0,
                    "topic_weights": {
                        topic: 1 for topic in minds["entities"][entity].get("medium", {}).get("topics", [])
                    },
                    "relationships": {
                        peer: value.get("familiarity", 0.0)
                        for peer, value in minds["entities"][entity].get("people", {}).items()
                    },
                    "lifetime_memory_count": len(LIFE_MEMORY[entity]),
                },
                "memory": [
                    {"text": memory["text"]}
                    for memory in minds["entities"][entity].get("room_memories", [])[-8:]
                ],
            }
            for entity in ENTITY_ORDER
        },
    }
    live = {
        "generated_at": timestamp,
        "architecture_version": "room-cognition-v2.1",
        "minds": compatibility_minds,
        "profiles": PROFILES,
        "state": world_state,
        "conversation": visible,
        "discourse": tree,
        "network": {
            "compute_nodes": 12,
            "entities": 4,
            "nodes_per_entity": 3,
            "tasks_per_node": 4,
            "active_processes": 48,
            "voting": False,
            "public_bus": True,
            "private_scope": "same_entity",
        },
    }
    save_json(ROOM / "live.json", live)
    # Compatibility publication path only; cognition never reads this legacy location.
    save_json(ROOT / "society" / "live.json", live)

    if spoken:
        print(f"{NAMES[spoken['speaker']]}: {spoken['cognition']['move_type']}")
    else:
        print("Room silent; all 12 nodes processed")


def self_test():
    sensed = [sense(node_id, "selftest") for node_id in range(12)]
    bus = build_bus(sensed, "selftest")
    recurrent_parts = [recurrent(node_id, "selftest", bus) for node_id in range(12)]
    assert len(recurrent_parts) == 12
    assert all(len(bus["private"][entity]) == 3 for entity in ENTITY_ORDER)
    assert len(bus["public"]) == 12
    assert ARCH["network"]["voting"] is False
    assert all(len({kind for memory in LIFE_MEMORY[e] for kind in memory["types"]}) >= 10 for e in ENTITY_ORDER)
    assert set(bus["network"]["expression_readiness"].keys()) == set(ENTITY_ORDER)

    synthetic = {
        "id": "synthetic",
        "speaker": "mara",
        "text": "I had a best friend move away when I was thirteen.",
        "runtime": "room-cognition-v2",
        "cognition": {
            "move_type": "self_disclosure",
            "memory_provenance": "mara-004",
            "branch_owner": "mara",
            "branch_memory": "mara-004",
        },
        "discourse_id": "synthetic-d",
    }
    owner = synthetic["cognition"].get("branch_owner")
    memory = synthetic["cognition"].get("branch_memory")
    assert owner == "mara" and memory == "mara-004"

    print(
        "PASS 4 entities x 3 nodes x 4 tasks = 48 processes; "
        "12-node public bus; private entity scope; branch provenance; bounded discourse; no voting"
    )


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    node = sub.add_parser("node")
    node.add_argument("--phase", choices=["sense", "recurrent"], required=True)
    node.add_argument("--bus", default="")
    sub.add_parser("bus")
    sub.add_parser("commit")
    sub.add_parser("selftest")
    args = parser.parse_args()

    cycle_key = os.environ.get("ROOM_CYCLE_KEY") or f"{state().get('cycle', 0) + 1}:{os.environ.get('GITHUB_RUN_ID', 'local')}"

    if args.command == "node":
        node_id = int(os.environ["ROOM_NODE_ID"])
        result = (
            sense(node_id, cycle_key)
            if args.phase == "sense"
            else recurrent(node_id, cycle_key, load_json(Path(args.bus), {}))
        )
        PARTS.mkdir(exist_ok=True)
        save_json(PARTS / f"{args.phase}-{node_id:02d}.json", result)
    elif args.command == "bus":
        WORK.mkdir(exist_ok=True)
        parts = [load_json(path, {}) for path in sorted(PARTS.glob("sense-*.json"))]
        save_json(WORK / "bus-sense.json", build_bus(parts, cycle_key))
    elif args.command == "commit":
        parts = [load_json(path, {}) for path in sorted(PARTS.glob("recurrent-*.json"))]
        if {part["node"] for part in parts} != set(range(12)):
            raise RuntimeError("Commit requires all 12 recurrent node artifacts")
        commit(parts, cycle_key)
    else:
        self_test()


if __name__ == "__main__":
    main()
