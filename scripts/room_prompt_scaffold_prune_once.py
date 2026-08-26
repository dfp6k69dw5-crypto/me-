#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from pathlib import Path

AUTONOMY = Path("scripts/room_private_model_autonomy.py")
CORE = Path("scripts/room_engine_v5_core.py")

a = AUTONOMY.read_text()
anchor = '''    hard_patterns = (\n        r"\\b(?:prompt|schema|field)\\s+(?:says|requires|expects|allows|forces|tells)\\b",\n        r"\\b(?:output|generation|response)\\s+(?:format|process|schema)\\b",\n        r"\\b(?:return|output|generate)\\s+(?:only\\s+)?(?:json|structured\\s+(?:data|object))\\b",\n    )\n'''
replacement = '''    hard_patterns = (\n        r"\\b(?:prompt|schema|field)\\s+(?:says|requires|expects|allows|forces|tells)\\b",\n        r"\\b(?:output|generation|response)\\s+(?:format|process|schema)\\b",\n        r"\\b(?:return|output|generate)\\s+(?:only\\s+)?(?:json|structured\\s+(?:data|object))\\b",\n        r"\\bkeep\\s+(?:the|your|its)\\s+(?:chosen\\s+)?move.{0,32}focus.{0,32}(?:intended\\s+)?partner\\b",\n        r"\\b(?:move|focus)\\s*(?:,|and)\\s*(?:focus|partner).{0,24}(?:partner|intact)\\b",\n        r"\\bdo\\s+not\\s+(?:resolve|invent|copy).{0,48}\\b(?:issue|conflict|speech|conversation)\\b",\n        r"\\buse\\s+only\\s+details\\s+supported\\s+by\\s+(?:what|the conversation)\\b",\n        r"\\bbase\\s+(?:the\\s+)?reply\\s+only\\s+on\\s+what\\s+was\\s+actually\\s+said\\b",\n    )\n'''
if replacement not in a:
    if anchor not in a:
        raise SystemExit("autonomy meta-language anchor not found")
    a = a.replace(anchor, replacement, 1)
AUTONOMY.write_text(a)

c = CORE.read_text()
anchor2 = '''def _memory_worthy_text(text, move=None):\n    """Speech may be public without automatically becoming durable memory."""\n    lexical = [w.strip("'-") for w in re.findall(r"[a-z][a-z'-]*", str(text or "").lower())]\n'''
replacement2 = '''def _memory_worthy_text(text, move=None):\n    """Speech may be public without automatically becoming durable memory."""\n    low = str(text or "").lower()\n    scaffold_patterns = (\n        r"\\bkeep\\s+(?:the|your|its)\\s+(?:chosen\\s+)?move.{0,32}focus.{0,32}(?:intended\\s+)?partner\\b",\n        r"\\b(?:move|focus)\\s*(?:,|and)\\s*(?:focus|partner).{0,24}(?:partner|intact)\\b",\n        r"\\buse\\s+only\\s+details\\s+supported\\s+by\\s+(?:what|the conversation)\\b",\n        r"\\bbase\\s+(?:the\\s+)?reply\\s+only\\s+on\\s+what\\s+was\\s+actually\\s+said\\b",\n    )\n    if any(re.search(pattern, low) for pattern in scaffold_patterns):\n        return False\n    lexical = [w.strip("'-") for w in re.findall(r"[a-z][a-z'-]*", low)]\n'''
if replacement2 not in c:
    if anchor2 not in c:
        raise SystemExit("memory-worthy scaffold anchor not found")
    c = c.replace(anchor2, replacement2, 1)
CORE.write_text(c)

subprocess.run(["python3", "-m", "py_compile", str(AUTONOMY), str(CORE)], check=True)
subprocess.run(["git", "config", "user.name", "the-room-repair"], check=True)
subprocess.run(["git", "config", "user.email", "actions@users.noreply.github.com"], check=True)
subprocess.run(["git", "add", str(AUTONOMY), str(CORE)], check=True)
if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode != 0:
    subprocess.run(["git", "commit", "-m", "Block Room prompt scaffolding from speech and memory"], check=True)
    for _ in range(3):
        pushed = subprocess.run(["git", "push", "origin", "HEAD:main"])
        if pushed.returncode == 0:
            break
        subprocess.run(["git", "fetch", "origin", "main"], check=True)
        subprocess.run(["git", "rebase", "origin/main"], check=True)
    else:
        raise SystemExit("could not push prompt scaffold guard")
