#!/usr/bin/env python3
import json, os, re, hashlib, subprocess, sys, random
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
entity_id=os.environ["ENTITY_ID"].strip().lower(); node_id=int(os.environ["NODE_ID"]); run_id=os.environ.get("GITHUB_RUN_ID","local")
model_path=Path(os.environ.get("SOCIETY_MODEL_PATH", ROOT/"society_model/society-brain-q4_0.gguf")); completion_bin=Path(os.environ.get("LLAMA_COMPLETION", ROOT/"runtime/llama-completion"))
minds=json.loads((ROOT/"society/minds.json").read_text()); conversation=json.loads((ROOT/"society/conversation.json").read_text())
entity=minds["entities"][entity_id]; name=entity["name"]; g=entity["genome"]; d=entity.get("development",{})
names={k:v["name"] for k,v in minds["entities"].items()}; peer_names=", ".join(v["name"] for k,v in minds["entities"].items() if k!=entity_id)
recent=conversation[-8:]; last_text=str(recent[-1].get("text","") if recent else ""); last_words=len(last_text.split())
transcript="\n".join(f'{names.get(m.get("speaker"),m.get("speaker","?"))}: {m.get("text","")}' for m in recent) or "(The room is quiet. Everyone already knows the others; no introductions are needed.)"
topics=sorted((d.get("topic_weights") or {}).items(),key=lambda kv:kv[1],reverse=True)[:5]; topic_text=", ".join(k for k,_ in topics) or "none yet"
familiarity=min(1.0,len(conversation)/60.0)

seed=int(hashlib.sha256(f"{run_id}:{entity_id}:{node_id}".encode()).hexdigest()[:8],16)&0x7fffffff; rng=random.Random(seed)
activation=float(d.get("recent_activation",0.5) or 0.5)
drive=0.53+0.22*g["spontaneous_initiation"]-0.20*g["inhibition"]+0.08*activation
if recent: drive+=0.10*g["social_salience"]+0.05*g["attention_persistence"]
drive=max(0.18,min(0.90,drive)); wants_to_speak=rng.random()<drive
temperature=max(0.42,min(1.08,0.47+0.52*g["exploration"]+0.08*g["association_spread"]))
max_tokens=24 if not recent else int(max(14,min(40,8+1.6*last_words)))

stage_note="Shared history is still sparse; do not pretend familiarity that has not developed." if familiarity<0.25 else "Use only familiarity that is actually supported by the room history and learned associations."
system_prompt=f"""Generate exactly one possible next spoken line for {name}, one peer in an ongoing shared room with {peer_names}. There is no user, customer, visitor, task, host, meeting agenda, or service relationship. Nobody is an assistant to anyone else.

Continue as ordinary peer-to-peer conversation. Do not introduce anyone, offer assistance, ask what someone needs, ask about tasks or goals, explain what {name} could say, narrate the conversation, mention instructions, or act like a chatbot. Do not copy or closely paraphrase a recent line.

Human small-group conversation often combines a direct reaction, an optional follow-up question tied to something actually said, an observation, a short self-reference, or a topic shift. A question is never required. If the previous speaker expressed a preference or opinion, {name} may reciprocate with a comparably sized reaction or one of {name}'s own learned preferences. Do not invent a human biography, job, family, body, travel history, or off-room event. Keep the turn roughly comparable in length to the previous turn unless a short acknowledgement is natural.

{name} has no predetermined personality. Wording should emerge from the immediate exchange, learned associations, genome-driven sampling, and accumulated interaction. {stage_note}
Learned association cues: {topic_text}
Output only the spoken line, without a name label or quotation marks."""
base_prompt=f"Recent room speech:\n{transcript}\n\n{name}:"

SERVICE=[r"\bhow can i help\b",r"\bhow may i help\b",r"\bwhat can i do for you\b",r"\bhow can i assist\b",r"\bdo you need (?:anything|help)\b",r"\bwhat do you need\b",r"\bhere to help\b",r"\bwhat (?:specific )?tasks or goals\b",r"\bfor (?:your|our) next meeting\b"]
META=[r"\bif [a-z]+ has something to say\b",r"\b[a-z]+ could say\b",r"\b[a-z]+ is now in the room\b",r"\boutput only\b",r"\brecent room speech\b",r"\bcontinue directly from here\b",r"\bprevious candidate\b",r"\bprevious (?:response|conversation) was (?:too )?(?:generic|repetitive)\b",r"\btoo generic or repetitive\b",r"\bgenuinely different peer remark\b",r"\bgrounded in the room\b",r"\bservice/task question\b",r"\bproduce a genuinely different\b",r"\bgenerate a fresh, thought-provoking statement\b"]
def tokens(t): return set(re.findall(r"[a-z0-9']+",(t or "").lower()))
def jac(a,b):
    a,b=tokens(a),tokens(b)
    if not a and not b:return 1.0
    if not a or not b:return 0.0
    return len(a&b)/len(a|b)
