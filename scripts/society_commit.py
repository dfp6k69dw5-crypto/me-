#!/usr/bin/env python3
import json, os, re
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
entity_id=os.environ["ENTITY_ID"].strip().lower()
minds_path=ROOT/"society/minds.json"; state_path=ROOT/"society/state.json"; conv_path=ROOT/"society/conversation.json"; live_path=ROOT/"society/live.json"
minds=json.loads(minds_path.read_text()); state=json.loads(state_path.read_text()); conversation=json.loads(conv_path.read_text())
entity=minds["entities"][entity_id]; name=entity["name"]; g=entity["genome"]; d=entity.setdefault("development",{}); memory=entity.setdefault("memory",[])

parts=[]
for p in sorted((ROOT/"society_parts").rglob(f"{entity_id}-node-*.json")):
    try:
        obj=json.loads(p.read_text())
        if obj.get("entity")==entity_id and "error" not in obj: parts.append(obj)
    except Exception: pass

SERVICE=[r"\bhow can i help\b",r"\bhow may i help\b",r"\bwhat can i do for you\b",r"\bhow can i assist\b",r"\bdo you need (?:anything|help)\b",r"\bwhat do you need\b",r"\bhere to help\b",r"\bwhat (?:specific )?tasks or goals\b",r"\bfor (?:your|our) next meeting\b"]
META=[r"\bif [a-z]+ has something to say\b",r"\b[a-z]+ could say\b",r"\boutput only\b",r"\brecent room speech\b"]

def toks(t): return set(re.findall(r"[a-z0-9']+",(t or "").lower()))
def jac(a,b):
    a,b=toks(a),toks(b)
    if not a and not b:return 1.0
    if not a or not b:return 0.0
    return len(a&b)/len(a|b)
def forbidden(text):
    low=(text or "").lower().strip()
    if any(re.search(p,low) for p in SERVICE+META): return True
    for m in conversation[-12:]:
        if jac(text,m.get("text",""))>=0.62:return True
    return False

parts=[p for p in parts if not forbidden(str(p.get("text","") or ""))]
now=datetime.now(timezone.utc); stamp=now.isoformat().replace("+00:00","Z")
state["attempts"]=int(state.get("attempts",0))+1; state["last_run"]=stamp; d["turns"]=int(d.get("turns",0))+1
speakers=[p for p in parts if p.get("speak") and str(p.get("text","")).strip()]; votes=len(speakers); chosen=None
last_text=conversation[-1].get("text","") if conversation else ""

if votes>=2:
    scored=[]
    for p in speakers:
        text=p["text"]
        recent_sim=max((jac(text,m.get("text","")) for m in conversation[-12:]),default=0.0)
        novelty=float(p.get("novelty",max(0,1-recent_sim)))
        relevance=min(1.0,3.0*jac(text,last_text)) if last_text else 0.5
        others=[q for q in speakers if q is not p]
        diversity=1.0-(sum(jac(text,q["text"]) for q in others)/len(others) if others else 0.0)
        sal=float(p.get("salience",0.5))
        # The three nodes vote on whether to speak. The winning wording is not
        # the most consensual phrase; it is the valid candidate balancing
        # responsiveness with novelty and diversity.
        score=0.42*novelty+0.25*sal+0.20*relevance+0.13*diversity
        scored.append((score,p))
    chosen=max(scored,key=lambda x:x[0])[1]

if chosen:
    text=str(chosen["text"]).strip()
    msg={"id":f"{now.strftime('%Y%m%dT%H%M%S')}-{entity_id}","at":stamp,"speaker":entity_id,"text":text,"node_agreement":{"spoke":votes,"total":3,"chosen_node":int(chosen.get("node",0))+1}}
    conversation.append(msg); state["messages"]=int(state.get("messages",0))+1; state["last_speaker"]=entity_id; state["silent_turns"]=0
    d["spoken"]=int(d.get("spoken",0))+1
    n=len(text.split()); old=float(d.get("response_length_ema",0) or 0); d["response_length_ema"]=round(n if old==0 else .88*old+.12*n,3); d["recent_activation"]=round(min(1,.72*float(d.get("recent_activation",.5))+.28),3)

    # Only the actual spoken line teaches the entity. Unchosen node candidates
    # never alter topic weights or memories.
    tw=d.setdefault("topic_weights",{})
    for topic in chosen.get("topics") or []:
        topic=re.sub(r"[^a-z0-9 _'-]","",str(topic).lower()).strip()[:40]
        if topic:
            inc=(.08+.30*g["plasticity"])*(.55+.45*float(chosen.get("salience",.5)))*(.55+.45*g["reinforcement_sensitivity"])
            tw[topic]=round(float(tw.get(topic,0))*.985+inc,4)
    if len(tw)>40:d["topic_weights"]=dict(sorted(tw.items(),key=lambda kv:kv[1],reverse=True)[:40])

    prev=next((m for m in reversed(conversation[:-1]) if m.get("speaker")!=entity_id),None)
    rel=d.setdefault("relationships",{})
    if prev and prev.get("speaker") in minds["entities"]:
        other=prev["speaker"]; inc=(.04+.16*g["social_salience"])*(.6+.4*g["reinforcement_sensitivity"]); rel[other]=round(float(rel.get(other,0))*.992+inc,4)
    # Keep memory interpretable but do not feed verbatim memory back into the
    # language model; node generation receives only learned association cues.
    memory.append({"at":stamp,"kind":"room_turn","text":text[:260],"topics":chosen.get("topics") or [],"responded_to":prev.get("speaker") if prev else None})
    cap=20+int(80*g["memory_retention"])
    if len(memory)>cap:del memory[:-cap]

    ad=ROOT/"society/archive"; ad.mkdir(exist_ok=True); ap=ad/f"{now.strftime('%Y-%m-%d')}.json"; arc=json.loads(ap.read_text()) if ap.exists() else []; arc.append(msg); ap.write_text(json.dumps(arc,indent=2,ensure_ascii=False)+"\n")
else:
    state["silent_turns"]=int(state.get("silent_turns",0))+1; d["silences"]=int(d.get("silences",0))+1; d["recent_activation"]=round(max(0,.86*float(d.get("recent_activation",.5))),3)

for eid,other in minds["entities"].items():
    if eid!=entity_id:
        od=other.setdefault("development",{}); od["recent_activation"]=round(max(0,.97*float(od.get("recent_activation",.5))),3)
conversation=conversation[-360:]
minds_path.write_text(json.dumps(minds,indent=2,ensure_ascii=False)+"\n"); state_path.write_text(json.dumps(state,indent=2,ensure_ascii=False)+"\n"); conv_path.write_text(json.dumps(conversation,indent=2,ensure_ascii=False)+"\n")
live={"generated_at":stamp,"minds":minds,"state":state,"conversation":conversation}; live_path.write_text(json.dumps(live,indent=2,ensure_ascii=False)+"\n")
print(f"{name}: {'spoke' if chosen else 'silent'} ({votes}/3 valid nodes voted to speak)")
