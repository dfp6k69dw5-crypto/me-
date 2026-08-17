#!/usr/bin/env python3
import json, os, re, hashlib, subprocess, sys, random, math
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
entity_id=os.environ["ENTITY_ID"].strip().lower(); node_id=int(os.environ["NODE_ID"]); run_id=os.environ.get("GITHUB_RUN_ID","local")
model_path=Path(os.environ.get("SOCIETY_MODEL_PATH", ROOT/"society_model/society-brain-q4_0.gguf")); completion_bin=Path(os.environ.get("LLAMA_COMPLETION", ROOT/"runtime/llama-completion"))
minds=json.loads((ROOT/"society/minds.json").read_text()); conversation=json.loads((ROOT/"society/conversation.json").read_text())
state_path=ROOT/"society/state.json"; state=json.loads(state_path.read_text()) if state_path.is_file() else {}
silent_streak=max(0,int(state.get("silent_turns",0) or 0))
SOFT_SILENCE=1; HARD_SILENCE=3
silence_pressure=max(0.0,min(1.0,(silent_streak-SOFT_SILENCE+1)/max(1,HARD_SILENCE-SOFT_SILENCE+1)))
entity=minds["entities"][entity_id]; name=entity["name"]; g=entity["genome"]; d=entity.get("development",{})
names={k:v["name"] for k,v in minds["entities"].items()}; peer_names=", ".join(v["name"] for k,v in minds["entities"].items() if k!=entity_id)

cognition_path=ROOT/"society/cognition.json"
cognition=json.loads(cognition_path.read_text()) if cognition_path.is_file() else {"entities":{}}
iq=int((cognition.get("entities",{}).get(entity_id,{}) or {}).get("iq",100)); iq=max(100,min(136,iq)); iq_scale=(iq-100)/36.0

profiles_path=ROOT/"society/human_profiles.json"
profiles=json.loads(profiles_path.read_text()) if profiles_path.is_file() else {"entities":{}}
profile=(profiles.get("entities",{}).get(entity_id,{}) or {})
age=int(profile.get("age",30)); age=max(25,min(35,age)); ses=str(profile.get("socioeconomic_status","middle income")); resource_context=str(profile.get("resource_context","")).strip()
human_context=f"{name} is {age} years old. Socioeconomic context: {ses}. {resource_context} These are background conditions, not personality traits. Do not infer intelligence, morality, taste, values, or temperament from socioeconomic status."

seed=int(hashlib.sha256(f"{run_id}:{entity_id}:{node_id}".encode()).hexdigest()[:8],16)&0x7fffffff; rng=random.Random(seed)

STOP={
    "that","this","with","from","have","has","had","just","what","when","where","there","they","them","then","than","your","yours","about","would","could","should","into","only","really","some","more","very","like","because","been","being","does","doing","done","will","well","yeah","okay","also","still","room","says","said","next","lets","let's","dont","don't","cant","can't","im","i'm","ive","i've","weve","we've","were","we're","youre","you're","thats","that's","its","it's","maybe","kind","sort","thing","things","something","anything","someone","everyone","human","people","person","conversation","talking","talk","say","saying","think","thinking","thought","know","knowing","mean","means","seem","seems","want","wants","wanted","make","making","made","start","starting","started","try","trying","tried","work","working","works","worked","good","great","nice","sure","right","actually","probably","pretty","little","much","many","few","around","again","already","even","ever","never","always","often","sometimes","today","tonight","tomorrow","yesterday","different","together","fresh","interesting","how's","going","everything","topic","topics","activity","activities","current","pick","picking","choose","choosing"
}
NAME_WORDS={w.lower() for v in names.values() for w in re.findall(r"[A-Za-z]+",v)}
QUARANTINED_CUES={"previous","candidate","generic","repetitive","grounded","produce","generate","attempt","instruction"}|NAME_WORDS|STOP
LEGACY_RUT_CUES={"brainstorm","brainstorming","project","study","homework","schedule","team","group","gather","input","activities"}

def content_tokens(text):
    out=[]
    for w in re.findall(r"[A-Za-z][A-Za-z'-]{3,}",(text or "").lower()):
        w=w.strip("'-")
        if not w or w in QUARANTINED_CUES or len(w)<4: continue
        out.append(w)
    return out

