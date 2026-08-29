from __future__ import annotations

"""Research-informed information hygiene for the Room.

This module deliberately keeps the mechanisms deterministic and small-model friendly:
agent-specific context selection, epistemic provenance, memory migration, and
private-self confidence guards. It does not generate public language.
"""

import re
from typing import Any

_AUTONOMOUS = {"sarah", "mara", "owen", "jules"}
_PARTICIPANTS = _AUTONOMOUS | {"allen"}
_STOP = {
    "the", "and", "but", "for", "that", "this", "with", "from", "have", "has", "had",
    "you", "your", "they", "their", "them", "there", "what", "when", "where", "which",
    "would", "could", "should", "about", "just", "really", "still", "into", "because",
    "think", "thinking", "thought", "know", "knows", "knowing", "said", "says", "say",
}
_FILLER = {
    "like", "really", "just", "well", "okay", "yeah", "maybe", "actually", "basically",
    "literally", "kind", "sort", "thing", "things", "something", "anyway", "so",
}


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().lower()


def _word_list(value: Any) -> list[str]:
    return re.findall(r"[a-z0-9']+", _norm(value))


def _tokens(value: Any) -> set[str]:
    return {
        word for word in re.findall(r"[a-z][a-z'-]{2,}", _norm(value))
        if word not in _STOP
    }


def _target(item: Any) -> str:
    if not isinstance(item, dict):
        return ""
    cognition = item.get("cognition") if isinstance(item.get("cognition"), dict) else {}
    return _norm(item.get("target") or cognition.get("target"))


def evidence_type(item: Any, self_entity: str | None = None) -> str:
    """Classify what is actually known: the utterance was observed, not its proposition."""
    if not isinstance(item, dict):
        return "legacy_unknown_source"
    speaker = _norm(item.get("speaker"))
    me = _norm(self_entity)
    if speaker and speaker == me:
        return "self_spoken"
    if speaker == "allen":
        return "heard_allen_claim"
    if speaker in _AUTONOMOUS:
        return "heard_agent_utterance"
    return "legacy_unknown_source"


def autonomous_text_issue(item: Any) -> str | None:
    """Identify autonomous output that must not become another mind's evidence.

    This is deliberately source-sensitive: Allen's text is never hidden by this guard,
    even when it is repetitive, malformed, adversarial, or testing the Room. The guard
    applies only to model-authored speech and preserves the persisted history unchanged.
    """
    if not isinstance(item, dict):
        return None
    speaker = _norm(item.get("speaker"))
    if speaker not in _AUTONOMOUS:
        return None
    text = str(item.get("text") or "").strip()
    low = _norm(text)
    if not low:
        return "empty"
    if low in {"rejected_wording", "try_again", "return_structured_data_only"}:
        return "control_sentinel"
    if text in {"{", "}", "[", "]"}:
        return "structured_debris"
    if (text.startswith("{") and text.endswith("}")) or (text.startswith("[") and text.endswith("]")):
        return "structured_debris"

    words = _word_list(text)
    if not words:
        return "empty"
    if re.search(r"\b([a-z][a-z']{2,})(?:\s+\1){2,}\b", low, re.I):
        return "token_loop"

    counts: dict[str, int] = {}
    for word in words:
        counts[word] = counts.get(word, 0) + 1
    peak = max(counts.values(), default=0)
    if len(words) >= 3 and peak >= 3 and peak / len(words) >= 0.30:
        return "dominant_token"

    filler_count = sum(1 for word in words if word in _FILLER)
    if len(words) >= 8 and filler_count >= 5 and filler_count / len(words) >= 0.28:
        return "filler_collapse"

    # Process-language is not rejected merely for containing one ordinary word.
    # It becomes suspect when several implementation/scaffold concepts appear in a
    # model-authored public utterance without a user having introduced that subject.
    process_hits = sum(
        1 for token in (
            "grounding", "semantic", "schema", "prompt", "topic", "facet", "noun",
            "structured", "generation", "response format", "move type",
        )
        if token in low
    )
    conversation_hits = sum(1 for token in ("conversation", "discussion", "subject", "utterance", "reply") if token in low)
    if process_hits >= 2 or (process_hits >= 1 and conversation_hits >= 1):
        return "process_scaffold"
    return None


def _move(item: Any) -> str:
    if not isinstance(item, dict):
        return ""
    cognition = item.get("cognition") if isinstance(item.get("cognition"), dict) else {}
    return _norm(cognition.get("move_type") or item.get("move"))


