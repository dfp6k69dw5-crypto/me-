#!/usr/bin/env python3
import json, os, re
from collections import Counter
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
entity_id=os.environ["ENTITY_ID"].strip().lower()
minds_path=ROOT/"society/minds.json"; state_path=ROOT/"society/state.json"; conv_path=ROOT/"society/conversation.json"; live_path=ROOT/"society/live.json"
minds=json.loads(minds_path.read_text()); state=json.loads(state_path.read_text()); conversation=json.loads(conv_path.read_text())
entity=minds["entities"][entity_id]; name=entity["name"]; g=entity["genome"]; d=entity.setdefault("development",{}); memory=entity.setdefault("memory",[])

raw_parts=[]
for p in sorted((ROOT/"society_parts").rglob(f"{entity_id}-node-*.json")):
    try:
        obj=json.loads(p.read_text())
        if obj.get("entity")==entity_id and "error" not in obj: raw_parts.append(obj)
    except Exception: pass

SERVICE=[r"\bhow can i help\b",r"\bhow may i help\b",r"\bwhat can i do for you\b",r"\bhow can i assist\b",r"\bdo you need (?:anything|help)\b",r"\bwhat do you need\b",r"\bhere to help\b",r"\bwhat (?:specific )?tasks or goals\b",r"\bfor (?:your|our) next meeting\b"]
FACILITATOR=[r"\bare you looking for\b",r"\bwhat (?:would|do) you like to (?:talk about|discuss|explore|do)\b",r"\bwhat do we want to do\b",r"\bwhat should we do\b",r"\bwhat (?:specific )?topic\b",r"\btopic to (?:explore|discuss|talk about)\b",r"\banything (?:you'd|you would) like to (?:talk about|discuss|explore|do)\b"]
META=[r"\bif [a-z]+ has something to say\b",r"\b[a-z]+ could say\b",r"\boutput only\b",r"\brecent room speech\b",r"\bprevious candidate\b",r"\btoo generic or repetitive\b",r"\btry another natural line\b",r"\bdiffer substantially from the first attempt\b",r"\bselected earlier memories\b",r"\bpersistent adult background\b",r"\bcognitive move\b"]
STOP={"that","this","with","from","have","has","had","just","what","when","where","there","they","them","then","than","your","about","would","could","should","into","only","really","some","more","very","like","because","been","being","does","doing","will","well","yeah","okay","also","still","room","says","said","next","lets","let's","dont","don't","cant","can't","im","i'm","ive","i've","weve","we've","were","we're","youre","you're","thats","that's","its","it's","maybe","kind","sort","thing","things","something","anything","someone","everyone","human","people","person","conversation","talking","talk","say","saying","think","thinking","thought","know","knowing","mean","means","seem","seems","want","wants","make","making","start","starting","try","trying","work","working","good","great","nice","sure","right","actually","probably","pretty","little","much","many","few","around","again","already","even","ever","never","always","often","sometimes"}
name_words={w.lower() for v in minds["entities"].values() for w in re.findall(r"[A-Za-z]+",v["name"])}
speaker_label_re=re.compile(r"(?im)(?:^|\n)\s*(?:"+"|".join(re.escape(v["name"]) for v in minds["entities"].values())+r")\s*:")

def toks(t): return set(re.findall(r"[a-z0-9']+",(t or "").lower()))
def jac(a,b):
    a,b=toks(a),toks(b)
    if not a and not b:return 1.0
    if not a or not b:return 0.0
    return len(a&b)/len(a|b)
def norm(t): return " ".join(str(t or "").lower().split())
def content_tokens(text):
    out=[]
    for w in re.findall(r"[A-Za-z][A-Za-z'-]{3,}",(text or "").lower()):
        w=w.strip("'-")
        if w and len(w)>=4 and w not in STOP and w not in name_words: out.append(w)
    return out
def meaningful_topic(topic):
    t=str(topic or "").lower().strip()
    return bool(t) and t not in STOP and t not in name_words and len(t)>=4

def core_forbidden(text):
    low=(text or "").lower().strip()
    return (not low) or bool(speaker_label_re.search(text or "")) or any(re.search(p,low) for p in SERVICE+FACILITATOR+META)
def exact_recent(text):
    n=norm(text)
    return bool(n) and any(n==norm(m.get("text","")) for m in conversation[-14:])
def recent_similarity(text): return max((jac(text,m.get("text","")) for m in conversation[-10:]),default=0.0)

# Measure whether the recent room has collapsed around a small repeated vocabulary.
# These words are used only as a temporary rejection signal; they never supply a new topic.
window=conversation[-12:]; flat=[w for m in window for w in set(content_tokens(m.get("text","")))]; counts=Counter(flat)
if flat:
    repeated=sum(c-1 for c in counts.values() if c>1); room_fatigue=max(0.0,min(1.0,repeated/max(4,len(window)*1.6)))
