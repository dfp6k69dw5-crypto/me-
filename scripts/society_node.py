#!/usr/bin/env python3
import json, os, re, hashlib, subprocess, sys, random
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
entity_id=os.environ["ENTITY_ID"].strip().lower()
node_id=int(os.environ["NODE_ID"])
run_id=os.environ.get("GITHUB_RUN_ID","local")
model_path=Path(os.environ.get("SOCIETY_MODEL_PATH", ROOT/"society_model/society-brain-q4_0.gguf"))
completion_bin=Path(os.environ.get("LLAMA_COMPLETION", ROOT/"runtime/llama-completion"))

minds=json.loads((ROOT/"society/minds.json").read_text())
conversation=json.loads((ROOT/"society/conversation.json").read_text())
entity=minds["entities"][entity_id]
name=entity["name"]
g=entity["genome"]
d=entity.get("development",{})
memory=entity.get("memory",[])
names={k:v["name"] for k,v in minds["entities"].items()}
peer_names=", ".join(v["name"] for k,v in minds["entities"].items() if k!=entity_id)

recent=conversation[-8:]
transcript="\n".join(f'{names.get(m.get("speaker"),m.get("speaker","?"))}: {m.get("text","")}' for m in recent) if recent else "(No one has spoken yet.)"
topics=sorted((d.get("topic_weights") or {}).items(),key=lambda kv:kv[1],reverse=True)[:4]
topic_text=", ".join(k for k,_ in topics) or "none yet"
memory_text="\n".join(f"- {m.get('text','')[:180]}" for m in memory[-3:]) or "none yet"

seed=int(hashlib.sha256(f"{run_id}:{entity_id}:{node_id}".encode()).hexdigest()[:8],16)&0x7fffffff
rng=random.Random(seed)
activation=float(d.get("recent_activation",0.5) or 0.5)

# Genes act underneath language. They affect the urge to speak and sampling,
# but are never translated into a named personality or assigned social role.
drive=0.53+0.22*g["spontaneous_initiation"]-0.20*g["inhibition"]+0.08*activation
if recent: drive+=0.10*g["social_salience"]+0.05*g["attention_persistence"]
drive=max(0.18,min(0.90,drive))
wants_to_speak=rng.random()<drive
temperature=max(0.38,min(1.02,0.43+0.50*g["exploration"]+0.06*g["association_spread"]))

system_prompt=f"""You contribute one possible next utterance for {name}, a continuing participant in a shared room with {peer_names}. They already coexist here; there is no visitor, customer, patient, or user to serve. {name} has no assigned personality. Let style emerge only from shared history and retained experience.

Speak like an ordinary peer, not an assistant, host, interviewer, therapist, teacher, or narrator. Be natural and usually brief. Fragments, pauses, uncertainty, mundane observations, and unfinished thoughts are fine. Do not automatically greet, offer help, ask why someone is here, ask what you can do for them, or ask for a topic. Do not force humor, wisdom, warmth, conflict, questions, cleverness, or profundity. Do not describe what {name} "says next." Output only the actual utterance, with no name label or quotation marks.

Recurring associations: {topic_text}
Retained experience:
{memory_text}"""
user_prompt=f"""Recent room:
{transcript}

If {name} has something to say to the others now, what is it? Output only the utterance."""

def request_local_model():
    if not model_path.is_file(): raise RuntimeError(f"GitHub-held model missing: {model_path}")
    if not completion_bin.is_file(): raise RuntimeError(f"GitHub-held completion runtime missing: {completion_bin}")
    cmd=[str(completion_bin),"-m",str(model_path),"--jinja","--single-turn",
         "-sys",system_prompt,"-p",user_prompt,
         "-n","24","-c","1024","-t","4","--no-warmup",
         "--temp",f"{temperature:.3f}","--top-p","0.92","-s",str(seed),
         "--simple-io","--no-display-prompt","--log-verbosity","0"]
    proc=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=90)
    if proc.returncode!=0:
        detail=(proc.stderr or proc.stdout or "llama-completion failed").strip()
        raise RuntimeError(f"local inference exit {proc.returncode}: {detail[-900:]}")
    return (proc.stdout or proc.stderr or "").strip()

def clean_generation(raw):
    text=(raw or "").replace("\r","")
    text=re.sub(r"\x1b\[[0-9;?]*[A-Za-z]","",text)
    for marker in ("<|im_end|>","<|eot_id|>","<|end_of_text|>","[end of text]","[end of sentence]"):
        if marker.lower() in text.lower():
            text=re.split(re.escape(marker),text,flags=re.I,maxsplit=1)[0]
    text=text.strip()
    # Small models sometimes echo an instruction-like wrapper. Remove only the
    # wrapper, not the substance of the utterance.
    text=re.sub(rf"^(?:assistant\s*[:>-]?\s*|{re.escape(name)}\s+(?:says|said)(?:\s+next)?\s*:\s*|{re.escape(name)}\s*[:>-]\s*)","",text,flags=re.I).strip()
    if len(text)>=2 and text[0]==text[-1] and text[0] in {'\"',"'"}:
        text=text[1:-1].strip()
    if len(text)>260: text=text[:260].rsplit(" ",1)[0].rstrip()+"…"
    return text

STOP={"that","this","with","from","have","just","what","when","where","there","they","them","then","than","your","about","would","could","should","into","only","really","some","more","very","like","because","been","being","does","will","well","yeah","okay","also","still","room","says","said","next"}
def infer_topics(text):
    out=[]
    for w in re.findall(r"[A-Za-z][A-Za-z'-]{3,}",(text or "").lower()):
        w=w.strip("'-")
        if w and w not in STOP and w not in out: out.append(w)
        if len(out)>=3: break
    return out

def novelty(text):
    a=set(re.findall(r"[a-z0-9']+",text.lower())); b=set(re.findall(r"[a-z0-9']+"," ".join(m.get("text","") for m in recent).lower()))
    return len(a-b)/len(a) if a else 0.0

outdir=ROOT/"society_parts"; outdir.mkdir(exist_ok=True)
result={"entity":entity_id,"name":name,"node":node_id,"speak":False,"text":"","salience":0.0,"topics":[],"memory_note":"",
        "engine":"github-held-gguf","model_asset":"society-brain-v1/society-brain-q4_0.gguf","speech_drive":round(drive,4)}
error=None; raw=""
try:
    if wants_to_speak:
        raw=request_local_model(); text=clean_generation(raw)
        if not text: raise RuntimeError("local model returned no usable utterance")
        result["speak"]=True; result["text"]=text; result["topics"]=infer_topics(text)
        sal=0.27+0.22*min(1,len(text.split())/18)+0.32*novelty(text)+0.19*g["novelty_weight"]
        result["salience"]=round(max(0,min(1,sal)),4)
        if result["salience"]>=0.64: result["memory_note"]=text[:160]
except Exception as e:
    error=str(e)[:900]; result["error"]=error
    if raw: result["raw_response"]=raw[:900]
path=outdir/f"{entity_id}-node-{node_id}.json"
path.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
print(json.dumps(result,ensure_ascii=False))
if error: sys.exit(2)