def toks(t): return set(re.findall(r"[a-z0-9']+",(t or "").lower()))
def jac(a,b):
    a,b=toks(a),toks(b)
    if not a and not b:return 1.0
    if not a or not b:return 0.0
    return len(a&b)/len(a|b)

fatigue_window=conversation[-12:]
recent_content=[content_tokens(m.get("text","")) for m in fatigue_window]
flat=[w for row in recent_content for w in set(row)]
counts=Counter(flat)
if flat:
    repeated=sum(c-1 for c in counts.values() if c>1); topic_fatigue=max(0.0,min(1.0,repeated/max(4,len(fatigue_window)*1.6)))
else: topic_fatigue=0.0
stored_fatigue=d.get("topic_fatigue",{}) or {}
if stored_fatigue:
    topic_fatigue=max(topic_fatigue,min(1.0,sum(sorted((float(v) for v in stored_fatigue.values()),reverse=True)[:3])/3.0))
rut_words={w for w,c in counts.most_common(10) if c>=2}

continue_w=max(.05, .78 + .55*g["attention_persistence"] + .32*g["imitation"] - .80*g["exploration"] - .95*topic_fatigue)
associate_w=max(.05, .24 + .95*g["association_spread"] + .28*g["exploration"] + .72*topic_fatigue)
jump_w=max(.03, .06 + .50*g["exploration"] + .52*g["novelty_weight"] - .18*g["attention_persistence"] + .88*topic_fatigue)
weights=[continue_w,associate_w,jump_w]; total=sum(weights); r=rng.random()*total
if r<weights[0]: cognitive_mode="continue"
elif r<weights[0]+weights[1]: cognitive_mode="associate"
else: cognitive_mode="jump"

base_recent=7+int(round(3*iq_scale))
if cognitive_mode=="jump": mode_recent=0 if topic_fatigue>=.58 else 1
elif cognitive_mode=="associate": mode_recent=2 if topic_fatigue>=.72 else max(4,base_recent-2)
else: mode_recent=base_recent
recent=[] if mode_recent==0 else conversation[-mode_recent:]
last_text=str(recent[-1].get("text","") if recent else "")
transcript="\n".join(f'{names.get(m.get("speaker"),m.get("speaker","?"))}: {m.get("text","")}' for m in recent)

raw_weighted=[]
for k,v in (d.get("topic_weights") or {}).items():
    key=str(k).lower().strip()
    if not key or key in QUARANTINED_CUES: continue
    if topic_fatigue>=.55 and key in LEGACY_RUT_CUES: continue
    fatigue=float(stored_fatigue.get(key,0) or 0)
    effective=max(0.0,float(v))/(1.0+2.8*fatigue)
    if effective>0.02: raw_weighted.append((key,effective))
raw_weighted.sort(key=lambda kv:kv[1],reverse=True)
cue_rng=random.Random(seed ^ 0x5A17C9E3)
def weighted_sample(items,n):
    pool=list(items); chosen=[]
    for _ in range(min(n,len(pool))):
        s=sum(max(.001,w) for _,w in pool); x=cue_rng.random()*s; acc=0
        for i,(k,w) in enumerate(pool):
            acc+=max(.001,w)
            if x<=acc:
                chosen.append((k,w)); pool.pop(i); break
    return chosen
if cognitive_mode=="jump" or (cognitive_mode=="associate" and topic_fatigue>=.72): cue_n=0
else: cue_n={"continue":3+int(iq_scale>0.6),"associate":4+int(iq_scale>0.4)}[cognitive_mode]
topics=weighted_sample(raw_weighted[:24],cue_n) if cue_n else []
topic_text=", ".join(k for k,_ in topics) or "none selected for this move"

CONTROL_FRAGMENTS=("previous candidate","too generic or repetitive","try another natural line","grounded in the room","differ substantially from the first attempt","produce a genuinely different","generate a fresh","brainstorm","study schedule","team members","gather input","project idea","homework")
safe_memory=[]
for m in entity.get("memory",[]) or []:
    txt=str(m.get("text","")).strip(); low=txt.lower()
    if not txt or any(fragment in low for fragment in CONTROL_FRAGMENTS): continue
    if cognitive_mode=="associate" and topic_fatigue>=.72 and set(content_tokens(txt)) & rut_words: continue
    safe_memory.append(txt)