def max_recent_similarity(text): return max((jac(text,m.get("text","")) for m in recent),default=0.0)
def forbidden_reason(text):
    low=(text or "").lower().strip()
    for pat in SERVICE:
        if re.search(pat,low):return "service-language"
    for pat in META:
        if re.search(pat,low):return "prompt-echo"
    for m in recent:
        if " ".join(low.split())==" ".join(str(m.get("text","")).lower().split()) and low:return "exact-repeat"
    sim=max_recent_similarity(text)
    if sim>=0.62:return f"near-repeat-{sim:.2f}"
    return ""
def request_local_model(local_seed,attempt):
    if not model_path.is_file():raise RuntimeError(f"GitHub-held model missing: {model_path}")
    if not completion_bin.is_file():raise RuntimeError(f"GitHub-held completion runtime missing: {completion_bin}")
    retry="" if attempt==0 else "\nTry another natural line. It must differ substantially from the first attempt and continue the peers' current exchange."
    cmd=[str(completion_bin),"-m",str(model_path),"--jinja","--single-turn","-sys",system_prompt,"-p",base_prompt+retry,"-n",str(max_tokens),"-c","1024","-t","4","--no-warmup","--temp",f"{temperature:.3f}","--top-p","0.93","-s",str(local_seed),"--simple-io","--no-display-prompt","--log-verbosity","0"]
    proc=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=90)
    if proc.returncode!=0:
        detail=(proc.stderr or proc.stdout or "llama-completion failed").strip();raise RuntimeError(f"local inference exit {proc.returncode}: {detail[-900:]}")
    return (proc.stdout or proc.stderr or "").strip()
def clean_generation(raw):
    text=(raw or "").replace("\r","");text=re.sub(r"\x1b\[[0-9;?]*[A-Za-z]","",text)
    for marker in ("<|im_end|>","<|eot_id|>","<|end_of_text|>","[end of text]","[end of sentence]"):
        if marker.lower() in text.lower():text=re.split(re.escape(marker),text,flags=re.I,maxsplit=1)[0]
    text=text.strip();text=re.sub(rf"^(?:assistant\s*[:>-]?\s*|{re.escape(name)}\s+(?:says|said)(?:\s+next)?\s*:\s*|{re.escape(name)}\s*[:>-]\s*)","",text,flags=re.I).strip()
    if len(text)>=2 and text[0]==text[-1] and text[0] in {'\"',"'"}:text=text[1:-1].strip()
    if len(text)>260:text=text[:260].rsplit(" ",1)[0].rstrip()+"…"
    return text
STOP={"that","this","with","from","have","just","what","when","where","there","they","them","then","than","your","about","would","could","should","into","only","really","some","more","very","like","because","been","being","does","will","well","yeah","okay","also","still","room","says","said","next"}
def infer_topics(text):
    out=[]
    for w in re.findall(r"[A-Za-z][A-Za-z'-]{3,}",(text or "").lower()):
        w=w.strip("'-")
        if w and w not in STOP and w not in out:out.append(w)
        if len(out)>=3:break
    return out
def novelty(text):
    if not text:return 0.0
    sim=max_recent_similarity(text);unique=tokens(text);recent_words=tokens(" ".join(m.get("text","") for m in recent));new_ratio=len(unique-recent_words)/len(unique) if unique else 0.0
    return max(0.0,min(1.0,0.60*(1.0-sim)+0.40*new_ratio))

outdir=ROOT/"society_parts";outdir.mkdir(exist_ok=True)
result={"entity":entity_id,"name":name,"node":node_id,"speak":False,"text":"","salience":0.0,"novelty":0.0,"topics":[],"memory_note":"","engine":"github-held-gguf","model_asset":"society-brain-v1/society-brain-q4_0.gguf","speech_drive":round(drive,4)}
error=None;rejected=[]
try:
    if wants_to_speak:
        text=""
        for attempt in range(4):
            candidate=clean_generation(request_local_model((seed+attempt*104729)&0x7fffffff,attempt))
            if not candidate:rejected.append("empty");continue
            reason=forbidden_reason(candidate)
            if reason:rejected.append(reason);continue
            text=candidate;break
        if text:
            nov=novelty(text);result["speak"]=True;result["text"]=text;result["topics"]=infer_topics(text);result["novelty"]=round(nov,4)
            sal=0.24+0.18*min(1,len(text.split())/18)+0.39*nov+0.19*g["novelty_weight"];result["salience"]=round(max(0,min(1,sal)),4)
            if result["salience"]>=0.66:result["memory_note"]=text[:160]
        elif rejected:result["rejected_candidates"]=rejected
except Exception as e:
    error=str(e)[:900];result["error"]=error
path=outdir/f"{entity_id}-node-{node_id}.json";path.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n");print(json.dumps(result,ensure_ascii=False))
if error:sys.exit(2)
