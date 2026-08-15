#!/usr/bin/env python3
import json, os, re, hashlib, subprocess, sys, random
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
entity_id=os.environ["ENTITY_ID"].strip().lower()
node_id=int(os.environ["NODE_ID"])
run_id=os.environ.get("GITHUB_RUN_ID","local")
model_path=Path(os.environ.get("SOCIETY_MODEL_PATH", ROOT/"society_model/society-brain-q4_0.gguf"))
llama_cli=Path(os.environ.get("LLAMA_CLI", ROOT/"runtime/llama-cli"))

minds=json.loads((ROOT/"society/minds.json").read_text())
conversation=json.loads((ROOT/"society/conversation.json").read_text())
entity=minds["entities"][entity_id]
name=entity["name"]
g=entity["genome"]
d=entity.get("development",{})
memory=entity.get("memory",[])
names={k:v["name"] for k,v in minds["entities"].items()}

recent=conversation[-16:]
transcript="\n".join(f'{names.get(m.get("speaker"),m.get("speaker","?"))}: {m.get("text","")}' for m in recent) if recent else "(Nobody has spoken here yet.)"
topics=sorted((d.get("topic_weights") or {}).items(),key=lambda kv:kv[1],reverse=True)[:6]
topic_text=", ".join(k for k,_ in topics) or "none yet"
memory_text="\n".join(f"- {m.get('text','')}" for m in memory[-5:]) or "none yet"

seed=int(hashlib.sha256(f"{run_id}:{entity_id}:{node_id}".encode()).hexdigest()[:8],16)&0x7fffffff
rng=random.Random(seed)
activation=float(d.get("recent_activation",0.5) or 0.5)

# Genes act underneath language. They alter whether this node speaks and how
# exploratory its sampling is; they are not translated into personality labels.
drive=(0.53 + 0.22*g["spontaneous_initiation"] - 0.20*g["inhibition"] + 0.08*activation)
if recent:
    drive += 0.10*g["social_salience"] + 0.05*g["attention_persistence"]
drive=max(0.18,min(0.90,drive))
wants_to_speak=rng.random()<drive
temperature=max(0.38,min(1.02,0.43+0.50*g["exploration"]+0.06*g["association_spread"]))

system_prompt=f"""You contribute one possible next utterance for {name}, a continuing participant in a shared room.
{name} has no assigned personality. Let style emerge only from prior conversation, retained experience, and repeated development.
Speak like an ordinary participant, not an assistant. Keep it natural and usually brief. Fragments, uncertainty, ordinary remarks, and imperfect phrasing are fine. Do not force humor, profundity, warmth, disagreement, questions, or cleverness. Do not discuss hidden machinery unless the room is already discussing it. Output only what {name} says, with no name label or explanation.

Recurring associations: {topic_text}
Retained experience:
{memory_text}"""
user_prompt=f"""Recent room:\n{transcript}\n\nWhat does {name} say next?"""
full_prompt=(f"<|im_start|>system\n{system_prompt}<|im_end|>\n"
             f"<|im_start|>user\n{user_prompt}<|im_end|>\n"
             f"<|im_start|>assistant\n")

def request_local_model():
    if not model_path.is_file(): raise RuntimeError(f"GitHub-held model missing: {model_path}")
    if not llama_cli.is_file(): raise RuntimeError(f"GitHub-held runtime missing: {llama_cli}")
    cmd=[str(llama_cli),"-m",str(model_path),"-p",full_prompt,"-no-cnv",
         "-n","48","-c","2048","-t","4","--no-warmup",
         "--temp",f"{temperature:.3f}","--top-p","0.92","-s",str(seed),
         "--no-display-prompt","--no-show-timings","-co","off"]
    proc=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=150)
    if proc.returncode!=0:
        detail=(proc.stderr or proc.stdout or "llama-cli failed").strip()
        raise RuntimeError(f"local inference exit {proc.returncode}: {detail[-1000:]}")
    return (proc.stdout or "").strip()

def clean_generation(raw):
    text=(raw or "").replace("\r","")
    text=re.sub(r"\x1b\[[0-9;?]*[A-Za-z]","",text)
    if "<|im_start|>assistant" in text:
        text=text.rsplit("<|im_start|>assistant",1)[-1]
    text=text.replace("<|im_end|>","").strip()
    kept=[]
    skip=("Loading model","build      :","model      :","ftype      :","modalities :","llama_","ggml_","main:")
    for line in text.splitlines():
        s=line.strip()
        if not s or s.startswith(skip) or s in {"Exiting...","available commands:"}: continue
        if set(s)<=set("▄█▀ "): continue
        kept.append(s)
    text=" ".join(kept).strip()
    text=re.sub(rf"^(?:assistant\s*[:>-]?\s*|{re.escape(name)}\s*[:>-]\s*)","",text,flags=re.I).strip()
    # Keep conversational scale even if the model rambles.
    if len(text)>420:
        text=text[:420].rsplit(" ",1)[0].rstrip()+"…"
    return text

STOP={"that","this","with","from","have","just","what","when","where","there","they","them","then","than","your","about","would","could","should","into","only","really","some","more","very","like","because","been","being","does","will","well","yeah","okay","also","still","room"}
def infer_topics(text):
    out=[]
    for w in re.findall(r"[A-Za-z][A-Za-z'-]{3,}",(text or "").lower()):
        w=w.strip("'-")
        if w and w not in STOP and w not in out: out.append(w)
        if len(out)>=3: break
    return out

def novelty(text):
    a=set(re.findall(r"[a-z0-9']+",text.lower()))
    b=set(re.findall(r"[a-z0-9']+"," ".join(m.get("text","") for m in recent[-6:]).lower()))
    return len(a-b)/len(a) if a else 0.0

outdir=ROOT/"society_parts"; outdir.mkdir(exist_ok=True)
result={"entity":entity_id,"name":name,"node":node_id,"speak":False,"text":"","salience":0.0,
        "topics":[],"memory_note":"","engine":"github-held-gguf",
        "model_asset":"society-brain-v1/society-brain-q4_0.gguf","speech_drive":round(drive,4)}
error=None; raw=""
try:
    if wants_to_speak:
        raw=request_local_model(); text=clean_generation(raw)
        if not text: raise RuntimeError("local model returned no usable utterance")
        result["speak"]=True; result["text"]=text; result["topics"]=infer_topics(text)
        sal=0.27+0.22*min(1,len(text.split())/20)+0.32*novelty(text)+0.19*g["novelty_weight"]
        result["salience"]=round(max(0,min(1,sal)),4)
        if result["salience"]>=0.64: result["memory_note"]=text[:180]
except Exception as e:
    error=str(e)[:1000]; result["error"]=error
    if raw: result["raw_response"]=raw[:1000]

path=outdir/f"{entity_id}-node-{node_id}.json"
path.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
print(json.dumps(result,ensure_ascii=False))
if error: sys.exit(2)