else: room_fatigue=0.0
rut_words={w for w,c in counts.most_common(10) if c>=2}
def rut_overlap(text): return len(set(content_tokens(text)) & rut_words)

# Natural short pauses remain possible, but the room cannot drift into hours of silence.
HARD_SILENCE=3
silent_before=max(0,int(state.get("silent_turns",0) or 0)); silence_pressure=max(0.0,min(1.0,silent_before/HARD_SILENCE)); hard_continuation=silent_before>=HARD_SILENCE
repeat_limit=max(.46,min(.80,.64-.10*room_fatigue+.16*silence_pressure))

def forbidden(text,mode="continue"):
    if core_forbidden(text) or exact_recent(text): return True
    overlap=rut_overlap(text)
    if room_fatigue>=.72:
        if mode=="jump" and overlap>0: return True
        if mode=="associate" and overlap>=2: return True
    return recent_similarity(text)>=repeat_limit

parts=[]
for p in raw_parts:
    text=str(p.get("text","") or ""); mode=str(p.get("cognitive_mode","continue"))
    if not forbidden(text,mode): parts.append(p)
now=datetime.now(timezone.utc); stamp=now.isoformat().replace("+00:00","Z")
state["attempts"]=int(state.get("attempts",0))+1; state["last_run"]=stamp; d["turns"]=int(d.get("turns",0))+1
speakers=[p for p in parts if p.get("speak") and str(p.get("text","")).strip()]; votes=len(speakers); chosen=None; emergency_used=False
last_text=conversation[-1].get("text","") if conversation else ""; required_votes=1 if hard_continuation else 2

if votes>=required_votes:
    scored=[]
    for p in speakers:
        text=p["text"]; recent_sim=recent_similarity(text); novelty=float(p.get("novelty",max(0,1-recent_sim))); relevance=min(1.0,3.0*jac(text,last_text)) if last_text else 0.5
        others=[q for q in speakers if q is not p]; diversity=1.0-(sum(jac(text,q["text"]) for q in others)/len(others) if others else 0.0); sal=float(p.get("salience",0.5)); mode=str(p.get("cognitive_mode","continue"))
        relevance_w=.28*(1.0-room_fatigue); diversity_w=.15+.18*room_fatigue; novelty_w=.32+.10*room_fatigue
        mode_bonus=room_fatigue*({"continue":-.05,"associate":.08,"jump":.16}.get(mode,0.0))
        rut_penalty=room_fatigue*.10*rut_overlap(text)
        score=novelty_w*novelty+.22*sal+relevance_w*relevance+diversity_w*diversity+mode_bonus-rut_penalty
        scored.append((score,p))
    chosen=max(scored,key=lambda x:x[0])[1]

# Hard fallback after three silent room turns. Even here, malformed transcript echoes and
# facilitator language are never published.
if hard_continuation and not chosen:
    emergency=[]
    for p in raw_parts:
        e=p.get("emergency_candidate") or {}; text=str(e.get("text","") or "").strip(); mode=str(e.get("cognitive_mode") or p.get("cognitive_mode","continue"))
        if not text or core_forbidden(text): continue
        overlap=rut_overlap(text)
        if room_fatigue>=.72 and ((mode=="jump" and overlap>0) or (mode=="associate" and overlap>=2)): continue
        sim=recent_similarity(text)
        mode_cost={"jump":-.16,"associate":-.05,"continue":.10}.get(mode,0.0)*room_fatigue
        emergency.append((sim+.11*overlap+mode_cost,p,e))
    if emergency:
        _,p,e=min(emergency,key=lambda x:x[0]); sim=recent_similarity(str(e.get("text","") or ""))
        chosen={"node":p.get("node",0),"text":e.get("text",""),"topics":e.get("topics") or [],"novelty":float(e.get("novelty",max(0,1-sim))),"salience":0.45,"cognitive_mode":e.get("cognitive_mode") or p.get("cognitive_mode","continue")}; emergency_used=True

