#!/usr/bin/env python3
# trigger: 2026-08-27T01:28Z
from pathlib import Path
import subprocess

p = Path('scripts/room_engine_v5_core.py')
s = p.read_text()

old_labels = '''_MEMORY_INTERNAL_MOVE_LABELS = {
    "acknowledge", "appreciate", "support", "repair", "answer",
    "respond", "response", "disclose", "compare", "disagree",
    "agree", "bridge", "close", "deepen", "callback",
}
'''
new_labels = '''_MEMORY_INTERNAL_MOVE_LABELS = {
    "acknowledge", "appreciate", "support", "repair", "answer",
    "respond", "response", "disclose", "compare", "disagree",
    "agree", "bridge", "close", "deepen", "callback", "focus",
}
'''
if new_labels not in s:
    if old_labels not in s:
        raise SystemExit('memory label anchor not found')
    s = s.replace(old_labels, new_labels, 1)

old_self = '''        entity_state.setdefault("self_history", []).append({
            "source": message["id"],
            "text": message["text"],
            "move": message["cognition"]["move_type"],
            "discourse": message["discourse_id"],
            "beat_id": message["beat_id"],
            "topic_episode": message["cognition"].get("topic_episode"),
            "topic_facet": message["cognition"].get("topic_facet"),
        })
        entity_state["self_history"] = entity_state["self_history"][-220:]
'''
new_self = '''        entity_state.setdefault("self_history", []).append({
            "source": message["id"],
            "text": _memory_excerpt(message["text"], 300),
            "move": message["cognition"]["move_type"],
            "discourse": message["discourse_id"],
            "beat_id": message["beat_id"],
            "topic_episode": message["cognition"].get("topic_episode"),
            "topic_facet": message["cognition"].get("topic_facet"),
        })
        entity_state["self_history"] = _dedupe_memories(entity_state["self_history"], 220)
'''
if new_self not in s:
    if old_self not in s:
        raise SystemExit('self-history anchor not found')
    s = s.replace(old_self, new_self, 1)

p.write_text(s)
subprocess.run(['python3','-m','py_compile',str(p)], check=True)
subprocess.run(['git','config','user.name','the-room-repair'], check=True)
subprocess.run(['git','config','user.email','actions@users.noreply.github.com'], check=True)
subprocess.run(['git','add',str(p)], check=True)
if subprocess.run(['git','diff','--cached','--quiet']).returncode != 0:
    subprocess.run(['git','commit','-m','Close Room memory dedupe bypass'], check=True)
    for _ in range(4):
        if subprocess.run(['git','push','origin','HEAD:main']).returncode == 0:
            break
        subprocess.run(['git','fetch','origin','main'], check=True)
        subprocess.run(['git','rebase','origin/main'], check=True)
    else:
        raise SystemExit('could not push Room memory hygiene repair')
