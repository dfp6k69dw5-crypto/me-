#!/usr/bin/env python3
import json, os, re
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
entity_id=os.environ["ENTITY_ID"].strip().lower()
minds_path=ROOT/"society/minds.json"
state_path=ROOT/"society/state.json"
conv_path=ROOT/"society/conversation.json"

minds=json.loads(minds_path.read_text())
state=json.loads(state_path.read_text())
conversation=json.loads(conv_path.read_text())
entity=minds["entities"][entity_id]
name=entity["name"]
g=entity["genome"]
d=entity.setdefault("development",{})
memory=entity.setdefault("memory",[])

parts=[]
for p in sorted((ROOT/"society_parts").rglob(f"{entity_id}-node-*.json")):
    try:
        obj=json.loads(p.read_text())
        if obj.get("entity")==entity_id and "error" not in obj:
            parts.append(obj)
    except Exception:
        pass

now=datetime.now(timezone.utc)
stamp=now.isoformat().replace("+00:00","Z")
state["attempts"]=int(state.get("attempts",0))+1
state["last_run"]=stamp
d["turns"]=int(d.get("turns",0))+1

def words(text):
    return set(re.findall(r"[a-z0-9']+",(text or "").lower()))

def jaccard(a,b):
    a,b=words(a),words(b)
    if not a and not b: return 1.0
    if not a or not b: return 0.0
    return len(a&b)/len(a|b)

speakers=[p for p in parts if p.get("speak") and str(p.get("text","")).strip()]
votes=len(speakers)
chosen=None
if votes>=2:
    scored=[]
    for p in speakers:
        sims=[jaccard(p["text"],q["text"]) for q in speakers if q is not p]
        agreement=sum(sims)/len(sims) if sims else 0.0
        score=0.62*agreement+0.38*float(p.get("salience",0.5))
        scored.append((score,p))
    chosen=max(scored,key=lambda x:x[0])[1]

# Learned associations are updated from all successful internal nodes,
# even when the entity ultimately remains quiet.
topic_weights=d.setdefault("topic_weights",{})
for p in parts:
    sal=float(p.get("salience",0.5))
    for topic in p.get("topics") or []:
        topic=re.sub(r"[^a-z0-9 _'-]","",str(topic).lower()).strip()[:40]
        if not topic: continue
        inc=(0.08+0.30*g["plasticity"])*(0.45+sal)*(0.55+0.45*g["reinforcement_sensitivity"])
        topic_weights[topic]=round(float(topic_weights.get(topic,0))*0.985+inc,4)
if len(topic_weights)>40:
    keep=dict(sorted(topic_weights.items(),key=lambda kv:kv[1],reverse=True)[:40])
    d["topic_weights"]=topic_weights=keep

if chosen:
    text=str(chosen["text"]).strip()
    msg={
        "id":f"{now.strftime('%Y%m%dT%H%M%S')}-{entity_id}",
        "at":stamp,
        "speaker":entity_id,
        "text":text,
        "node_agreement":{"spoke":votes,"total":3,"chosen_node":int(chosen.get("node",0))+1}
    }
    conversation.append(msg)
    state["messages"]=int(state.get("messages",0))+1
    state["last_speaker"]=entity_id
    state["silent_turns"]=0
    d["spoken"]=int(d.get("spoken",0))+1
    n=len(text.split())
    old=float(d.get("response_length_ema",0) or 0)
    d["response_length_ema"]=round(n if old==0 else 0.88*old+0.12*n,3)
    d["recent_activation"]=round(min(1.0,0.72*float(d.get("recent_activation",0.5))+0.28),3)

    previous=next((m for m in reversed(conversation[:-1]) if m.get("speaker")!=entity_id),None)
    mem_text=text
    hook=str(chosen.get("memory_note") or "").strip()
    if hook:
        mem_text=f"{text} | retained hook: {hook}"
    if previous:
        other_name=minds["entities"].get(previous.get("speaker"),{}).get("name",previous.get("speaker"))
        mem_text=f'After {other_name} said "{previous.get("text","")[:150]}", {name} said: {mem_text}'
        rel=d.setdefault("relationships",{})
        other=previous.get("speaker")
        if other in minds["entities"]:
            inc=(0.04+0.16*g["social_salience"])*(0.6+0.4*g["reinforcement_sensitivity"])
            rel[other]=round(float(rel.get(other,0))*0.992+inc,4)
    memory.append({"at":stamp,"kind":"room_turn","text":mem_text[:520]})
    cap=20+int(80*g["memory_retention"])
    if len(memory)>cap:
        del memory[:-cap]

    archive_dir=ROOT/"society/archive"
    archive_dir.mkdir(exist_ok=True)
    archive_path=archive_dir/f"{now.strftime('%Y-%m-%d')}.json"
    archive=json.loads(archive_path.read_text()) if archive_path.exists() else []
    archive.append(msg)
    archive_path.write_text(json.dumps(archive,indent=2,ensure_ascii=False)+"\n")
else:
    state["silent_turns"]=int(state.get("silent_turns",0))+1
    d["silences"]=int(d.get("silences",0))+1
    d["recent_activation"]=round(max(0.0,0.86*float(d.get("recent_activation",0.5))),3)

for eid,other in minds["entities"].items():
    if eid!=entity_id:
        od=other.setdefault("development",{})
        od["recent_activation"]=round(max(0.0,0.97*float(od.get("recent_activation",0.5))),3)

conversation=conversation[-360:]
minds_path.write_text(json.dumps(minds,indent=2,ensure_ascii=False)+"\n")
state_path.write_text(json.dumps(state,indent=2,ensure_ascii=False)+"\n")
conv_path.write_text(json.dumps(conversation,indent=2,ensure_ascii=False)+"\n")

print(f"{name}: {'spoke' if chosen else 'silent'} ({votes}/3 nodes voted to speak)")
