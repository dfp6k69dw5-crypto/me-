from __future__ import annotations

import re
from typing import Any

STOP = set("the a an and or but if then than this that these those it its is are was were be been being to of in on for with from by at as about into over under we i you he she they them our your their my me us do does did can could would should will just very really quite more most less few some any all one two what why how when where who which everyone everybody someone somebody".split())
NAMES = {"sarah", "mara", "owen", "jules", "allen"}


def _norm(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _terms(text: str) -> list[str]:
    out = []
    for word in re.findall(r"[a-z][a-z'-]{2,}", _norm(text)):
        word = word.strip("'-")
        if word in STOP or word in NAMES or word in out:
            continue
        out.append(word)
    return out[:8]


def classify_event(event: dict | None, context: list[dict] | None = None) -> list[str]:
    event = event or {}
    text = _norm(event.get("text"))
    target = _norm(((event.get("cognition") or {}).get("target")))
    labels: list[str] = []
    if re.search(r"\b(hi|hello|hey|good morning|good evening)\b", text):
        labels.append("greeting")
    if text.endswith("?"):
        labels.append("question")
    if re.search(r"\b(proof|evidence|source|show me|how do you know|why believe)\b", text):
        labels.append("evidence_request")
    if re.search(r"\b(let'?s talk|talk about|topic|discuss|what about)\b", text):
        labels.append("topic_bid")
    if re.search(r"\b(sorry|apologize|apologies|my fault|too harsh|i was wrong)\b", text):
        labels.append("repair_bid")
    if re.search(r"\b(winner|great|smart|brilliant|right|best|excellent|good point)\b", text):
        labels.append("praise_or_alignment")
    if re.search(r"\b(wrong|nonsense|stupid|bad argument|makes no sense|ridiculous|idiot)\b", text):
        labels.append("criticism_or_rejection")
    if re.search(r"\b(left out|exclude|excluded|ignore|ignored|doesn'?t get it|don'?t get it|everyone but|without you)\b", text):
        labels.append("exclusion")
    if re.search(r"\b(platypus|electroreceptor|monotreme|venom|quantum|recursive causation|axolotl|octopus)\b", text):
        labels.append("novel_or_odd_detail")
    names_in_text = [name for name in NAMES if re.search(rf"\b{re.escape(name)}\b", text)]
    if target in NAMES or names_in_text:
        labels.append("direct_address")
    terms = _terms(text)
    if len(terms) <= 2 and "greeting" not in labels and "question" not in labels:
        labels.append("fragment_or_ambiguous")
    recent_terms: set[str] = set()
    for item in (context or [])[-4:]:
        recent_terms.update(_terms(str(item.get("text", ""))))
    if terms and any(term not in recent_terms for term in terms):
        labels.append("new_information")
    return list(dict.fromkeys(labels or ["ordinary_turn"]))


def _schema_matches(profile: dict, labels: list[str], self_implicated: bool) -> list[dict]:
    active: list[dict] = []
    for item in profile.get("schema_vulnerabilities", []) or []:
        if not isinstance(item, dict):
            continue
        triggers = {str(x) for x in item.get("triggers", [])}
        matched = [
            label for label in labels
            if label in triggers
            and (self_implicated or label not in {"criticism_or_rejection", "exclusion", "praise_or_alignment"})
        ]
        if matched:
            active.append({
                "schema": item.get("name"),
                "trigger": matched[0],
                "interpretation_bias": item.get("interpretation_bias"),
                "coping_bias": item.get("coping_bias"),
            })
    return active


def appraise(entity: str, profile: dict, event: dict | None, context: list[dict] | None = None) -> dict:
    labels = classify_event(event, context)
    text = str((event or {}).get("text", "")).strip()
    speaker = str((event or {}).get("speaker") or "").lower() or None
    terms = _terms(text)
    text_low = _norm(text)
    target = _norm((((event or {}).get("cognition") or {}).get("target")))
    self_implicated = bool(target == entity or re.search(rf"\b{re.escape(entity)}\b", text_low))
    schema = _schema_matches(profile, labels, self_implicated)

    lenses: list[str] = []
    if "greeting" in labels or "direct_address" in labels or "question" in labels:
        lenses.append(str(profile.get("reciprocity_style", "")))
    if "topic_bid" in labels:
        lenses.append(str(profile.get("topic_mobility", "")))
    if "novel_or_odd_detail" in labels or "new_information" in labels:
        lenses.append(str(profile.get("novelty_response", "")))
    if "evidence_request" in labels:
        lenses.append(str(profile.get("evidence_style", "")))
    if "praise_or_alignment" in labels:
        lenses.extend([str(profile.get("praise_response", "")), str(profile.get("affiliation_style", ""))])
    if "criticism_or_rejection" in labels:
        lenses.extend([str(profile.get("criticism_response", "")), str(profile.get("disagreement_style", ""))])
    if "exclusion" in labels:
        lenses.extend([str(profile.get("status_sensitivity", "")), str(profile.get("affiliation_style", ""))])
    if "repair_bid" in labels:
        lenses.extend([str(profile.get("repair_recovery", "")), str(profile.get("affiliation_style", ""))])
    if not lenses:
        lenses.extend([str(profile.get("attention_magnets", "")), str(profile.get("topic_mobility", ""))])

    priority = "ground_latest_turn" if any(
        label in labels
        for label in ("greeting", "question", "direct_address", "topic_bid", "evidence_request", "repair_bid")
    ) else "integrate_latest_turn"
    if "fragment_or_ambiguous" in labels and "question" not in labels:
        priority = "clarify_or_interpret_fragment"

    return {
        "entity": entity,
        "partner": speaker,
        "self_implicated": self_implicated,
        "situation": labels,
        "grounding": {"source_text": text[:500], "terms": terms},
        "priority": priority,
        "personality_lens": [x for x in lenses if x][:4],
        "interpersonal_style": {
            "agency": profile.get("agency_style"),
            "communion": profile.get("communion_style"),
        },
        "schema_activation": schema,
        "coping_patterns": profile.get("coping_patterns"),
    }
