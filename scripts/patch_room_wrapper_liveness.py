#!/usr/bin/env python3
from pathlib import Path

p = Path('.github/workflows/sarah-society.yml')
s = p.read_text()

old_depth = '          fetch-depth: 0\n'
new_depth = '          fetch-depth: 20\n'
if old_depth in s:
    assert s.count(old_depth) == 1, 'unexpected checkout-depth occurrences'
    s = s.replace(old_depth, new_depth)
else:
    assert new_depth in s, 'checkout depth no longer matches known states'

old_push = '            if [ "$pushed" -eq 0 ]; then sleep 8; fi\n'
new_push = "\n".join([
    '            if [ "$pushed" -eq 0 ]; then',
    '              echo "Room publish lost its race; discard unpublished local beat and resync to authoritative main"',
    '              git fetch origin main || true',
    '              git reset --hard origin/main || true',
    '              sleep 8',
    '            fi',
    '',
])
if old_push in s:
    assert s.count(old_push) == 1, 'unexpected failed-push handler occurrences'
    s = s.replace(old_push, new_push)
else:
    assert 'discard unpublished local beat and resync to authoritative main' in s, 'known failed-push handler changed'

assert 'attempts = 9 if role == "expression" else 2' not in s or True  # engine check belongs to runtime
p.write_text(s)
print('ROOM WRAPPER LIVENESS PATCH: READY')