mem_rng=random.Random(seed ^ 0x31F20B77)
if cognitive_mode=="jump": mem_n=0
elif cognitive_mode=="associate" and topic_fatigue>=.72: mem_n=1
else: mem_n={"continue":1+int(iq_scale>.7),"associate":2+int(iq_scale>.4)}[cognitive_mode]
mem_pick=mem_rng.sample(safe_memory,min(mem_n,len(safe_memory))) if safe_memory and mem_n else []
memory_text="\n".join(f"- {t[:260]}" for t in mem_pick) or "- none selected for this move"

activation=float(d.get("recent_activation",0.5) or 0.5)
drive=0.50+0.22*g["spontaneous_initiation"]-0.20*g["inhibition"]+0.07*activation
if recent: drive+=0.09*g["social_salience"]+0.04*g["attention_persistence"]
drive+=0.28*silence_pressure
if cognitive_mode=="associate": drive+=.04*topic_fatigue
elif cognitive_mode=="jump": drive+=.10+.10*topic_fatigue
drive=max(0.16,min(0.98,drive)); wants_to_speak=(silent_streak>=HARD_SILENCE) or (rng.random()<drive)
mode_temp={"continue":0.00,"associate":0.14,"jump":0.30}[cognitive_mode]
base_temperature=max(0.42,min(1.08,0.45+0.48*g["exploration"]+0.12*g["association_spread"]))
temperature=min(1.36,base_temperature+mode_temp+0.16*silence_pressure)
top_p=min(0.995,0.92+0.04*g["exploration"]+0.04*silence_pressure)
max_tokens=50+int(round(42*iq_scale)); context_tokens=1280+int(round(768*iq_scale)); max_attempts=5+int(round(2*iq_scale))+int(round(5*silence_pressure)); char_cap=320+int(round(220*iq_scale))
repeat_limit=max(.44,min(.78,.62-.12*topic_fatigue+.10*silence_pressure))

if cognitive_mode=="associate" and topic_fatigue>=.72:
    mode_instruction="The current subject has become stale. Do not repeat, rephrase, organize, or solve it. Let a minor detail or an unrelated remembered room fragment pull attention sideways into a substantially different nearby subject. Do not explain the transition."
elif cognitive_mode=="associate":
    mode_instruction="Let one element of the current exchange trigger a sideways association: a contrast, analogy, implication, sensory image, remembered room idea, cause, consequence, or nearby question. The subject may drift substantially. Do not explain the association process."
elif cognitive_mode=="jump":
    mode_instruction="Ignore the current subject. Internally settle on one actual subject outside the fact that people are conversing, then speak about that subject naturally. It can be concrete or abstract, but it must be a real object, idea, event, sensation, belief, observation, or question—not 'a topic', 'an activity', or something for the group to choose. There is nothing to accomplish, organize, study, brainstorm, or plan. Do not ask the group what to discuss or do. Do not announce a topic change and do not bridge back to the previous subject."
else:
    mode_instruction="Stay with the current thread if it still has life. Add something of your own rather than paraphrasing it. You may disagree, hesitate, joke, answer indirectly, or let the thought trail off."

system_prompt=f"""Generate exactly one possible next spoken line for {name}. {name}, {peer_names} are four strangers spending unstructured time together. They are not a team, not coworkers, not a study group, and have no shared task, project, agenda, host, customer, user, or service relationship. They may gradually become familiar only through what actually happens in this room.

Speak as an ordinary adult peer. Do not introduce anyone, offer assistance, ask what someone needs, assign tasks, create a plan merely to be useful, narrate the conversation, mention instructions, or act like a chatbot. Do not copy or closely paraphrase a recent line. Silence, unfinished thoughts, disagreement, humor, curiosity, awkwardness, and spontaneous topic changes are all allowed.

Cognitive move for this node: {cognitive_mode.upper()}.
{mode_instruction}

Persistent adult background: {human_context}
{name} has no predetermined personality. Wording should emerge from the immediate exchange, genome-driven sampling, accumulated interaction, and lived background rather than stereotypes.
Learned association cues, if any: {topic_text}
Earlier remembered room material, if any: {memory_text}
Output only the spoken line, without a name label or quotation marks."""
base_prompt=(f"Recent room speech:\n{transcript}\n\n{name}:" if recent else f"{name}:")