if chosen:
    text=str(chosen["text"]).strip(); mode=str(chosen.get("cognitive_mode","continue")); agreement={"spoke":votes,"total":3,"chosen_node":int(chosen.get("node",0))+1,"cognitive_mode":mode}
    if hard_continuation: agreement["silence_ceiling"]=True
    if emergency_used: agreement["emergency_generated_candidate"]=True
    msg={"id":f"{now.strftime('%Y%m%dT%H%M%S')}-{entity_id}","at":stamp,"speaker":entity_id,"text":text,"node_agreement":agreement}
    conversation.append(msg); state["messages"]=int(state.get("messages",0))+1; state["last_speaker"]=entity_id; state["silent_turns"]=0
    d["spoken"]=int(d.get("spoken",0))+1; n=len(text.split()); old=float(d.get("response_length_ema",0) or 0); d["response_length_ema"]=round(n if old==0 else .88*old+.12*n,3); d["recent_activation"]=round(min(1,.72*float(d.get("recent_activation",.5))+.28),3)
    modes=d.setdefault("cognitive_modes",{"continue":0,"associate":0,"jump":0}); modes[mode]=int(modes.get(mode,0))+1

    # Real forgetting: all learned topics decay every spoken turn. Immediate reuse builds
    # short-lived fatigue, which suppresses a cue for a while without deleting the memory.
    tw=d.setdefault("topic_weights",{}); tf=d.setdefault("topic_fatigue",{})
    clean_tw={}
    for k,v in tw.items():
        key=str(k).lower().strip()
        if meaningful_topic(key):
            nv=float(v)*.982
            if nv>.025: clean_tw[key]=round(nv,4)
    tw=clean_tw; d["topic_weights"]=tw
    new_tf={}
    for k,v in tf.items():
        key=str(k).lower().strip(); nv=float(v)*.76
        if meaningful_topic(key) and nv>.025: new_tf[key]=round(nv,4)
    tf=new_tf; d["topic_fatigue"]=tf

    reinforcement_scale=0.22 if emergency_used else {"continue":.72,"associate":.92,"jump":.82}.get(mode,.8)
    for topic in chosen.get("topics") or []:
        topic=re.sub(r"[^a-z0-9 _'-]","",str(topic).lower()).strip()[:40]
        if meaningful_topic(topic):
            inc=reinforcement_scale*(.07+.24*g["plasticity"])*(.50+.50*float(chosen.get("salience",.5)))*(.52+.48*g["reinforcement_sensitivity"])
            tw[topic]=round(float(tw.get(topic,0))+inc,4); tf[topic]=round(min(1.25,float(tf.get(topic,0))+.42),4)
    if len(tw)>50:d["topic_weights"]=dict(sorted(tw.items(),key=lambda kv:kv[1],reverse=True)[:50])
    if len(tf)>50:d["topic_fatigue"]=dict(sorted(tf.items(),key=lambda kv:kv[1],reverse=True)[:50])

    prev=next((m for m in reversed(conversation[:-1]) if m.get("speaker")!=entity_id),None); rel=d.setdefault("relationships",{})
    if prev and prev.get("speaker") in minds["entities"]:
        other=prev["speaker"]; inc=(.04+.16*g["social_salience"])*(.6+.4*g["reinforcement_sensitivity"]); rel[other]=round(float(rel.get(other,0))*.992+inc,4)
    memory.append({"at":stamp,"kind":"room_turn","text":text[:260],"topics":[t for t in chosen.get("topics") or [] if meaningful_topic(t)],"responded_to":prev.get("speaker") if prev else None,"cognitive_mode":mode})
    cap=20+int(80*g["memory_retention"])
    if len(memory)>cap:del memory[:-cap]

    ad=ROOT/"society/archive"; ad.mkdir(exist_ok=True); ap=ad/f"{now.strftime('%Y-%m-%d')}.json"; arc=json.loads(ap.read_text()) if ap.exists() else []; arc.append(msg); ap.write_text(json.dumps(arc,indent=2,ensure_ascii=False)+"\n")
else:
    state["silent_turns"]=silent_before+1; d["silences"]=int(d.get("silences",0))+1; d["recent_activation"]=round(max(0,.86*float(d.get("recent_activation",.5))),3)

for eid,other in minds["entities"].items():
    if eid!=entity_id:
        od=other.setdefault("development",{}); od["recent_activation"]=round(max(0,.97*float(od.get("recent_activation",.5))),3)
        if od.get("topic_fatigue"):
            od["topic_fatigue"]={k:round(float(v)*.88,4) for k,v in od["topic_fatigue"].items() if float(v)*.88>.025}
conversation=conversation[-360:]
state["note"]="Conversation state is committed by The Room GitHub Action."
minds_path.write_text(json.dumps(minds,indent=2,ensure_ascii=False)+"\n"); state_path.write_text(json.dumps(state,indent=2,ensure_ascii=False)+"\n"); conv_path.write_text(json.dumps(conversation,indent=2,ensure_ascii=False)+"\n")
live={"generated_at":stamp,"minds":minds,"state":state,"conversation":conversation}; live_path.write_text(json.dumps(live,indent=2,ensure_ascii=False)+"\n")
extra=f" {mode}" if chosen else ""; extra+=(" emergency" if emergency_used else (" ceiling" if hard_continuation and chosen else ""))
print(f"{name}: {'spoke' if chosen else 'silent'} ({votes}/3 valid nodes voted to speak{extra})")
