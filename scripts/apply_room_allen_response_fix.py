#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"expected patch anchor missing in {path}")
    path.write_text(text.replace(old, new, 1))


def replace_exact_count(path: Path, old: str, new: str, expected: int) -> None:
    text = path.read_text()
    if new in text and old not in text:
        return
    count = text.count(old)
    if count != expected:
        raise SystemExit(f"expected {expected} occurrences in {path}, found {count}")
    path.write_text(text.replace(old, new))


def main() -> None:
    engine = SCRIPTS / "room_engine_v5.py"
    private_model = SCRIPTS / "room_private_model.py"
    private_commit = SCRIPTS / "room_private_commit.py"

    replace_once(
        engine,
        'N = {entity: P[entity]["name"] for entity in ORDER}\nSTOP = set(',
        'N = {entity: P[entity]["name"] for entity in ORDER}\n'
        'PARTICIPANTS = tuple(ORDER) + ("allen",)\n'
        'PARTICIPANT_RELATIONSHIP_DEFAULTS = {\n'
        '    "exposure": 0.18,\n'
        '    "direct_familiarity": 0.10,\n'
        '    "trust": 0.10,\n'
        '    "predictability": 0.10,\n'
        '    "reciprocity": 0.10,\n'
        '    "warmth": 0.10,\n'
        '    "respect": 0.12,\n'
        '    "disclosure_depth": 0.0,\n'
        '    "tension": 0.0,\n'
        '}\n\n'
        'def relationship_for(mind, entity, partner):\n'
        '    rel = ((mind.get("entities") or {}).get(entity, {}).get("people") or {}).get(partner)\n'
        '    if isinstance(rel, dict):\n'
        '        return rel\n'
        '    return dict(PARTICIPANT_RELATIONSHIP_DEFAULTS)\n\n\n'
        'STOP = set('
    )
    replace_once(
        engine,
        '    if partner not in ORDER or partner == entity:\n        partner = choose_partner(entity, mind, topic, int(current_state.get("cycle", 0)))\n    rel = mind["entities"][entity]["people"][partner]\n',
        '    if partner not in PARTICIPANTS or partner == entity:\n        partner = choose_partner(entity, mind, topic, int(current_state.get("cycle", 0)))\n    rel = relationship_for(mind, entity, partner)\n'
    )

    replace_once(
        private_model,
        'PEOPLE = ["sarah", "mara", "owen", "jules"]',
        'PEOPLE = ["sarah", "mara", "owen", "jules", "allen"]'
    )

    replace_exact_count(
        private_commit,
        'if target not in c.ORDER or target == entity:',
        'if target not in c.PARTICIPANTS or target == entity:',
        2,
    )

    print("Applied Allen response-relevance patch")


if __name__ == "__main__":
    main()
