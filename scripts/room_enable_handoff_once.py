#!/usr/bin/env python3
# One-shot trigger: allow fresh Room runs to replace stale warm code.
from pathlib import Path
import subprocess

p = Path('.github/workflows/sarah-society.yml')
text = p.read_text()
old = 'concurrency:\n  group: the-room-world-main\n  cancel-in-progress: false\n'
new = 'concurrency:\n  group: the-room-world-main\n  cancel-in-progress: true\n'
if new not in text:
    if old not in text:
        raise SystemExit('Room concurrency anchor not found')
    text = text.replace(old, new, 1)
p.write_text(text)
subprocess.run(['git','config','user.name','the-room-repair'], check=True)
subprocess.run(['git','config','user.email','actions@users.noreply.github.com'], check=True)
subprocess.run(['git','add',str(p)], check=True)
if subprocess.run(['git','diff','--cached','--quiet']).returncode != 0:
    subprocess.run(['git','commit','-m','Allow fresh Room runs to replace stale code'], check=True)
    for _ in range(3):
        if subprocess.run(['git','push','origin','HEAD:main']).returncode == 0:
            break
        subprocess.run(['git','fetch','origin','main'], check=True)
        subprocess.run(['git','rebase','origin/main'], check=True)
    else:
        raise SystemExit('could not push Room handoff fix')
