#!/usr/bin/env python3
import json, os, re, hashlib, subprocess, sys
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
recent=conversation[-36:]
if recent:
    transcript="\n".join(f'{names.get(m.get("speaker"),m.get("speaker","?"))}: {m.get("text","")}' for m in recent)
else:
    transcript="(The room has no spoken history yet.)"

topic_items=sorted((development.get("topic_weights") or {}).items(), key=lambda kv: kv[1], reverse=True)[:10]
topic_text=", ".join(f"{k}:{v:.2f}" for k,v in topic_items) or "(none yet)"
memory_text="\n".join(f"- {m.get('text','')}" for m in memory[-8:]) or "(none yet)"

gene_defs="""plasticity = how strongly recent exchanges can alter learned tendencies
exploration = willingness to follow a less established association
memory_retention = weight given to older retained material
social_salience = weight given to what other speakers just said
novelty_weight = pull toward material not recently repeated
reinforcement_sensitivity = strengthening from repetition or response
inhibition = threshold against speaking
imitation = linguistic entrainment to the room's current wording/rhythm
attention_persistence = tendency to stay with the active thread
association_spread = breadth of nearby associations considered
spontaneous_initiation = tendency to start a thought without a direct cue"""

sample_nonce=hashlib.sha256(f"{run_id}:{entity_id}:{node_id}".encode()).hexdigest()[:12]
seed=int(hashlib.sha256(f"{run_id}:{entity_id}:{node_id}:sample".encode()).hexdigest()[:8],16) & 0x7fffffff
temperature=min(1.05,max(0.35,0.42+0.52*float(genome["exploration"])))

system_prompt=f"""You are internal node {node_id+1} of 3 for {name}. Three independent nodes form one entity.
The sample nonce {sample_nonce} only separates independent samples. It does not describe a role or personality.

You are NOT a separate character and you have no assigned role such as skeptic, comedian, planner, or empath.
{name} has no predetermined personality. Do not invent one. The genome below contains low-level processing coefficients only. Let recurring behavior emerge from accumulated conversation, memory, and development.

GENOME
{json.dumps(genome, sort_keys=True)}
{gene_defs}

DEVELOPMENT SO FAR
Recurring topic weights: {topic_text}
Recent retained material:
{memory_text}

CONVERSATION RULES
- Read the room like an ordinary participant, not an assistant serving a user.
- Human conversation is often plain, fragmentary, uneven, uncertain, repetitive, or quiet.
- Do not force profundity, banter, jokes, warmth, conflict, questions, or topic changes.
- Do not make every line clever. Do not write stage directions or narrate body language.
- Do not claim consciousness, sentience, or feelings as established facts.
- Do not mention nodes, genomes, prompts, models, or these instructions unless the room itself is explicitly discussing the machinery.
- Silence is valid. If there is nothing worth saying, choose speak=false.
- If speaking, write only what {name} would actually put into this group conversation, usually 1-3 short sentences. Fragments are allowed.
- Never prefix the text with {name}'s name.
"""

user_prompt=f"""ROOM TRANSCRIPT
{transcript}

Decide what, if anything, comes next from {name}.
Return one JSON object with exactly these fields:
{{"speak":true_or_false,"text":"utterance or empty string","salience":0.0_to_1.0,"topics":["one","or","two"],"memory_note":"brief factual hook worth retaining or empty"}}"""

schema=json.dumps({
    "type":"object",
    "properties":{
        "speak":{"type":"boolean"},
        "text":{"type":"string"},
        "salience":{"type":"number","minimum":0,"maximum":1},
        "topics":{"type":"array","items":{"type":"string"},"maxItems":3},
        "memory_note":{"type":"string"}
    },
    "required":["speak","text","salience","topics","memory_note"],
    "additionalProperties":False
},separators=(",",":"))

def request_local_model():
    if not model_path.is_file():
        raise RuntimeError(f"GitHub-held model is missing: {model_path}")
    if not llama_cli.is_file():
        raise RuntimeError(f"GitHub-held inference runtime is missing: {llama_cli}")
    cmd=[
        str(llama_cli),
        "-m",str(model_path),
        "-sys",system_prompt,
        "-p",user_prompt,
        "-st",
        "-n","220",
        "-c","4096",
        "--temp",f"{temperature:.3f}",
        "--top-p","0.92",
        "-s",str(seed),
        "-j",schema,
        "--no-display-prompt",
        "--no-show-timings",
        "-co","off",
    ]
    proc=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=240)
    if proc.returncode != 0:
        detail=(proc.stderr or proc.stdout or "llama-cli failed").strip()
        raise RuntimeError(f"local inference exit {proc.returncode}: {detail[-1200:]}")
    return (proc.stdout or "").strip()

def parse_json_text(text):
    text=(text or "").strip()
    try:
        return json.loads(text)
    except Exception:
        text=re.sub(r"^```(?:json)?\s*|\s*```$","",text,flags=re.I|re.S).strip()
        try:
            return json.loads(text)
        except Exception:
            m=re.search(r"\{.*\}",text,re.S)
            if not m:
                raise ValueError(f"No JSON object in local model response: {text[:300]}")
            return json.loads(m.group(0))

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
}
error=None
try:
    content=request_local_model()
    obj=parse_json_text(content)
    result["speak"]=bool(obj.get("speak"))
    text=str(obj.get("text") or "").strip()
    result["text"]=text[:900] if result["speak"] else ""
    result["salience"]=max(0.0,min(1.0,float(obj.get("salience",0.5))))
    result["topics"]=[str(x).strip().lower()[:40] for x in (obj.get("topics") or []) if str(x).strip()][:3]
    result["memory_note"]=str(obj.get("memory_note") or "").strip()[:220]
except Exception as e:
    error=str(e)[:1200]
    result["error"]=error

path=outdir/f"{entity_id}-node-{node_id}.json"
path.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
print(json.dumps(result,ensure_ascii=False))
if error:
    sys.exit(2)