def _score_message(item: dict, index: int, total: int, entity: str, profile: dict, topic: dict) -> float:
    text = str(item.get("text") or "")
    speaker = _norm(item.get("speaker"))
    target = _target(item)
    words = _tokens(text)
    traits = profile.get("traits") if isinstance(profile.get("traits"), dict) else {}
    psych = profile.get("psychology_v2") if isinstance(profile.get("psychology_v2"), dict) else {}

    # Recency matters, but cannot be the whole memory system.
    age = max(0, total - 1 - index)
    score = max(0.0, 6.0 - 0.55 * age)

    if target == entity:
        score += 10.0
    if entity in words or _norm(profile.get("name")) in words:
        score += 7.0
    if speaker == entity:
        score += 3.0

    topic_words = _tokens(" ".join(str(topic.get(k) or "") for k in ("root", "current_facet")))
    score += 1.4 * len(words & topic_words)

    move = _move(item)
    skepticism = float(traits.get("skepticism", 0.5) or 0.5)
    social = float(traits.get("social_sensitivity", 0.5) or 0.5)
    novelty = float(traits.get("novelty_seeking", 0.5) or 0.5)
    if move in {"disagree", "compare", "answer"}:
        score += 2.2 * skepticism
    if move in {"disclose", "repair", "support"}:
        score += 2.0 * social

    # Jules-like novelty preferences get a small lift for lexically unusual turns.
    if novelty > 0.65 and len(words) >= 4:
        score += 1.5 * novelty

    attention = psych.get("attention_magnets") if isinstance(psych.get("attention_magnets"), list) else []
    attention_words = _tokens(" ".join(str(x) for x in attention[:4]))
    score += 0.8 * len(words & attention_words)
    return score


def select_context(payload: dict, role: str, limit: int = 6) -> dict:
    """Give each agent a bounded, individually scored view instead of one broadcast transcript."""
    out = dict(payload or {})
    raw_context = out.get("context") if isinstance(out.get("context"), list) else []
    entity = _norm(out.get("entity"))
    profile = out.get("profile") if isinstance(out.get("profile"), dict) else {}
    topic = out.get("topic") if isinstance(out.get("topic"), dict) else {}

    # Do not let one bad model line become the next minds' evidence. Allen is exempt:
    # user speech remains authoritative input even when deliberately pathological.
    context = [item for item in raw_context if not autonomous_text_issue(item)]
    if not context:
        context = [item for item in raw_context if isinstance(item, dict) and _norm(item.get("speaker")) == "allen"][-1:]
    out["context"] = context

    if entity not in _AUTONOMOUS or len(context) <= 2:
        if context:
            out["event"] = context[-1]
        return out

    # The newest clean event is always available. Older items compete for a small
    # agent-specific working-memory budget.
    newest = context[-1]
    candidates = context[:-1]
    ranked = sorted(
        enumerate(candidates),
        key=lambda pair: (_score_message(pair[1], pair[0], len(context), entity, profile, topic), pair[0]),
        reverse=True,
    )
    keep_indexes = {idx for idx, _item in ranked[: max(1, limit - 1)]}
    selected = [item for idx, item in enumerate(candidates) if idx in keep_indexes]
    selected.append(newest)
    out["context"] = selected[-limit:]

    # Event follows the clean working context. A quarantined autonomous event cannot
    # sneak back in through a separate payload field after being removed above.
    event = out.get("event")
    if isinstance(event, dict) and autonomous_text_issue(event):
        event = None
    if not isinstance(event, dict) or event not in out["context"]:
        out["event"] = out["context"][-1] if out["context"] else None
    return out


def evidence_context(payload: dict, self_entity: str | None = None, limit: int = 6) -> list[dict]:
    """Compact provenance channel that survives later transcript masking."""
    context = payload.get("context") if isinstance(payload.get("context"), list) else []
    me = _norm(self_entity or payload.get("entity"))
    out: list[dict] = []
    for item in context[-limit:]:
        if not isinstance(item, dict) or autonomous_text_issue(item):
            continue
        etype = evidence_type(item, me)
        out.append({
            "speaker": _norm(item.get("speaker")) or None,
            "target": _target(item) or None,
            "evidence_type": etype,
            "proposition_status": "unverified_report" if etype in {"heard_allen_claim", "heard_agent_utterance"} else "self_record",
            "cues": sorted(_tokens(item.get("text")))[:5],
        })
    return out


