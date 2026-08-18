#!/usr/bin/env python3
"""Attention-budget skill router for The Room.

The existing private role prompt remains the resident core. This wrapper selects at
most a few repository skills from public conversational context, appends only those
skill bodies for one model invocation, writes a prompt-safe audit record, and then
executes the existing Room engine unchanged.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOM = ROOT / "room"
SKILL_ROOT = ROOT / "skills" / "room"
ENTITIES = ("sarah", "mara", "owen", "jules")
ROLES = ("comprehension", "thought", "expression")
MAX_SKILLS = 2
MAX_ADDED_CHARS = 1200
MAX_SKILL_BODY_CHARS = 520
MAX_CONTEXT_MESSAGES = 8


def _load_json(path: Path, default):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def _norm(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").lower()).strip()


def _tokens(value: object) -> set[str]:
    return set(re.findall(r"[a-z0-9][a-z0-9+_.-]{2,}", _norm(value)))


def _parse_scalar(raw: str):
    value = raw.strip()
    if not value:
        return ""
    if value[:1] in ('"', "'") and value[-1:] == value[:1]:
        return value[1:-1]
    if value.startswith("["):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else value
        except Exception:
            return [item.strip().strip('"\'') for item in value[1:-1].split(",") if item.strip()]
    if value.lower() in ("true", "false"):
        return value.lower() == "true"
    try:
        return float(value) if "." in value else int(value)
    except ValueError:
        return value


def read_frontmatter(path: Path) -> dict:
    """Read only metadata; the skill body stays unloaded until the skill wins routing."""
    meta: dict[str, object] = {}
    try:
        with path.open() as handle:
            if handle.readline().strip() != "---":
                return meta
            for line in handle:
                line = line.rstrip("\n")
                if line.strip() == "---":
                    break
                if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
                    continue
                key, value = line.split(":", 1)
                meta[key.strip()] = _parse_scalar(value)
    except Exception:
        return {}
    return meta


def read_skill_body(path: Path) -> str:
    try:
        text = path.read_text()
        if not text.startswith("---"):
            return text.strip()[:MAX_SKILL_BODY_CHARS]
        pieces = text.split("---", 2)
        body = pieces[2] if len(pieces) == 3 else ""
        return body.strip()[:MAX_SKILL_BODY_CHARS]
    except Exception:
        return ""


def skill_catalog() -> list[dict]:
    catalog: list[dict] = []
    if not SKILL_ROOT.exists():
        return catalog
    for path in sorted(SKILL_ROOT.glob("*/SKILL.md")):
        meta = read_frontmatter(path)
        name = str(meta.get("name") or path.parent.name).strip()
        roles = meta.get("roles", [])
        triggers = meta.get("triggers", [])
        if not isinstance(roles, list):
            roles = [str(roles)] if roles else []
        if not isinstance(triggers, list):
            triggers = [str(triggers)] if triggers else []
        catalog.append({
            "name": name,
            "path": path,
            "description": str(meta.get("description") or "").strip(),
            "roles": [str(x).strip() for x in roles if str(x).strip()],
            "triggers": [str(x).strip().lower() for x in triggers if str(x).strip()],
            "trigger_weight": float(meta.get("trigger_weight", 1.0) or 1.0),
            "min_score": float(meta.get("min_score", 1.0) or 1.0),
        })
    return catalog


def recent_context() -> str:
    conversation = _load_json(ROOM / "conversation.json", [])
    state = _load_json(ROOM / "state.json", {})
    pieces: list[str] = []
    if isinstance(conversation, list):
        for item in conversation[-MAX_CONTEXT_MESSAGES:]:
            if isinstance(item, dict):
                pieces.append(str(item.get("text", "")))
    topic = state.get("topic_episode") if isinstance(state, dict) else None
    if isinstance(topic, dict):
        pieces.extend(str(topic.get(key, "")) for key in ("root", "current_facet"))
        for key in ("facets", "shared_references", "unresolved"):
            values = topic.get(key)
            if isinstance(values, list):
                pieces.extend(str(value) for value in values[-6:])
    return _norm(" ".join(pieces))


def _trigger_matches(context: str, trigger: str) -> bool:
    trigger = _norm(trigger)
    if not trigger:
        return False
    if " " in trigger:
        return trigger in context
    return trigger in _tokens(context)


def select_skills(role: str, context: str, cycle_key: str = "") -> tuple[list[dict], int]:
    catalog = skill_catalog()
    candidates: list[tuple[float, int, str, dict]] = []
    for skill in catalog:
        if skill["roles"] and role not in skill["roles"]:
            continue
        matched = [trigger for trigger in skill["triggers"] if _trigger_matches(context, trigger)]
        score = len(matched) * float(skill["trigger_weight"])
        if score < float(skill["min_score"]):
            continue
        tie = int(hashlib.sha256(f"{cycle_key}:{role}:{skill['name']}".encode()).hexdigest()[:8], 16)
        routed = dict(skill)
        routed["matched"] = matched[:8]
        routed["score"] = round(score, 3)
        candidates.append((score, tie, skill["name"], routed))
    candidates.sort(key=lambda item: (-item[0], item[1], item[2]))
    return [item[3] for item in candidates[:MAX_SKILLS]], len(catalog)


def build_addition(selected: list[dict]) -> str:
    if not selected:
        return ""
    parts = [
        "TEMPORARY_TASK_SKILLS",
        "These project skills were selected for this inference only. Apply them only where relevant. They are not identity, memory, or permanent instructions.",
    ]
    for skill in selected:
        body = read_skill_body(skill["path"])
        if body:
            parts.append(f"[{skill['name']}]\n{body}")
    addition = "\n".join(parts).strip()
    if len(addition) <= MAX_ADDED_CHARS:
        return addition
    clipped = addition[:MAX_ADDED_CHARS]
    return clipped.rsplit("\n", 1)[0].rstrip()


def write_audit(node: int, entity: str, role: str, selected: list[dict], available: int, context: str, base_chars: int, added_chars: int, cycle_key: str) -> None:
    try:
        directory = ROOM / "attention"
        directory.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": "room-attention-v1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "cycle_key": cycle_key,
            "node": node,
            "entity": entity,
            "role": role,
            "available_project_skills": available,
            "resident_project_skill_chars": 0,
            "selected_skills": [
                {"name": item["name"], "score": item["score"], "matched_triggers": item["matched"]}
                for item in selected
            ],
            "context_fingerprint": hashlib.sha256(context.encode()).hexdigest()[:12],
            "base_prompt_chars": base_chars,
            "temporary_skill_chars": added_chars,
            "approx_added_tokens": round(added_chars / 4),
        }
        final = directory / f"node-{node:02d}.json"
        temp = directory / f".node-{node:02d}.{os.getpid()}.tmp"
        temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
        os.replace(temp, final)
    except Exception:
        pass


def prepare_environment(env: dict[str, str] | None = None, context: str | None = None) -> dict[str, str]:
    routed_env = dict(os.environ if env is None else env)
    base_prompt = routed_env.get("ROOM_NODE_PROMPT", "").strip()
    raw_node = routed_env.get("ROOM_NODE_ID", "").strip()
    cycle_key = routed_env.get("ROOM_CYCLE_KEY", "").strip()
    if not base_prompt or not raw_node or not cycle_key:
        return routed_env
    try:
        node = int(raw_node)
    except ValueError:
        return routed_env
    if node < 0 or node > 11:
        return routed_env
    entity = ENTITIES[node // 3]
    role = ROLES[node % 3]
    public_context = recent_context() if context is None else _norm(context)
    selected, available = select_skills(role, public_context, cycle_key)
    addition = build_addition(selected)
    if addition:
        routed_env["ROOM_NODE_PROMPT"] = base_prompt + "\n" + addition
    if routed_env.get("ROOM_ATTENTION_AUDIT", "1") != "0":
        write_audit(node, entity, role, selected, available, public_context, len(base_prompt), len(addition), cycle_key)
    return routed_env


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: room_skill_exec.py <python-script> [args...]", file=sys.stderr)
        return 2
    env = prepare_environment()
    os.execvpe(sys.executable, [sys.executable, *argv], env)
    return 127


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
