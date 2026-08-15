#!/usr/bin/env python3
import json, os, random, hashlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
minds=json.loads((ROOT/"society/minds.json").read_text())
state=json.loads((ROOT/"society/state.json").read_text())
conversation=json.loads((ROOT/"society/conversation.json").read_text())
entities=minds["entities"]

# Repository-held pause flag is reserved for maintenance only. Ordinary silence
# comes from each selected entity's three independent nodes, not a room-wide skip.
if (ROOT/"society/PAUSED").exists():
    chosen="rest"
    resting=True
else:
    forced=(os.getenv("FORCED_ENTITY") or "auto").strip().lower()
    if forced and forced != "auto":
        if forced not in entities:
            raise SystemExit(f"Unknown forced entity: {forced}")
        chosen=forced
        resting=False
    else:
        seed_text=f'{os.getenv("GITHUB_RUN_ID","local")}:{os.getenv("GITHUB_RUN_ATTEMPT","1")}:{state.get("attempts",0)}'
        seed=int(hashlib.sha256(seed_text.encode()).hexdigest()[:16],16)
        rng=random.Random(seed)
        recent=[m.get("speaker") for m in conversation[-8:] if m.get("speaker")]
        last=state.get("last_speaker")
        ids=list(entities)
        weights=[]
        for eid in ids:
            g=entities[eid]["genome"]
            d=entities[eid].get("development",{})
            weight=0.18 + 1.35*g["spontaneous_initiation"] + 0.42*g["social_salience"] + 0.22*g["exploration"]
            if last==eid:
                weight*=0.30
            count=recent.count(eid)
            weight*=1/(1+0.35*count)
            weight*=0.75+0.5*float(d.get("recent_activation",0.5))
            weights.append(max(0.01,weight))
        chosen=rng.choices(ids,weights=weights,k=1)[0]
        resting=False

out=os.getenv("GITHUB_OUTPUT")
if out:
    with open(out,"a",encoding="utf-8") as f:
        f.write(f"entity={chosen}\n")
        f.write(f"resting={'true' if resting else 'false'}\n")
print(chosen)
