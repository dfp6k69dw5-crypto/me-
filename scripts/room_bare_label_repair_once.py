#!/usr/bin/env python3
from __future__ import annotations

# One-shot trigger: retry bare internal move labels without policing weird speech.
import subprocess
from pathlib import Path

PATH = Path("scripts/room_private_model_autonomy.py")
text = PATH.read_text()

anchor = '''                utterance = str(obj.get("utterance") or "").strip()\n                if len(utterance.split()) < max(1, int(min_words)):\n'''
replacement = '''                utterance = str(obj.get("utterance") or "").strip()\n                # Preserve strange/short speech, but do not mistake an internal\n                # discourse move label for a public utterance. Retry only while\n                # another attempt remains so this quality guard can never freeze\n                # the Room by itself.\n                bare_words = _words(utterance)\n                bare_move_labels = {\n                    "acknowledge", "appreciate", "support", "repair", "answer",\n                    "respond", "response", "disclose", "compare", "disagree",\n                    "agree", "bridge", "close", "deepen", "callback",\n                }\n                if (\n                    attempt < attempts - 1\n                    and len(bare_words) == 1\n                    and bare_words[0] in bare_move_labels\n                ):\n                    last_reason = "bare_move_label"\n                    continue\n                if len(utterance.split()) < max(1, int(min_words)):\n'''

if replacement not in text:
    if anchor not in text:
        raise SystemExit("bare-label anchor not found")
    text = text.replace(anchor, replacement, 1)
    PATH.write_text(text)

subprocess.run(["python3", "-m", "py_compile", str(PATH)], check=True)
subprocess.run(["git", "config", "user.name", "the-room-repair"], check=True)
subprocess.run(["git", "config", "user.email", "actions@users.noreply.github.com"], check=True)
subprocess.run(["git", "add", str(PATH)], check=True)
if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode != 0:
    subprocess.run(["git", "commit", "-m", "Retry bare Room move labels before publishing"], check=True)
    for _ in range(3):
        pushed = subprocess.run(["git", "push", "origin", "HEAD:main"])
        if pushed.returncode == 0:
            break
        subprocess.run(["git", "fetch", "origin", "main"], check=True)
        subprocess.run(["git", "rebase", "origin/main"], check=True)
    else:
        raise SystemExit("could not push bare-label repair")