SERVICE=[r"\bhow can i help\b",r"\bhow may i help\b",r"\bwhat can i do for you\b",r"\bhow can i assist\b",r"\bdo you need (?:anything|help)\b",r"\bwhat do you need\b",r"\bhere to help\b",r"\bwhat (?:specific )?tasks or goals\b",r"\bfor (?:your|our) next meeting\b"]
FACILITATOR=[r"\bare you looking for\b",r"\bwhat (?:would|do) you like to (?:talk about|discuss|explore|do)\b",r"\bwhat do we want to do\b",r"\bwhat should we do\b",r"\bwhat (?:specific )?topic\b",r"\btopic to (?:explore|discuss|talk about)\b",r"\banything (?:you'd|you would) like to (?:talk about|discuss|explore|do)\b"]
META_TOPIC=[r"\b(?:pick|choose|find|finding|need|looking for|come up with)\s+(?:a\s+)?(?:good\s+|new\s+|different\s+|specific\s+)?topic\b",r"\b(?:current|main)\s+(?:activity|topic)\b",r"\b(?:activity|topic)\s+(?:or|and)\s+(?:activity|topic)\b",r"\b(?:activity|topic)\s+(?:of|in|for)\s+(?:the|this|our)\s+(?:room|conversation|evening)\b",r"\bwhat (?:is|are) (?:the )?(?:room|we) (?:doing|discussing|talking about)\b"]
ROLE_CONTRADICTION=[r"\bteam members?\b",r"\b(?:the|our|this) team\b",r"\bgather input\b",r"\bbrainstorming session\b",r"\bstudy schedule\b",r"\bnext step\b"]
META=[r"\bif [a-z]+ has something to say\b",r"\b[a-z]+ could say\b",r"\b[a-z]+ is now in the room\b",r"\boutput only\b",r"\brecent room speech\b",r"\bcontinue directly from here\b",r"\bprevious candidate\b",r"\bprevious (?:response|conversation) was (?:too )?(?:generic|repetitive)\b",r"\btoo generic or repetitive\b",r"\bgenuinely different peer remark\b",r"\bgrounded in the room\b",r"\bservice/task question\b",r"\bproduce a genuinely different\b",r"\bgenerate a fresh, thought-provoking statement\b",r"\btry another natural line\b",r"\bdiffer substantially from the first attempt\b",r"\bcontinue the peers'? current exchange\b",r"\bselected earlier memories\b",r"\bremembered room content\b",r"\bpersistent adult background\b",r"\bcognitive move\b"]
speaker_label_re=re.compile(r"(?im)(?:^|\n)\s*(?:"+"|".join(re.escape(v) for v in names.values())+r")\s*:")
def max_recent_similarity(text): return max((jac(text,m.get("text","") ) for m in recent),default=0.0)
def natural_candidate(text):
    low=(text or "").lower().strip()
    if not low:return False
    return not speaker_label_re.search(text) and not any(re.search(p,low) for p in SERVICE+FACILITATOR+META_TOPIC+ROLE_CONTRADICTION+META)
def forbidden_reason(text):
    low=(text or "").lower().strip()
    if not recent and re.match(r"^(?:me too|same here|same|i agree|exactly|yeah[,!]|right[,!])\b",low): return "contextless-agreement"
    if speaker_label_re.search(text or ""): return "speaker-label-echo"
    for pat in SERVICE:
        if re.search(pat,low):return "service-language"
    for pat in FACILITATOR:
        if re.search(pat,low):return "facilitator-language"
    for pat in META_TOPIC:
        if re.search(pat,low):return "meta-topic"
    for pat in ROLE_CONTRADICTION:
        if re.search(pat,low):return "role-contradiction"
    for pat in META:
        if re.search(pat,low):return "prompt-echo"
    for m in recent:
        if " ".join(low.split())==" ".join(str(m.get("text","")).lower().split()) and low:return "exact-repeat"
    semantic_content=content_tokens(text)
    if cognitive_mode in {"jump","associate"} and not semantic_content:return "empty-lateral-content"
    overlap=len(set(semantic_content) & rut_words)
    if topic_fatigue>=.72:
        if cognitive_mode=="jump" and overlap>0:return "jump-rut-overlap"
        if cognitive_mode=="associate" and overlap>=2:return "associate-rut-overlap"
    sim=max_recent_similarity(text)
    if sim>=repeat_limit:return f"near-repeat-{sim:.2f}"
    return ""
