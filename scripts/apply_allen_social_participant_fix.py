#!/usr/bin/env python3
from pathlib import Path

path = Path(__file__).with_name("room_social_v5.py")
text = path.read_text()

marker = 'PARTICIPANTS=ORDER+("allen",)'
if marker in text:
    print("Allen social participant boundary already applied")
    raise SystemExit(0)

replacements = [
    (
        'ORDER=("sarah","mara","owen","jules")\nREL_KEYS=',
        'ORDER=("sarah","mara","owen","jules")\nPARTICIPANTS=ORDER+("allen",)\nREL_KEYS=',
    ),
    (
        " for e in ORDER:\n  people=ents.setdefault(e,{}).setdefault('people',{})\n  for o in ORDER:\n",
        " for e in ORDER:\n  people=ents.setdefault(e,{}).setdefault('people',{})\n  for o in PARTICIPANTS:\n",
    ),
    (
        "'disagreements':[],'shared_references':[],'participants':list(ORDER),'turns':0,",
        "'disagreements':[],'shared_references':[],'participants':list(PARTICIPANTS),'turns':0,",
    ),
    (
        " for k,v in defaults.items(): t.setdefault(k,v)\n if int(t.get('semantic_schema',1))<4:",
        " for k,v in defaults.items(): t.setdefault(k,v)\n t['participants']=list(PARTICIPANTS)\n if int(t.get('semantic_schema',1))<4:",
    ),
    (
        " if tgt in ORDER: return tgt",
        " if tgt in PARTICIPANTS: return tgt",
    ),
    (
        "by[p].get('speaker') in ORDER: return by[p]['speaker']",
        "by[p].get('speaker') in PARTICIPANTS: return by[p]['speaker']",
    ),
    (
        " if sp not in ORDER or sp==listener: return None",
        " if sp not in PARTICIPANTS or sp==listener: return None",
    ),
    (
        "partner=qtarget if qtarget in ORDER and qtarget!=e else choose_partner(e,M,t,cycle)",
        "partner=qtarget if qtarget in PARTICIPANTS and qtarget!=e else choose_partner(e,M,t,cycle)",
    ),
    (
        "def audit_invariants(M,t):\n migrate_minds(M)\n for e in ORDER:\n  for o in ORDER:\n",
        "def audit_invariants(M,t):\n migrate_minds(M)\n for e in ORDER:\n  for o in PARTICIPANTS:\n",
    ),
]

for old, new in replacements:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"refusing patch: expected exactly one match, got {count}: {old[:80]!r}")
    text = text.replace(old, new, 1)

path.write_text(text)
print("Applied Allen conversational-participant boundary to room_social_v5.py")
