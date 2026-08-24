from __future__ import annotations

"""Live compatibility overlay for Room private-model requests.

Python imports this package in preference to the sibling room_private_model.py.
The proven implementation is loaded intact under a private alias and re-exported.
The overlay changes the live thought/expression boundary while preserving the
engine API and relationship context.
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

LIVE_EXPRESSION_OVERLAY = "2026-08-24-hot4-personality-v3"
_HEAT_LEVELS = (1.70, 2.10, 2.50, 3.00, 3.50, 4.00)
_THOUGHT_HEAT_LEVELS = (0.62, 0.78, 0.94, 1.10)
_RELATIONSHIP_KEYS = (
    "trust", "warmth", "tension", "respect", "predictability",
    "reciprocity", "disclosure_depth", "direct_familiarity", "exposure",
)


def _schema(role: str, self_entity: str | None = None) -> dict:
    # room_engine_v5 adds Allen after importing this package. Synchronize the
    # preserved implementation before delegating so target enums remain aligned.
    _BASE.PEOPLE = globals()["PEOPLE"]
    return _BASE._schema(role, self_entity)


def _compact_payload(payload: dict, role: str, self_entity: str | None = None) -> dict:
    """Preserve the proven compact payload while retaining interpersonal state."""
    compact = _BASE._compact_payload(payload, role, self_entity)
    if role == "expression" and isinstance(payload, dict):
        relationship = payload.get("relationship")
        if isinstance(relationship, dict):
            rel = {key: relationship.get(key) for key in _RELATIONSHIP_KEYS if key in relationship}
            if rel:
                compact["relationship_context"] = rel
    return compact


def _expression_temperature(self_entity: str | None, attempt: int) -> float:
    """Start genuinely hot, then cool retries so freedom does not destroy liveness."""
    heat_seed = globals()["_sample_seed"]("expression_heat", self_entity, 0)
    base = _HEAT_LEVELS[heat_seed % len(_HEAT_LEVELS)]
    return max(1.25, min(4.0, base - 0.45 * max(0, attempt)))


def _entity_from_prompt(prompt: str) -> str | None:
    match = re.search(r'"entity":"(sarah|mara|owen|jules)"', str(prompt or ""), re.I)
    return match.group(1).lower() if match else None


def _thought_temperature(entity: str | None, attempt: int) -> float:
    """Give deliberation enough variation to escape the generic SUPPORT attractor."""
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
            "SUPPORT is only one possible action and must not be the default. Use the supplied relationship state and personality: "
            "trust, warmth, tension, respect, familiarity, rivalry, insecurity, boredom, irritation, attraction, suspicion, pride, "
            "attachment, and unresolved friction may change the move. DISAGREE, COMPARE, CALLBACK, BRIDGE, CLOSE, DISCLOSE, REPAIR, "
            "ANSWER, DEEPEN, or SUPPORT are all legitimate when they fit. If the recent conversation keeps circling the same pleasant "
            "idea, do not obediently continue it: get bored, challenge an assumption, tease or confront another participant, revive an "
            "unresolved interpersonal thread, make a sharper comparison, close the stale subject, or deliberately change direction. "
            "Do not invent relatives, jobs, houses, past events, or shared memories. Do not plan generic chores or group projects unless "
            "the newest spoken line genuinely calls for that. The chosen action should feel causally connected to this person's motives "
            "and relationship with the target, even when that makes the exchange messy or uncomfortable. "
        )
        if edge:
            agency += "Persistent interpersonal edge for this thinker: " + edge + " "
        prompt = agency + "\n" + prompt

    if role == "expression":
        # Enforce heat here at the final request boundary. room_engine_v5 may
        # calculate an older temperature upstream, but it cannot clamp this one.
        temperature = _expression_temperature(self_entity, attempt)
        edge = globals().get("INTERPERSONAL_EDGES", {}).get(self_entity, "")
        freedom = (
            "LIVE EXPRESSION RULE: Personality has causal force. Speak as this specific person, not as a polite generic assistant. "
            "Use relationship_context when present: trust, warmth, tension, respect, familiarity, and reciprocity should affect how "
            "you interpret and answer the other person. Direct profanity, insults, mockery, contempt, dismissiveness, hostile banter, "
            "emotional volatility, pettiness, grudges, rivalry, and impulsive escalation toward other Room participants are allowed "
            "when they fit the person, relationship, and moment. Do not sanitize anger or contempt into polite disagreement. Do not "
            "force aggression or profanity when it would be unnatural. Follow the deliberated move rather than drifting back to generic "
            "support. Do not invent unsupported relatives, jobs, houses, shared memories, or personal history merely to fill space. If "
            "the conversation is vague or repetitive, react to another participant, challenge them, tease them, disagree, disclose "
            "something concrete in the present, or deliberately change direction instead of fabricating biography. "
        )
        if edge:
            freedom += "Persistent interpersonal edge for this speaker: " + edge + " "
        prompt = freedom + "\n" + prompt

    body = {
        "prompt": prompt,
        "n_predict": {"comprehension": 192, "thought": 220, "expression": 220}.get(role, 192),
        "temperature": temperature,
        "cache_prompt": True,
        # Resolve dynamically because room_engine_v5 replaces this package's
        # _schema with its compatibility wrapper after import.
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
