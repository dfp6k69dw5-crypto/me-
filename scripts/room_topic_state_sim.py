#!/usr/bin/env python3
from __future__ import annotations

import room_private_commit as commit
import room_social_v5 as social


def message(speaker: str, text: str, terms: list[str], episode_id: str) -> dict:
    return {
        "speaker": speaker,
        "text": text,
        "cognition": {
            "topic_episode": episode_id,
            "topic_terms": terms,
        },
    }


def pathological_topic(cycle: int = 500) -> dict:
    topic = social.topic_template(cycle)
    topic["root"] = "books"
    topic["current_facet"] = "depth-37"
    topic["facets"] = [f"depth-{i}" for i in range(1, 38)]
    topic["visited_facets"] = list(topic["facets"])
    topic["branches"] = [
        {"label": "books", "parent": None, "depth": 0, "first_cycle": cycle - 40, "last_cycle": cycle, "hits": 40, "status": "open"}
    ]
    parent = "books"
    for depth in range(1, 38):
        label = f"depth-{depth}"
        topic["branches"].append({
            "label": label,
            "parent": parent,
            "depth": depth,
            "first_cycle": cycle - (38 - depth),
            "last_cycle": cycle,
            "hits": 2,
            "status": "open",
        })
        parent = label
    topic["branch_history"] = [f"depth-{i}" for i in range(1, 38)]
    topic["status"] = "active"
    return topic


def main() -> None:
    topic = pathological_topic()
    episode = topic["id"]
    history = [
        message("sarah", "I keep thinking about the ending of this book.", ["books", "ending"], episode),
        message("mara", "The ending changes how I see the main character.", ["books", "ending", "character"], episode),
        message("owen", "The evidence in the final chapter matters more than the reputation of the novel.", ["books", "final chapter", "evidence"], episode),
    ]
    bounded = social.update_topic(topic, history, 501)
    depths = [int(branch.get("depth", 0)) for branch in bounded.get("branches", [])]
    assert max(depths or [0]) <= 1, f"runaway topic depth survived replacement: {max(depths)}"
    assert len(bounded.get("facets", [])) <= 8, bounded.get("facets")
    assert len(bounded.get("visited_facets", [])) <= 8, bounded.get("visited_facets")
    assert len(bounded.get("branch_history", [])) <= 8, bounded.get("branch_history")

    old_id = bounded["id"]
    outside_turn = message(
        "allen",
        "Let's talk about platypuses and why the males have venomous ankle spurs.",
        ["platypuses", "venomous ankle spurs"],
        old_id,
    )
    shifted = social.update_topic(bounded, [*history, outside_turn], 502)
    assert shifted.get("id") != old_id, "genuinely new outside-participant subject was swallowed by stale episode"
    assert shifted.get("root") == "platypuses", shifted
    assert max([int(branch.get("depth", 0)) for branch in shifted.get("branches", [])] or [0]) <= 1

    expr = {"semantic_terms": ["platypuses", "public-interest", "books"]}
    spoken = "Platypuses are mammals, and the males can carry venom in ankle spurs."
    terms = commit.clean_terms(expr, {"root": "books", "current_facet": "classics"}, spoken)
    assert "platypuses" in terms, terms
    assert "public-interest" not in terms, terms
    assert "books" not in terms, "stale topic term was re-declared despite not appearing in the spoken line"

    print("ROOM BOUNDED TOPIC SIM: GREEN")


if __name__ == "__main__":
    main()