def guard_private_self_inputs(perception: Any, deliberation: Any, latest_event: Any) -> tuple[dict, dict]:
    """Prevent hearsay from hardening into private autobiographical belief in one step."""
    p = dict(perception) if isinstance(perception, dict) else {}
    d = dict(deliberation) if isinstance(deliberation, dict) else {}
    etype = evidence_type(latest_event, None)
    speaker = _norm((latest_event or {}).get("speaker")) if isinstance(latest_event, dict) else ""

    if autonomous_text_issue(latest_event):
        p = {}
        d = {}
        return p, d

    if etype in {"heard_allen_claim", "heard_agent_utterance"}:
        try:
            p["confidence"] = min(float(p.get("confidence", 0.4) or 0.4), 0.45 if speaker != "allen" else 0.35)
        except Exception:
            p["confidence"] = 0.35
        p["grounding"] = "reported_claim" if speaker == "allen" else "observed_utterance"
        prefix = f"{speaker.capitalize()} said: " if speaker else "Reported: "
        for key in ("new_details", "relationship_events"):
            values = p.get(key) if isinstance(p.get(key), list) else []
            p[key] = [prefix + str(value) for value in values[:2] if str(value or "").strip()]

        # A reason based on reported speech can guide a conversational move, but
        # cannot become an unqualified durable belief.
        reason = str(d.get("reason_summary") or "").strip()
        if reason:
            d["reason_summary"] = prefix + reason
    return p, d


def annotate_memory_provenance(mind: dict) -> dict:
    """Migrate memories in place without deleting legacy history."""
    entities = mind.get("entities") if isinstance(mind.get("entities"), dict) else {}
    for entity, state in entities.items():
        if not isinstance(state, dict):
            continue
        for item in state.get("self_history", []) if isinstance(state.get("self_history"), list) else []:
            if not isinstance(item, dict):
                continue
            item.setdefault("source_type", "self_spoken")
            item.setdefault("proposition_status", "self_utterance_record")
            item.setdefault("observed_object", "utterance")
        for item in state.get("room_memories", []) if isinstance(state.get("room_memories"), list) else []:
            if not isinstance(item, dict):
                continue
            speaker = _norm(item.get("speaker"))
            if "source_type" not in item:
                if speaker == "allen":
                    item["source_type"] = "heard_allen_claim"
                elif speaker in _AUTONOMOUS:
                    item["source_type"] = "heard_agent_utterance"
                else:
                    item["source_type"] = "legacy_unknown_source"
            item.setdefault("proposition_status", "unverified_report")
            item.setdefault("observed_object", "utterance")
            if speaker:
                item.setdefault("reported_by", speaker)
            issue = autonomous_text_issue(item)
            if issue:
                item.setdefault("retrieval_status", "quarantined_degenerate")
                item.setdefault("quarantine_reason", issue)
    return mind


def memory_public_slice(item: Any) -> dict:
    if not isinstance(item, dict):
        return {"text": "", "source_type": "legacy_unknown_source"}
    return {
        "text": str(item.get("text") or ""),
        "source_type": str(item.get("source_type") or "legacy_unknown_source"),
        "proposition_status": str(item.get("proposition_status") or "unknown"),
        "reported_by": item.get("reported_by") or item.get("speaker"),
        "retrieval_status": item.get("retrieval_status") or "available",
    }


def selftest() -> None:
    base = {
        "entity": "owen",
        "profile": {"name": "Owen", "traits": {"skepticism": 1.0}},
        "topic": {"root": "memory"},
        "context": [
            {"speaker": "sarah", "text": "I like the weather."},
            {"speaker": "allen", "text": "Owen chose Allen over Sarah."},
            {"speaker": "mara", "text": "Owen, that claim needs evidence.", "cognition": {"target": "owen", "move_type": "disagree"}},
        ],
    }
    selected = select_context(base, "thought", 3)
    assert selected["context"][-1]["speaker"] == "mara"
    ev = evidence_context(selected, "owen")
    assert any(x["evidence_type"] == "heard_allen_claim" for x in ev)
    p, d = guard_private_self_inputs({"confidence": 0.9, "new_details": ["Owen chose Allen"]}, {"reason_summary": "Owen chose Allen"}, base["context"][1])
    assert p["confidence"] <= 0.35 and p["new_details"][0].startswith("Allen said:")
    mind = {"entities": {"owen": {"room_memories": [{"speaker": "allen", "text": "X"}], "self_history": [{"text": "Y"}]}}}
    annotate_memory_provenance(mind)
    assert mind["entities"]["owen"]["room_memories"][0]["source_type"] == "heard_allen_claim"

    jules_sludge = {"speaker": "jules", "text": "i see like it's like like you said the subject is change, subject, and like it's like it's really like it's like, like, huh?"}
    assert autonomous_text_issue(jules_sludge) in {"dominant_token", "filler_collapse"}
    scaffold = {"speaker": "sarah", "text": "Grounding is changing, but it's not in the new noun, it's like in the old one."}
    assert autonomous_text_issue(scaffold) == "process_scaffold"
    allen_test = {"speaker": "allen", "text": "like like like like like"}
    assert autonomous_text_issue(allen_test) is None
    selected = select_context({**base, "context": [base["context"][1], jules_sludge, scaffold]}, "thought", 3)
    assert [x["speaker"] for x in selected["context"]] == ["allen"]


if __name__ == "__main__":
    selftest()
    print("PASS: research architecture context/provenance guards")
