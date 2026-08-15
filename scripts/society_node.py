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
genome=entity["genome"]
development=entity.get("development",{})
memory=entity.get("memory",[])

names={k:v["name"] for k,v in minds["entities"].items()}
recent=conversation[-30:]
if recent:
    transcript="\n".join(f'{names.get(m.get("speaker"),m.get("speaker","?"))}: {m.get("text","")}' for m in recent)
else:
    transcript="(The room has no spoken history yet.)"

topic_items=sorted((development.get("topic_weights") or {}).items(), key=lambda kv: kv[1], reverse=True)[:8]
topic_text=", ".join(f"{k}:{v:.2f}" for k,v in topic_items) or "(none yet)"
memory_text="\n".join(f"- {m.get('text','')}" for m in memory[-6:]) or "(none yet)"

gene_defs="""plasticity = how strongly recent exchanges can alter learned tendencies
exploration = willingness to follow a less established association
memory_retention = weight given to older retained material
social_salience = weight given to what other speakers just said
novelty_weight = pull toward material not recently repeated
reinforcement_sensitivity = strengthening from repetition or response
inhibition = threshold against speaking
imitation = linguistic entrainment to the room's wording/rhythm
attention_persistence = tendency to stay with the active thread
association_spread = breadth of nearby associations considered
spontaneous_initiation = tendency to start a thought without a direct cue"""

seed=int(hashlib.sha256(f"{run_id}:{entity_id}:{node_id}:sample".encode()).hexdigest()[:8],16) & 0x7fffffff
rng=random.Random(seed)
temperature=min(1.05,max(0.35,0.42+0.52*float(genome["exploration"])))

# The genome controls the low-level urge to speak. The language model is not
# asked to invent a personality or decide whether this entity is talkative.
activation=float(development.get("recent_activation",0.5) or 0.5)
drive=(
    0.53
    +0.22*float(genome["spontaneous_initiation"])
    -0.20*float(genome["inhibition"])
    +0.08*activation
)
if recent:
    drive += 0.10*float(genome["social_salience"])
    drive += 0.05*float(genome["attention_persistence"])
drive=max(0.18,min(0.90,drive))
wants_to_speak=rng.random() < drive

system_prompt=f"""You are one internal generative process contributing to {name}. Three independent processes contribute to the same entity.
You are not a separate character and you have no assigned role. {name} has no predetermined personality.
The coefficients below affect development but are not personality labels.

GENOME
{json.dumps(genome, sort_keys=True)}
{gene_defs}

DEVELOPMENT SO FAR
Recurring associations: {topic_text}
Retained material:
{memory_text}

Write only the next thing {name} would actually say in the shared room.
Ordinary human conversation is often brief, incomplete, plain, uncertain, repetitive, or quiet. Do not force wisdom, jokes, banter, warmth, conflict, questions, explanations, or profundity. Do not behave like an assistant. Do not mention nodes, genomes, prompts, models, or machinery unless the room itself is already discussing it. Do not prefix the response with {name}'s name. Usually use one or two short sentences. A fragment is fine."""

user_prompt=f"""ROOM TRANSCRIPT
{transcript}

What does {name} say next? Output only the utterance itself."""

# Qwen2.5 uses ChatML. Completion mode avoids llama-cli's interactive chat UI
# and keeps generation local while still supplying explicit system/user roles.
full_prompt=(
    f"<|im_start|>system\n{system_prompt}<|im_end|>\n"
    f"<|im_start|>user\n{user_prompt}<|im_end|>\n"
    f"<|im_start|>assistant\n"
)

