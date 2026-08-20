#!/usr/bin/env python3
from __future__ import annotations

import json
import os

import room_engine_v5 as engine


def payload(context_text: str = "What did you think of the ending?", speaker: str = "mara") -> dict:
    return {
        "entity": "sarah",
        "profile": {"traits": {"curiosity": 0.88, "skepticism": 0.84}},
        "event": {"speaker": speaker, "text": context_text, "cognition": {"target": "sarah"}},
        "context": [{"speaker": speaker, "text": context_text, "cognition": {"target": "sarah"}}],
        "topic": {"root": "books", "current_facet": "ending", "facets": ["ending", "characters"], "shared_references": [], "unresolved": []},
        "partner": speaker,
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
    prompts: list[str] = []
    original = engine._private_model._request
    old_prompt = os.environ.get("ROOM_NODE_PROMPT")
    old_url = os.environ.get("ROOM_MODEL_URL")

    def fake_request(_url, prompt, _role, _temperature, _timeout, _self_entity=None, _attempt=0):
        prompts.append(prompt)
        return items[min(len(prompts) - 1, len(items) - 1)]

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
    return result, prompts


def require_retry(label: str, bad: str, good: str, source: dict | None = None):
    result, prompts = run_sequence([expression(bad), expression(good)], source)
    actual = str(result.get("utterance") or "")
    assert len(prompts) >= 2, f"{label}: bad first expression was accepted: {actual!r}"
    assert actual == good, f"{label}: retry did not return clean expression: {actual!r}"


def require_first_try(label: str, text: str):
    result, prompts = run_sequence([expression(text)])
    assert len(prompts) == 1, f"{label}: natural expression was over-rejected ({len(prompts)} attempts)"
    assert result.get("utterance") == text


def main():
    schema = engine._private_model._schema("expression", "sarah")
    assert schema["properties"]["utterance"]["maxLength"] <= 420, "expression schema still permits rambling output"

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
    require_retry(
        "dangling truncation fragment",
        "The trial scene is the part I keep thinking about,",
        "The trial scene is the part I keep thinking about because Scout notices how adults rationalize unfairness.",
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

    # Fail-soft invariant: if the model keeps emitting the exact mechanical token
    # corruption seen live, the beat must not die after five identical attempts.
    malformed = "I r excited to read more about it, and we r all looking forward to another novel."
    salvaged, salvage_prompts = run_sequence([expression(malformed)] * 5)
    salvaged_text = str(salvaged.get("utterance") or "")
    assert salvaged_text, "persistent mechanical corruption killed the expression instead of being salvaged"
    assert " i r " not in f" {salvaged_text.lower()} " and " we r " not in f" {salvaged_text.lower()} ", salvaged_text
    assert len(salvaged_text) <= 420

    # Semantic-copy recovery: after two duplicate failures, stale AI wording must
    # leave the third prompt so generation can escape in the same beat.
    fresh = "I would rather switch to why people reread books that made them uncomfortable the first time."
    _result, copy_prompts = run_sequence([expression(near_copy), expression(near_copy), expression(fresh)], payload(previous))
    assert len(copy_prompts) >= 3
    assert previous not in copy_prompts[2], "third attempt still carries the stale AI loop context"

    # A real participant interruption is different: recovery may simplify context
    # but must never throw away Allen's actual newest words to escape repetition.
    allen_words = "Why do platypuses have bills?"
    allen_source = payload(allen_words, speaker="allen")
    allen_fresh = "The bill is packed with electroreceptors that help locate prey underwater."
    _result, allen_prompts = run_sequence([
        expression("Why do platypuses have bills? That is the question I keep thinking about."),
        expression("Why do platypuses have bills? That is the question I keep thinking about."),
        expression(allen_fresh),
    ], allen_source)
    assert len(allen_prompts) >= 3
    assert allen_words in allen_prompts[2], "fail-soft recovery discarded Allen's newest spoken words"

    require_first_try(
        "ordinary natural expression",
        "I liked the ambiguity at the end because it leaves the moral judgment less tidy.",
    )
    require_first_try(
        "literal R programming reference",
        "R is the programming language I use when I want to inspect a dataset quickly.",
    )
    require_first_try(
        "natural colon ending setup",
        "I keep coming back to one question: what did Scout understand that the adults missed?",
    )

    print("ROOM EXPRESSION QUALITY SIM: GREEN")


if __name__ == "__main__":
    main()
