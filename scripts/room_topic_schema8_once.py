#!/usr/bin/env python3
from pathlib import Path
import subprocess

p = Path('scripts/room_topic_bounded.py')
s = p.read_text()

s = s.replace('SCHEMA = 7\n', 'SCHEMA = 8\n', 1)
s = s.replace('MIN_FACET_SUPPORT = 2\n', 'MIN_FACET_SUPPORT = 2\nMIN_ROOT_SUPPORT = 2\n', 1)

noise_anchor = '    "tough", "hard", "difficult", "easy", "rough",\n'
noise_new = noise_anchor + '    "get", "gets", "got", "getting", "leave", "leaves", "left", "leaving",\n    "convince", "convinces", "convinced", "convincing",\n'
if noise_new not in s:
    if noise_anchor not in s:
        raise SystemExit('topic noise anchor not found')
    s = s.replace(noise_anchor, noise_new, 1)

old = '    if schema < SCHEMA or had_runaway_depth:\n        schema_upgrade = schema < SCHEMA\n        candidates = [] if schema_upgrade else [\n'
new = '    if schema < SCHEMA or had_runaway_depth:\n        schema_upgrade = schema < SCHEMA\n        if schema_upgrade:\n            # Schema 8 re-forms the subject under the same independent-support\n            # rule used for facets instead of preserving a one-message root.\n            root = None\n        candidates = [] if schema_upgrade else [\n'
if new not in s:
    if old not in s:
        raise SystemExit('schema migration anchor not found')
    s = s.replace(old, new, 1)

old2 = '    min_support = 1 if current.get("root") is None else MIN_FACET_SUPPORT\n'
new2 = '    min_support = MIN_ROOT_SUPPORT if current.get("root") is None else MIN_FACET_SUPPORT\n'
if new2 not in s:
    if old2 not in s:
        raise SystemExit('root support anchor not found')
    s = s.replace(old2, new2, 1)

p.write_text(s)
subprocess.run(['python3','-m','py_compile',str(p)], check=True)
subprocess.run(['git','config','user.name','the-room-repair'], check=True)
subprocess.run(['git','config','user.email','actions@users.noreply.github.com'], check=True)
subprocess.run(['git','add',str(p)], check=True)
if subprocess.run(['git','diff','--cached','--quiet']).returncode != 0:
    subprocess.run(['git','commit','-m','Require supported Room topic roots'], check=True)
    for _ in range(4):
        if subprocess.run(['git','push','origin','HEAD:main']).returncode == 0:
            break
        subprocess.run(['git','fetch','origin','main'], check=True)
        subprocess.run(['git','rebase','origin/main'], check=True)
    else:
        raise SystemExit('could not push topic schema 8 repair')
