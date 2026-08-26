#!/usr/bin/env python3
from __future__ import annotations

# One-shot trigger: prune historical bare internal move labels from durable memory.
import subprocess
from pathlib import Path

PATH = Path("scripts/room_engine_v5_core.py")
text = PATH.read_text()

anchor = '_MEMORY_SALIENT_MOVES = {"disclose", "repair", "callback", "disagree", "answer", "support"}\n'
replacement = '''_MEMORY_SALIENT_MOVES = {"disclose", "repair", "callback", "disagree", "answer", "support"}\n_MEMORY_INTERNAL_MOVE_LABELS = {\n    "acknowledge", "appreciate", "support", "repair", "answer",\n    "respond", "response", "disclose", "compare", "disagree",\n    "agree", "bridge", "close", "deepen", "callback",\n}\n'''
if replacement not in text:
    if anchor not in text:
        raise SystemExit("memory label set anchor not found")
    text = text.replace(anchor, replacement, 1)

anchor2 = '''    if not lexical:\n        return False\n    content = _memory_content_tokens(text)\n'''
replacement2 = '''    if not lexical:\n        return False\n    if len(lexical) == 1 and lexical[0] in _MEMORY_INTERNAL_MOVE_LABELS:\n        return False\n    content = _memory_content_tokens(text)\n'''
if replacement2 not in text:
    if anchor2 not in text:
        raise SystemExit("memory-worthy anchor not found")
    text = text.replace(anchor2, replacement2, 1)

PATH.write_text(text)
subprocess.run(["python3", "-m", "py_compile", str(PATH)], check=True)
subprocess.run(["git", "config", "user.name", "the-room-repair"], check=True)
subprocess.run(["git", "config", "user.email", "actions@users.noreply.github.com"], check=True)
subprocess.run(["git", "add", str(PATH)], check=True)
if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode != 0:
    subprocess.run(["git", "commit", "-m", "Prune internal move labels from Room memory"], check=True)
    for _ in range(3):
        pushed = subprocess.run(["git", "push", "origin", "HEAD:main"])
        if pushed.returncode == 0:
            break
        subprocess.run(["git", "fetch", "origin", "main"], check=True)
        subprocess.run(["git", "rebase", "origin/main"], check=True)
    else:
        raise SystemExit("could not push memory-label prune")
