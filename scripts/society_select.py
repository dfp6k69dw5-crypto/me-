#!/usr/bin/env python3
import json, os, random, hashlib, re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
minds=json.loads((ROOT/"society/minds.json").read_text())
state=json.loads((ROOT/"society/state.json").read_text())
conversation=json.loads((ROOT/"society/conversation.json").read_text())
entities=minds["entities"]

# Maintenance pause only. Ordinary silence happens inside the selected entity's
# three independent nodes.
if (ROOT/"society/PAUSED").exists():
    chosen="rest"; resting=True
else:
    forced=(os.getenv("FORCED_ENTITY") or "auto").strip().lower()
    if forced and forced != "auto":
        if forced not in entities: raise SystemExit(f"Unknown forced entity: {forced}")
        chosen=forced; resting=False
    else:
        seed_text=f'{os.getenv("GITHUB_RUN_ID","local")}:{os.getenv("GITHUB_RUN_ATTEMPT","1")}:{state.get("attempts",0)}'
        seed=int(hashlib.sha256(seed_text.encode()).hexdigest()[:16],16)
        rng=random.Random(seed)
        ids=list(entities)
        recent=[m.get("speaker") for m in conversation[-10:] if m.get("speaker")]
        last_msg=conversation[-1] if conversation else {}
        last=last_msg.get("speaker") or state.get("last_speaker")
        last_text=str(last_msg.get("text","") or "")

        # Multiparty turn-taking: a current speaker may select a next speaker
        # (we approximate explicit selection by use of a peer's name); otherwise
        # non-speakers self-select and compete probabilistically for the floor.
        addressed=[]
        for eid,e in entities.items():
            if eid==last: continue
            if re.search(rf"\b{re.escape(e['name'])}\b",last_text,re.I): addressed.append(eid)

        weights=[]
        for eid in ids:
            g=entities[eid]["genome"]
            d=entities[eid].get("development",{})
            # Individual readiness contributes, but does not determine a persona.
            w=0.20+1.10*g["spontaneous_initiation"]+0.40*g["social_salience"]+0.18*g["exploration"]
            w*=0.72+0.56*float(d.get("recent_activation",0.5) or 0.5)

            # People who just spoke usually yield the floor, but can continue if
            # nobody else wins it.
            if eid==last: w*=0.20

            # Avoid mechanical round-robin and monopolies: recent speakers are
            # less likely to win another self-selection competition.
            w*=1/(1+0.42*recent.count(eid))

            # Recipient selection strongly boosts an explicitly addressed peer.
            if addressed:
                if eid in addressed: w*=4.5
                elif eid!=last: w*=0.45
            elif last_text.rstrip().endswith("?") and eid!=last:
                # An unaddressed question opens the floor to the other peers.
                w*=1.25

            weights.append(max(0.01,w))

        chosen=rng.choices(ids,weights=weights,k=1)[0]
        resting=False

out=os.getenv("GITHUB_OUTPUT")
if out:
    with open(out,"a",encoding="utf-8") as f:
        f.write(f"entity={chosen}\n")
        f.write(f"resting={'true' if resting else 'false'}\n")
print(chosen)
