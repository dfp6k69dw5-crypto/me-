#!/usr/bin/env python3
from __future__ import annotations

import json
import os

import room_engine_v5 as engine


def expression(text: str) -> str:
    return json.dumps({
        "target": "allen",
        "move": "answer",
        "utterance": text,
        "semantic_terms": ["platypus", "electroreception"],
    })


def main() -> None:
    truncated = (
        "I think we could explore different themes and use Harper Lee's writing as a foundation for a different genre. "
        "What themes do you have in mind for your next books or what"
    )
    repaired = engine._expression_quality.repair_expression(truncated, "sarah")
    assert repaired != truncated, "RED: mid-sentence truncation survived repair"
    assert not repaired.lower().endswith("or what"), "RED: dangling final clause survived repair"
    assert repaired[-1:] in ".!?", "repaired expression is not grammatically closed"
    assert engine._expression_quality.repair_expression("Guess what?", "sarah") == "Guess what?"
    assert engine._expression_quality.repair_expression("I think the ending matters.", "sarah") == "I think the ending matters."

    allen_words = "Why do platypuses have bills?"
    payload = {
        "entity": "sarah",
        "profile": {"traits": {"curiosity": 0.88, "skepticism": 0.84}},
        "event": {"speaker": "allen", "text": allen_words, "cognition": {"target": "sarah"}},
        "context": [{"speaker": "allen", "text": allen_words, "cognition": {"target": "sarah"}}],
        "topic": {"root": "platypuses", "current_facet": "electroreception", "facets": ["electroreception"]},
        "partner": "allen",
        "relationship": {"warmth": 0.2, "respect": 0.2},
        "deliberation": {"action": "ANSWER", "focus": "electroreception"},
    }

    prompts: list[str] = []
    original = engine._private_model._request
    old_prompt = os.environ.get("ROOM_NODE_PROMPT")
    old_url = os.environ.get("ROOM_MODEL_URL")

    def fake_request(_url, prompt, _role, _temperature, _timeout, _self_entity=None, attempt=0):
        prompts.append(prompt)
        if attempt == 0:
            return expression(allen_words)
        return expression("Allen, their bills contain electroreceptors that help them locate prey underwater.")

    engine._private_model._request = fake_request
    os.environ["ROOM_NODE_PROMPT"] = "enabled-for-simulator"
    os.environ["ROOM_MODEL_URL"] = "http://simulator.invalid"
    try:
        result = engine._private_run("expression", payload, timeout=1)
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

    assert result.get("utterance")
    assert len(prompts) >= 2, "retry probe did not force a second expression attempt"
    first_prefix = prompts[0].split("\nCONVERSATION\n", 1)[0]
    second_prefix = prompts[1].split("\nCONVERSATION\n", 1)[0]
    assert first_prefix == second_prefix, "RED: rejection added model-visible retry prose"
    assert "use a different idea" not in prompts[1].lower(), "RED: retry instruction can be echoed into dialogue"
    assert allen_words in prompts[1], "Allen's newest words were lost during retry recovery"

    print("ROOM RETRY/TRUNCATION BOUNDARY SIM: GREEN")


if __name__ == "__main__":
    main()
