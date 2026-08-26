#!/usr/bin/env python3
from pathlib import Path

# Trigger revision 2: workflow now exists on main.
p = Path('scripts/room_engine_v5.py')
s = p.read_text()

if '_TOPIC_STATE_TERMS = {' not in s:
    marker = '_TOPIC_SOCIAL_MOVE_TERMS = {'
    start = s.index(marker)
    end = s.index('\n}\n', start) + len('\n}\n')
    block = '''_TOPIC_STATE_TERMS = {\n    # Generic affect / interpersonal stance. These shape how a turn is said,\n    # but are too weak to define what the conversation is about.\n    "glad", "happy", "sad", "sorry", "sure", "unsure", "worried", "worry", "worrying",\n    "grateful", "thankful", "overwhelmed", "upset", "angry", "afraid", "scared", "nervous",\n    "confused", "comfortable", "uncomfortable", "honest", "open", "okay", "fine",\n    # Generic wanting/needing language should yield to the concrete object of\n    # that state (for example autonomy, art, a movie, a plan).\n    "need", "needs", "needed", "needing", "want", "wants", "wanted", "wanting",\n}\n'''
    s = s[:end] + block + s[end:]

old = 'if len(word) < 4 or word in _CUE_STOPWORDS or word in _TOPIC_SOCIAL_MOVE_TERMS or word in cues:'
new = 'if len(word) < 4 or word in _CUE_STOPWORDS or word in _TOPIC_SOCIAL_MOVE_TERMS or word in _TOPIC_STATE_TERMS or word in cues:'
if old in s:
    s = s.replace(old, new, 1)
elif new not in s:
    raise SystemExit('semantic cue state-filter anchor missing')

old2 = '''                or candidate in _TOPIC_FILLER\n                or candidate in _TOPIC_SOCIAL_MOVE_TERMS\n            ):'''
new2 = '''                or candidate in _TOPIC_FILLER\n                or candidate in _TOPIC_SOCIAL_MOVE_TERMS\n                or candidate in _TOPIC_STATE_TERMS\n            ):'''
if old2 in s:
    s = s.replace(old2, new2, 1)
elif new2 not in s:
    raise SystemExit('declared topic state-filter anchor missing')

p.write_text(s)
