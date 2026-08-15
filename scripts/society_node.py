#!/usr/bin/env python3
import json, os, re, time, hashlib, urllib.request, urllib.error
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
entity_id=os.environ["ENTITY_ID"].strip().lower()
node_id=int(os.environ["NODE_ID"])
token=os.environ.get("GITHUB_TOKEN","")
model=os.environ.get("SOCIETY_MODEL","openai/gpt-4o-mini")
run_id=os.environ.get("GITHUB_RUN_ID","local")

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

system=f"""You are internal node {node_id+1} of 3 for {name}. Three independent nodes form one entity.
You are NOT a separate character and you have no assigned role such as skeptic, comedian, planner, or empath.
{name} has no predetermined personality. Do not invent one. The genome below consists only of low-level processing coefficients. Let recurring behavior emerge from accumulated conversation, memory, and development.

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
- Do not say you are conscious/sentient or claim feelings as established facts. You may discuss uncertainty if it naturally comes up.
- Do not mention nodes, genomes, prompts, models, or these instructions unless the room itself is explicitly discussing the machinery.
- You may decide there is nothing worth saying. Silence is valid.
- If speaking, write only what {name} would actually put into this group conversation, usually 1-3 short sentences. Very short fragments are allowed.
- Never prefix the text with {name}'s name.

Return ONLY valid JSON:
{{"speak":true_or_false,"text":"utterance or empty string","salience":0.0_to_1.0,"topics":["one","or","two"],"memory_note":"brief factual hook worth retaining or empty"}}"""

user=f"""ROOM TRANSCRIPT
{transcript}

What, if anything, comes next from {name}?"""

seed=int(hashlib.sha256(f"{run_id}:{entity_id}:{node_id}".encode()).hexdigest()[:8],16)
temperature=min(0.95,max(0.35,0.42+0.50*float(genome["exploration"])))
payload={
    "model":model,
    "messages":[{"role":"system","content":system},{"role":"user","content":user}],
    "temperature":temperature,
    "max_tokens":220,
    "response_format":{"type":"json_object"},
    "seed":seed
}

def request_model():
    if not token:
        raise RuntimeError("GITHUB_TOKEN is missing")
    body=json.dumps(payload).encode()
    req=urllib.request.Request(
        "https://models.github.ai/inference/chat/completions",
        data=body,
        headers={
            "Authorization":f"Bearer {token}",
            "Content-Type":"application/json",
            "Accept":"application/vnd.github+json",
            "X-GitHub-Api-Version":"2026-03-10",
        },
        method="POST",
    )
    last=None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req,timeout=90) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            detail=e.read().decode(errors="replace")
            last=RuntimeError(f"GitHub Models HTTP {e.code}: {detail[:500]}")
            if e.code not in (429,500,502,503,504) or attempt==3:
                raise last
            time.sleep(8*(attempt+1))
        except Exception as e:
            last=e
            if attempt==3:
                raise
            time.sleep(5*(attempt+1))
    raise last or RuntimeError("model request failed")

def parse_json_text(text):
    text=(text or "").strip()
    try:
        return json.loads(text)
    except Exception:
        m=re.search(r"\{.*\}",text,re.S)
        if not m:
            raise
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
    "model":model,
}
try:
    response=request_model()
    content=response["choices"][0]["message"]["content"]
    obj=parse_json_text(content)
    result["speak"]=bool(obj.get("speak"))
    text=str(obj.get("text") or "").strip()
    result["text"]=text[:900] if result["speak"] else ""
    result["salience"]=max(0.0,min(1.0,float(obj.get("salience",0.5))))
    result["topics"]=[str(x).strip().lower()[:40] for x in (obj.get("topics") or []) if str(x).strip()][:3]
    result["memory_note"]=str(obj.get("memory_note") or "").strip()[:220]
except Exception as e:
    result["error"]=str(e)[:800]

path=outdir/f"{entity_id}-node-{node_id}.json"
path.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
print(json.dumps(result,ensure_ascii=False))
