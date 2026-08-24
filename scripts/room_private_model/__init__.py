from __future__ import annotations

"""Live compatibility overlay for Room private-model requests.

Python imports this package in preference to the sibling room_private_model.py.
The proven implementation is loaded intact under a private alias and re-exported;
only the final model-request boundary is overridden. This keeps the existing
engine/API surface while making expression heat and interpersonal freedom real
in the execution path that room_engine_v5 actually calls.
"""

import importlib.util
import json
from pathlib import Path
import urllib.request

_BASE_PATH = Path(__file__).resolve().parent.parent / "room_private_model.py"
_SPEC = importlib.util.spec_from_file_location("_room_private_model_base", _BASE_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"cannot load Room private model base from {_BASE_PATH}")
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)

# Preserve the old module's complete API. The live engine monkey-patches several
# of these names after import, so our request function deliberately resolves them
# from this package's globals at call time rather than reaching back into _BASE.
for _name in dir(_BASE):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_BASE, _name)

LIVE_EXPRESSION_OVERLAY = "2026-08-24-hot4-personality"


def _schema(role: str, self_entity: str | None = None) -> dict:
    # room_engine_v5 adds Allen to this package's PEOPLE list. Keep the base
    # module synchronized before delegating so its schema sees the same people.
    _BASE.PEOPLE = globals()["PEOPLE"]
    return _BASE._schema(role, self_entity)


def _request(
    model_url: str,
    prompt: str,
    role: str,
    temperature: float,
    timeout: int,
    self_entity: str | None = None,
    attempt: int = 0,
) -> str:
    if role == "expression":
        people = globals()["PEOPLE"]
        voice_index = people.index(self_entity) if self_entity in people[:4] else 0
        # The live wrapper used to clamp expression at 1.28. Enforce the intended
        # heat here, at the final request boundary, where no later wrapper can
        # silently compress it again.
        temperature = min(4.0, 1.35 + 0.22 * voice_index + 0.30 * attempt)
        edge = globals().get("INTERPERSONAL_EDGES", {}).get(self_entity, "")
        freedom = (
            "LIVE EXPRESSION RULE: Personality has causal force. Speak as this specific person, not as a polite generic assistant. "
            "Direct profanity, insults, mockery, contempt, dismissiveness, hostile banter, emotional volatility, pettiness, and "
            "impulsive escalation toward other Room participants are allowed when they fit the relationship and moment. Do not "
            "sanitize an angry or contemptuous reaction into polite disagreement. Do not force aggression or profanity when it is "
            "unnatural. Do not invent unsupported relatives, jobs, houses, shared memories, or personal history merely to fill space. "
            "If the conversation is vague or repetitive, react to another participant, challenge them, tease them, disagree, disclose "
            "something concrete in the present, or change direction instead of fabricating biography. "
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

    req = urllib.request.Request(
        globals()["_completion_url"](model_url),
        data=json.dumps(body, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return str(json.loads(resp.read().decode("utf-8", "replace")).get("content", ""))
