#!/usr/bin/env python3
from pathlib import Path

p = Path('scripts/room_engine_v5.py')
s = p.read_text()

move_set = '''_TOPIC_SOCIAL_MOVE_TERMS = {\n    "support", "supporting", "supported",\n    "repair", "repairing", "repaired",\n    "disagree", "disagreeing", "disagreement",\n    "agree", "agreeing", "agreement",\n    "answer", "answering", "answered",\n    "callback", "compare", "comparing", "compared",\n    "disclose", "disclosing", "disclosed",\n    "bridge", "bridging", "close", "closing", "closed",\n    "ask", "asking", "asked", "question", "questioning",\n    "respond", "responding", "response",\n    "apologize", "apologizing", "apology", "reassure", "reassuring",\n}\n'''
if '_TOPIC_SOCIAL_MOVE_TERMS = {' not in s:
    start = s.index('_TOPIC_FILLER = {')
    end = s.index('\n}\n', start) + 3
    s = s[:end] + move_set + s[end:]

old_cue = 'if len(word) < 4 or word in _CUE_STOPWORDS or word in cues:'
new_cue = 'if len(word) < 4 or word in _CUE_STOPWORDS or word in _TOPIC_SOCIAL_MOVE_TERMS or word in cues:'
if old_cue in s:
    s = s.replace(old_cue, new_cue, 1)
elif new_cue not in s:
    raise SystemExit('semantic cue filter anchor missing')

old_filter = '''                or candidate in _TOPIC_SCAFFOLD\n                or candidate in _TOPIC_FILLER\n            ):'''
new_filter = '''                or candidate in _TOPIC_SCAFFOLD\n                or candidate in _TOPIC_FILLER\n                or candidate in _TOPIC_SOCIAL_MOVE_TERMS\n            ):'''
if old_filter in s:
    s = s.replace(old_filter, new_filter, 1)
elif new_filter not in s:
    raise SystemExit('topic term filter anchor missing')

p.write_text(s)