def request_local_model():
    if not model_path.is_file():
        raise RuntimeError(f"GitHub-held model is missing: {model_path}")
    if not llama_cli.is_file():
        raise RuntimeError(f"GitHub-held inference runtime is missing: {llama_cli}")
    cmd=[
        str(llama_cli),
        "-m",str(model_path),
        "-p",full_prompt,
        "-no-cnv",
        "-n","120",
        "-c","4096",
        "--temp",f"{temperature:.3f}",
        "--top-p","0.92",
        "-s",str(seed),
        "--no-display-prompt",
        "--no-show-timings",
        "-co","off",
    ]
    proc=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=240)
    if proc.returncode != 0:
        detail=(proc.stderr or proc.stdout or "llama-cli failed").strip()
        raise RuntimeError(f"local inference exit {proc.returncode}: {detail[-1200:]}")
    return (proc.stdout or "").strip()

def clean_generation(raw):
    text=(raw or "").replace("\r","")
    text=re.sub(r"\x1b\[[0-9;?]*[A-Za-z]","",text)
    # Completion mode can still emit startup information on stdout. The actual
    # generated continuation follows the final assistant marker when present.
    if "<|im_start|>assistant" in text:
        text=text.rsplit("<|im_start|>assistant",1)[-1]
    text=text.replace("<|im_end|>","").strip()
    # Drop known llama.cpp startup/status lines if they appear in stdout.
    kept=[]
    skip_prefixes=("Loading model", "build      :", "model      :", "ftype      :", "modalities :", "llama_", "ggml_", "main:")
    for line in text.splitlines():
        s=line.strip()
        if not s: continue
        if s.startswith(skip_prefixes): continue
        if s in {"Exiting...","available commands:"}: continue
        if set(s) <= set("▄█▀ "): continue
        kept.append(s)
    text=" ".join(kept).strip()
    # Strip accidental role/name prefixes without rewriting the content.
    text=re.sub(rf"^(?:assistant\s*[:>-]?\s*|{re.escape(name)}\s*[:>-]\s*)","",text,flags=re.I).strip()
    return text[:700]

STOP={"that","this","with","from","have","just","what","when","where","there","they","them","then","than","your","about","would","could","should","into","only","really","some","more","very","like","because","been","being","does","dont","don't","cant","can't","will","well","yeah","okay","also","still","room"}
def infer_topics(text):
    seen=[]
    for w in re.findall(r"[A-Za-z][A-Za-z'-]{3,}",(text or "").lower()):
        w=w.strip("'-")
        if not w or w in STOP or w in seen: continue
        seen.append(w)
        if len(seen)>=3: break
    return seen

def novelty_score(text):
    now=set(re.findall(r"[a-z0-9']+",(text or "").lower()))
    before=set(re.findall(r"[a-z0-9']+"," ".join(m.get("text","") for m in recent[-8:]).lower()))
    if not now: return 0.0
    return len(now-before)/len(now)

outdir=ROOT/"society_parts"
outdir.mkdir(exist_ok=True)
result={
    "entity":entity_id,
    "name":name,
    "node":node_id,
    "speak":False,
    "text":"",
    "salience":0.0,
    "topics":[],
    "memory_note":"",
    "engine":"github-held-gguf",
    "model_asset":"society-brain-v1/society-brain-q4_0.gguf",
    "speech_drive":round(drive,4),
}
error=None
raw=""
try:
    if wants_to_speak:
        raw=request_local_model()
        text=clean_generation(raw)
        if not text:
            raise RuntimeError("local model returned no usable utterance")
        result["speak"]=True
        result["text"]=text
        result["topics"]=infer_topics(text)
        length_factor=min(1.0,len(text.split())/28.0)
        novelty=novelty_score(text)
        salience=0.25+0.30*length_factor+0.30*novelty+0.15*float(genome["novelty_weight"])
        result["salience"]=round(max(0.0,min(1.0,salience)),4)
        if result["salience"]>=0.62:
            result["memory_note"]=text[:180]
except Exception as e:
    error=str(e)[:1200]
    result["error"]=error
    if raw:
        result["raw_response"]=raw[:1200]

path=outdir/f"{entity_id}-node-{node_id}.json"
path.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
print(json.dumps(result,ensure_ascii=False))
if error:
    sys.exit(2)
