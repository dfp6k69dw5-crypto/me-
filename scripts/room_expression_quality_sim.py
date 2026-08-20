#!/usr/bin/env python3
from __future__ import annotations

import json
import os

import room_engine_v5 as engine


def payload(context_text: str = "What did you think of the ending?") -> dict:
    return {
        "entity": "sarah",
        "profile": {"traits": {"curiosity": 0.88, "skepticism": 0.84}},
        "event": {"speaker": "mara", "text": context_text, "cognition": {"target": "sarah"}},
        "context": [{"speaker": "mara", "text": context_text, "cognition": {"target": "sarah"}}],
        "topic": {"root": "books", "current_facet": "ending", "facets": ["ending", "characters"], "shared_references": [], "unresolved": []},
        "partner": "mara",
        "relationship": {"warmth": 0.6, "respect": 0.6},
        "deliberation": {"action": "ANSWER", "focus": "ending", "new_information_goal": "give a distinct reaction"},
    }


def expression(text: str) -> str:
    return json.dumps({
        "target": "mara",
        "move": "answer",
        "utterance": text,
        "semantic_terms": ["books", "ending"],
    })


def run_sequence(items: list[str], source: dict | None = None):
    calls: list[str] = []
    original = engine._private_model._request
    old_prompt = os.environ.get("ROOM_NODE_PROMPT")
    old_url = os.environ.get("ROOM_MODEL_URL")

    def fake_request(_url, prompt, _role, _temperature, _timeout, _self_entity=None, _attempt=0):
        calls.append(prompt)
        return items[min(len(calls) - 1, len(items) - 1)]

    engine._private_model._request = fake_request
    os.environ["ROOM_NODE_PROMPT"] = "enabled-for-simulator"
    os.environ["ROOM_MODEL_URL"] = "http://simulator.invalid"
    try:
        result = engine._private_run("expression", source or payload(), timeout=1)
    finally:
        engine._private_model._request = original
        if old_prompt is None:
            os.environ.pop("ROOM_NODE_PROMPT", None)
        else:
            os.environ["ROOM_NODE_PROMPT"] = old_prompt
        if old_url is None:
            os.environ.pop("ROOM_MODEL_URL", None)
        else:
            os.environ["ROOM_MODEL_URL"] = old_url
    return result, len(calls)


def require_retry(label: str, bad: str, good: str, source: dict | None = None):
    result, calls = run_sequence([expression(bad), expression(good)], source)
    actual = str(result.get("utterance") or "")
    assert calls >= 2, f"{label}: bad first expression was accepted: {actual!r}"
    assert actual == good, f"{label}: retry did not return clean expression: {actual!r}"


def main():
    require_retry(
        "malformed pronoun grammar",
        "I r excited to read more about it, and we r all looking forward to another novel.",
        "The ending interests me more than the book's reputation.",
    )

    require_retry(
        "self address",
        "Hey, Sarah. I think the ending is more interesting than the opening.",
        "Mara, I think the ending is more interesting than the opening.",
    )

    require_retry(
        "internal repetition",
        "The ending felt unresolved to me. The ending felt unresolved to me. I keep coming back to it.",
        "The unresolved ending works for me because it leaves the judgment with the reader.",
    )

    require_retry(
        "rambling expression",
        "I keep circling the same thought about this novel because the themes and characters make me feel inspired, and I keep circling the same thought about this novel because the themes and characters make me feel inspired, and I keep circling the same thought about this novel because the themes and characters make me feel inspired, and I keep circling the same thought about this novel because the themes and characters make me feel inspired, even though I have not added anything new yet.",
        "I like the moral ambiguity more than the book's reputation as a classic.",
    )

    previous = (
        "To Kill a Mockingbird is an excellent classic novel, and I am excited to read more about Harper Lee. "
        "I was surprised to discover it has a more prominent role in my collection. It is a good choice for "
        "someone who enjoys classic novels and has read a lot of them."
    )
    near_copy = (
        "Harper Lee is a well-known author and I am excited to read To Kill a Mockingbird. I was surprised to "
        "discover it has a prominent role in my collection. It is a good choice for someone who enjoys classic "
        "novels and has read a lot of them."
    )
    require_retry(
        "near-copy of recent speaker",
        near_copy,
        "I would rather talk about why the trial changes Scout's understanding of the adults around her.",
        payload(previous),
    )

    clean = "I liked the ambiguity at the end because it leaves the moral judgment less tidy."
    result, calls = run_sequence([expression(clean)])
    assert calls == 1, f"natural expression was over-rejected ({calls} attempts)"
    assert result.get("utterance") == clean

    print("ROOM EXPRESSION QUALITY SIM: GREEN")


if __name__ == "__main__":
    main()