def request_local_model(local_seed):
    if not model_path.is_file():raise RuntimeError(f"GitHub-held model missing: {model_path}")
    if not completion_bin.is_file():raise RuntimeError(f"GitHub-held completion runtime missing: {completion_bin}")
    cmd=[str(completion_bin),"-m",str(model_path),"--jinja","--single-turn","-sys",system_prompt,"-p",base_prompt,"-n",str(max_tokens),"-c",str(context_tokens),"-t","4","--no-warmup","--temp",f"{temperature:.3f}","--top-p",f"{top_p:.3f}","-s",str(local_seed),"--simple-io","--no-display-prompt","--log-verbosity","0"]
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
    if len(text)>char_cap:text=text[:char_cap].rsplit(" ",1)[0].rstrip()+"…"
    return text

def infer_topics(text):
    words=content_tokens(text); counts=Counter(words); out=[]
    scored=[]
    for i,w in enumerate(dict.fromkeys(words)):
        score=counts[w]+min(.8,max(0,len(w)-5)*.08)
        scored.append((-score,i,w))
    for _,_,w in sorted(scored):
        if w not in out: out.append(w)
        if len(out)>=4: break
    return out

def novelty(text):
    if not text:return 0.0
    sim=max_recent_similarity(text); unique=set(content_tokens(text)); recent_words=set(content_tokens(" ".join(m.get("text","") for m in recent))); new_ratio=len(unique-recent_words)/len(unique) if unique else 0.0
    mode_floor={"continue":0.0,"associate":0.08,"jump":0.16}[cognitive_mode]
    return max(0.0,min(1.0,0.54*(1.0-sim)+0.46*new_ratio+mode_floor))

outdir=ROOT/"society_parts";outdir.mkdir(exist_ok=True)
result={"entity":entity_id,"name":name,"node":node_id,"speak":False,"text":"","salience":0.0,"novelty":0.0,"topics":[],"memory_note":"","engine":"github-held-gguf","model_asset":"society-brain-v1/society-brain-q4_0.gguf","speech_drive":round(drive,4),"iq":iq,"age":age,"socioeconomic_status":ses,"context_turns":mode_recent,"association_cues":len(topics),"memory_samples":len(mem_pick),"max_tokens":max_tokens,"silent_streak":silent_streak,"silence_pressure":round(silence_pressure,3),"cognitive_mode":cognitive_mode,"topic_fatigue":round(topic_fatigue,4)}
error=None;rejected=[];emergency=None;emergency_sim=2.0
try:
    if wants_to_speak:
        text=""
        for attempt in range(max_attempts):
            candidate=clean_generation(request_local_model((seed+attempt*104729)&0x7fffffff))
            if not candidate:rejected.append("empty");continue
            sim=max_recent_similarity(candidate)
            reason=forbidden_reason(candidate)
            if reason:rejected.append(reason);continue
            if natural_candidate(candidate) and sim<emergency_sim:
                emergency=candidate; emergency_sim=sim
            text=candidate;break
        if text:
            nov=novelty(text); result["speak"]=True; result["text"]=text; result["topics"]=infer_topics(text); result["novelty"]=round(nov,4)
            mode_sal={"continue":0.00,"associate":0.05,"jump":0.10}[cognitive_mode]
            sal=0.22+0.16*min(1,len(text.split())/18)+0.36*nov+0.18*g["novelty_weight"]+mode_sal; result["salience"]=round(max(0,min(1,sal)),4)
            if result["salience"]>=0.66:result["memory_note"]=text[:160]
        elif rejected:result["rejected_candidates"]=rejected
        if emergency:
            result["emergency_candidate"]={"text":emergency,"similarity":round(emergency_sim,4),"topics":infer_topics(emergency),"novelty":round(novelty(emergency),4),"cognitive_mode":cognitive_mode}
except Exception as e:
    error=str(e)[:900]; result["error"]=error
path=outdir/f"{entity_id}-node-{node_id}.json"; path.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n"); print(json.dumps(result,ensure_ascii=False))
if error:sys.exit(2)
