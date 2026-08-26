#!/usr/bin/env python3
from pathlib import Path
import subprocess

p = Path('scripts/room_engine_v5_core.py')
s = p.read_text()

old_threshold = '            and _sim(text, prior.get("text", "")) >= 0.82\n'
new_threshold = '            and _sim(text, prior.get("text", "")) >= 0.78\n'
if new_threshold not in s:
    if old_threshold not in s:
        raise SystemExit('memory dedupe threshold anchor not found')
    s = s.replace(old_threshold, new_threshold, 1)

anchor = '\n\ndef record(history, discourse, mind, message, node, cycle):\n'
helper = '''\n\ndef _memory_excerpt(text, limit=300):\n    """Bound durable memory without cutting a thought mid-word or mid-sentence."""\n    value = re.sub(r"\\s+", " ", str(text or "")).strip()\n    if len(value) <= limit:\n        return value\n    head = value[: limit + 1]\n    sentence_ends = [head.rfind(mark) for mark in (". ", "? ", "! ")]\n    cut = max(sentence_ends)\n    if cut >= max(80, int(limit * 0.45)):\n        return head[: cut + 1].strip()\n    cut = head.rfind(" ", 0, limit + 1)\n    if cut >= max(80, int(limit * 0.70)):\n        return head[:cut].rstrip(" ,;:-") + "…"\n    return value[:limit].rstrip(" ,;:-") + "…"\n\n\ndef record(history, discourse, mind, message, node, cycle):\n'''
if '_memory_excerpt(text, limit=300)' not in s:
    if anchor not in s:
        raise SystemExit('record anchor not found')
    s = s.replace(anchor, helper, 1)

old_store = '                "text": message["text"][:300],\n'
new_store = '                "text": _memory_excerpt(message["text"], 300),\n'
if new_store not in s:
    if old_store not in s:
        raise SystemExit('memory storage anchor not found')
    s = s.replace(old_store, new_store, 1)

p.write_text(s)
subprocess.run(['python3','-m','py_compile',str(p)], check=True)
subprocess.run(['git','config','user.name','the-room-repair'], check=True)
subprocess.run(['git','config','user.email','actions@users.noreply.github.com'], check=True)
subprocess.run(['git','add',str(p)], check=True)
if subprocess.run(['git','diff','--cached','--quiet']).returncode != 0:
    subprocess.run(['git','commit','-m','Preserve complete Room memory excerpts'], check=True)
    for _ in range(4):
        if subprocess.run(['git','push','origin','HEAD:main']).returncode == 0:
            break
        subprocess.run(['git','fetch','origin','main'], check=True)
        subprocess.run(['git','rebase','origin/main'], check=True)
    else:
        raise SystemExit('could not push memory excerpt repair')
