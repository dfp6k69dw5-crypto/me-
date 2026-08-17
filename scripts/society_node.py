#!/usr/bin/env python3
import hashlib
import json
import os
import random
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
entity_id = os.environ["ENTITY_ID"].strip().lower()
node_id = int(os.environ["NODE_ID"])
run_id = os.environ.get("GITHUB_RUN_ID", "local")
model_path = Path(os.environ.get("SOCIETY_MODEL_PATH", ROOT / "society_model/society-brain-q4_0.gguf"))
completion_bin = Path(os.environ.get("LLAMA_COMPLETION", ROOT / "runtime/llama-completion"))

minds = json.loads((ROOT / "society/minds.json").read_text())
conversation = json.loads((ROOT / "society/conversation.json").read_text())
state_path = ROOT / "society/state.json"
state = json.loads(state_path.read_text()) if state_path.is_file() else {}
entity = minds["entities"][entity_id]
name = entity["name"]
g = entity["genome"]
d = entity.get("development", {})
names = {k: v["name"] for k, v in minds["entities"].items()}
peer_names = ", ".join(v for k, v in names.items() if k != entity_id)

# This marks the clean cognitive epoch. The old transcript remains visible, but old
# task/team/study-era speech no longer feeds generation or associative memory.
ROOM_REBUILD_EPOCH = "2026-08-17T01:20:00Z"

cognition_path = ROOT / "society/cognition.json"
cognition = json.loads(cognition_path.read_text()) if cognition_path.is_file() else {"entities": {}}
iq = int((cognition.get("entities", {}).get(entity_id, {}) or {}).get("iq", 100))
iq = max(100, min(136, iq))
iq_scale = (iq - 100) / 36.0

profiles_path = ROOT / "society/human_profiles.json"
profiles = json.loads(profiles_path.read_text()) if profiles_path.is_file() else {"entities": {}}
profile = (profiles.get("entities", {}).get(entity_id, {}) or {})
age = max(25, min(35, int(profile.get("age", 30))))
ses = str(profile.get("socioeconomic_status", "middle income"))
resource_context = str(profile.get("resource_context", "")).strip()
human_context = (
    f"{name} is {age} years old. Socioeconomic context: {ses}. {resource_context} "
    "These are background conditions, not personality traits. Do not infer intelligence, "
    "morality, taste, values, or temperament from socioeconomic status."
)

seed = int(hashlib.sha256(f"{run_id}:{entity_id}:{node_id}".encode()).hexdigest()[:8], 16) & 0x7FFFFFFF
rng = random.Random(seed)

STOP = {
    "that", "this", "with", "from", "have", "has", "had", "just", "what", "when", "where",
    "there", "they", "them", "then", "than", "your", "yours", "about", "would", "could",
    "should", "into", "only", "really", "some", "more", "very", "like", "because", "been",
    "being", "does", "doing", "done", "will", "well", "yeah", "okay", "also", "still",
    "says", "said", "next", "lets", "let's", "dont", "don't", "cant", "can't", "im", "i'm",
    "ive", "i've", "weve", "we've", "were", "we're", "youre", "you're", "thats", "that's",
    "its", "it's", "maybe", "kind", "sort", "thing", "things", "something", "anything",
    "someone", "everyone", "say", "saying", "think", "thinking", "thought", "know", "knowing",
    "mean", "means", "seem", "seems", "want", "wants", "wanted", "make", "making", "made",
    "start", "starting", "started", "try", "trying", "tried", "good", "great", "nice", "sure",
    "right", "actually", "probably", "pretty", "little", "much", "many", "few", "around", "again",
    "already", "even", "ever", "never", "always", "often", "sometimes", "today", "tonight",
    "tomorrow", "yesterday", "different", "together", "fresh", "interesting", "how's", "going",
    "everything", "current", "pick", "picking", "choose", "choosing", "choice", "choices",
}
NAME_WORDS = {w.lower() for person_name in names.values() for w in re.findall(r"[A-Za-z]+", person_name)}
META_WORDS = {
    "room", "stranger", "strangers", "peer", "peers", "conversation", "talk", "talking", "topic",
    "topics", "activity", "activities", "team", "group", "project", "projects", "study", "studying",
    "homework", "schedule", "schedules", "task", "tasks", "planning", "plan", "organize", "organizing",
    "brainstorm", "brainstorming", "assistant", "assistance", "help", "meeting", "session", "sessions",
    "subject", "subjects", "spark", "prompt", "cognitive", "jump", "associate", "continue",
}

SERVICE_PATTERNS = [
    r"\bhow can i help\b", r"\bhow may i help\b", r"\bwhat can i do for you\b", r"\bhow can i assist\b",
    r"\bdo you need (?:anything|help)\b", r"\bwhat do you need\b", r"\bhere to help\b",
]
FACILITATOR_PATTERNS = [
    r"\bwhat (?:would|do) you like to (?:talk about|discuss|explore|do)\b",
    r"\bwhat do we want to do\b", r"\bwhat should we do\b",
    r"\b(?:pick|choose|find|come up with)\s+(?:a\s+)?(?:good\s+|new\s+|different\s+)?topic\b",
    r"\bwhat (?:specific )?topic\b", r"\bcurrent (?:activity|topic)\b",
]
ROLE_PATTERNS = [
    r"\bteam members?\b", r"\b(?:the|our|this) team\b", r"\bgather input\b",
    r"\bbrainstorming session\b", r"\bstudy schedule\b", r"\bstudy session\b", r"\bnext step\b",
]
FUTURE_SHARED_PATTERNS = [
    r"\bwe(?:'ll| will)\s+(?:meet|meet up|get together|see each other|hang out)\b",
    r"\b(?:our|the)\s+next\s+(?:meeting|session|get-together)\b",
    r"\bsee you\s+(?:next|again|later)\b",
]
META_PATTERNS = [
    r"\boutput only\b", r"\brecent room speech\b", r"\bpersistent adult background\b",
    r"\bcognitive move\b", r"\bselected earlier memories\b", r"\bprivate spontaneous\b",
]
speaker_label_re = re.compile(
    r"(?im)(?:^|\n)\s*(?:" + "|".join(re.escape(v) for v in names.values()) + r")\s*:"
)


def tokens(text):
    return set(re.findall(r"[a-z0-9']+", str(text or "").lower()))


def content_tokens(text):
    out = []
    for word in re.findall(r"[A-Za-z][A-Za-z'-]{3,}", str(text or "").lower()):
        word = word.strip("'-")
        if not word or word in STOP or word in NAME_WORDS:
            continue
        out.append(word)
    return out


def jac(a, b):
    aa, bb = tokens(a), tokens(b)
    if not aa and not bb:
        return 1.0
    if not aa or not bb:
        return 0.0
    return len(aa & bb) / len(aa | bb)


def clean_generation(raw, cap=420):
    text = str(raw or "").replace("\r", "")
    text = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", text)
    for marker in ("<|im_end|>", "<|eot_id|>", "<|end_of_text|>", "[end of text]", "[end of sentence]"):
        if marker.lower() in text.lower():
            text = re.split(re.escape(marker), text, flags=re.I, maxsplit=1)[0]
    text = text.strip()
    text = re.sub(
        rf"^(?:assistant\s*[:>-]?\s*|{re.escape(name)}\s+(?:says|said)(?:\s+next)?\s*:\s*|{re.escape(name)}\s*[:>-]\s*)",
        "", text, flags=re.I,
    ).strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'\"', "'"}:
        text = text[1:-1].strip()
    if len(text) > cap:
        text = text[:cap].rsplit(" ", 1)[0].rstrip() + "…"
    return text


def run_local(system_text, prompt_text, local_seed, n_tokens, temp):
    if not model_path.is_file():
        raise RuntimeError(f"GitHub-held model missing: {model_path}")
    if not completion_bin.is_file():
        raise RuntimeError(f"GitHub-held completion runtime missing: {completion_bin}")
    context_tokens = 1280 + int(round(768 * iq_scale))
    top_p = min(0.995, 0.93 + 0.045 * g["exploration"] + 0.025 * silence_pressure)
    cmd = [
        str(completion_bin), "-m", str(model_path), "--jinja", "--single-turn", "-sys", system_text,
        "-p", prompt_text, "-n", str(n_tokens), "-c", str(context_tokens), "-t", "4", "--no-warmup",
        "--temp", f"{temp:.3f}", "--top-p", f"{top_p:.3f}", "-s", str(local_seed), "--simple-io",
        "--no-display-prompt", "--log-verbosity", "0",
    ]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=90)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "llama-completion failed").strip()
        raise RuntimeError(f"local inference exit {proc.returncode}: {detail[-900:]}")
    return (proc.stdout or proc.stderr or "").strip()


# Only rebuilt-era speech is allowed to shape the new conversational trajectory.
clean_history = [m for m in conversation if str(m.get("at", "")) >= ROOM_REBUILD_EPOCH]
recent_window = clean_history[-12:]
recent_content = [set(content_tokens(m.get("text", ""))) for m in recent_window]
flat = [w for row in recent_content for w in row]
counts = Counter(flat)
repeated = sum(c - 1 for c in counts.values() if c > 1)
topic_fatigue = max(0.0, min(1.0, repeated / max(4.0, len(recent_window) * 1.7))) if flat else 0.0
rut_words = {w for w, c in counts.most_common(12) if c >= 2}

# Rebuilt-era own memories are the only associative cues. Old learned weights are ignored.
clean_memories = [m for m in (entity.get("memory", []) or []) if str(m.get("at", "")) >= ROOM_REBUILD_EPOCH]
association_pool = []
for memory in clean_memories:
    for t in memory.get("topics") or []:
        t = str(t).lower().strip()
        if t and t not in STOP and t not in NAME_WORDS and t not in META_WORDS:
            association_pool.append(t)
association_pool = list(dict.fromkeys(association_pool))

silent_streak = max(0, int(state.get("silent_turns", 0) or 0))
SOFT_SILENCE, HARD_SILENCE = 1, 3
silence_pressure = max(0.0, min(1.0, (silent_streak - SOFT_SILENCE + 1) / max(1, HARD_SILENCE - SOFT_SILENCE + 1)))

continue_w = max(.05, .74 + .52 * g["attention_persistence"] + .24 * g["imitation"] - .72 * g["exploration"] - .78 * topic_fatigue)
associate_w = max(.06, .26 + .92 * g["association_spread"] + .24 * g["exploration"] + .62 * topic_fatigue)
jump_w = max(.05, .10 + .50 * g["exploration"] + .48 * g["novelty_weight"] - .14 * g["attention_persistence"] + .70 * topic_fatigue)
mode_roll = rng.random() * (continue_w + associate_w + jump_w)
if mode_roll < continue_w:
    cognitive_mode = "continue"
elif mode_roll < continue_w + associate_w:
    cognitive_mode = "associate"
else:
    cognitive_mode = "jump"

activation = float(d.get("recent_activation", 0.5) or 0.5)
drive = .48 + .22 * g["spontaneous_initiation"] - .18 * g["inhibition"] + .07 * activation + .28 * silence_pressure
if cognitive_mode == "jump":
    drive += .08 + .08 * topic_fatigue
elif cognitive_mode == "associate":
    drive += .03 * topic_fatigue
drive = max(.16, min(.98, drive))
wants_to_speak = silent_streak >= HARD_SILENCE or rng.random() < drive

base_temp = max(.48, min(1.10, .48 + .46 * g["exploration"] + .13 * g["association_spread"]))
temperature = min(1.36, base_temp + {"continue": 0.0, "associate": .13, "jump": .27}[cognitive_mode] + .12 * silence_pressure)
max_tokens = 52 + int(round(38 * iq_scale))
max_attempts = 5 + int(round(2 * iq_scale)) + int(round(4 * silence_pressure))
char_cap = 330 + int(round(180 * iq_scale))

# Context and cues vary by cognitive move.
if cognitive_mode == "jump":
    recent = []
    cues = []
elif cognitive_mode == "associate":
    recent = clean_history[-max(2, 4 + int(round(2 * iq_scale))):]
    cue_rng = random.Random(seed ^ 0x5A17C9E3)
    cues = cue_rng.sample(association_pool, min(4, len(association_pool))) if association_pool else []
else:
    recent = clean_history[-max(4, 6 + int(round(3 * iq_scale))):]
    cue_rng = random.Random(seed ^ 0x5A17C9E3)
    cues = cue_rng.sample(association_pool, min(2, len(association_pool))) if association_pool else []

transcript = "\n".join(f'{names.get(m.get("speaker"), m.get("speaker", "?"))}: {m.get("text", "")}' for m in recent)


def loose_stem(word):
    word = str(word or "").lower().strip()
    for suffix in ("ness", "ments", "ment", "ations", "ation", "ingly", "ing", "ers", "er", "ed", "ies", "es", "s"):
        if len(word) > len(suffix) + 4 and word.endswith(suffix):
            base = word[:-len(suffix)]
            if suffix == "ies":
                base += "y"
            return base
    return word


def concept_match(words_a, words_b):
    a = {loose_stem(w) for w in words_a}
    b = {loose_stem(w) for w in words_b}
    if a & b:
        return True
    return any(len(x) >= 5 and len(y) >= 5 and x[:5] == y[:5] for x in a for y in b)


def parse_spark_pool(raw):
    text = clean_generation(raw, cap=1000)
    # Prefer line-separated candidates, but tolerate compact comma/semicolon output.
    parts = re.split(r"[\n;|]+", text)
    if len(parts) <= 2 and text.count(",") >= 2:
        parts = text.split(",")
    out = []
    for part in parts:
        part = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", part).strip().strip('"\'` ')
        part = re.sub(r"^(?:subject|idea|thought|spark)\s*[:>-]\s*", "", part, flags=re.I).strip()
        part = " ".join(part.split())
        if part:
            out.append(part[:90])
    return out


def spark_valid(candidate):
    low = candidate.lower()
    raw_words = {w.lower().strip("'-") for w in re.findall(r"[A-Za-z][A-Za-z'-]{2,}", candidate)}
    meaningful = {w for w in raw_words if w not in STOP and w not in NAME_WORDS}
    if not meaningful:
        return False, "no-content"
    if len(candidate.split()) > 6:
        return False, "too-long"
    if any(w in META_WORDS for w in raw_words):
        return False, "room-or-task-meta"
    if raw_words & NAME_WORDS:
        return False, "person-name"
    if meaningful & rut_words:
        return False, "recent-rut"
    if speaker_label_re.search(candidate):
        return False, "speaker-label"
    if any(re.search(p, low) for p in SERVICE_PATTERNS + FACILITATOR_PATTERNS + ROLE_PATTERNS):
        return False, "dialogue-meta"
    return True, ""


private_spark = ""
spark_candidates = []
spark_rejections = []
if cognitive_mode == "jump":
    spark_system = (
        "Create a private pool of ten unrelated subjects that could simply cross an adult mind. "
        "Output exactly ten short noun phrases, one per line, with no numbering and no explanation. "
        "They must be actual things, phenomena, concepts, places, sensations, questions-as-concepts, or observations. "
        "Do not make them about the people present, conversation, socializing, a group activity, planning, productivity, studying, projects, schedules, tasks, meetings, or helping."
    )
    spark_prompt = "Ten unrelated subjects:"
    valid = []
    for pool_attempt in range(2):
        raw = run_local(
            spark_system,
            spark_prompt,
            (seed ^ 0x71C4D2A9 ^ (pool_attempt * 104729)) & 0x7FFFFFFF,
            110,
            min(1.36, temperature + .10),
        )
        for candidate in parse_spark_pool(raw):
            ok, reason = spark_valid(candidate)
            if ok:
                valid.append(candidate)
            else:
                spark_rejections.append({"candidate": candidate[:70], "reason": reason})
        if len(valid) >= 3:
            break
    # Deduplicate by a light stem signature; the mind supplies all candidates, machinery only selects.
    deduped = []
    seen = set()
    for candidate in valid:
        signature = tuple(sorted(loose_stem(w) for w in content_tokens(candidate)))
        if signature and signature not in seen:
            seen.add(signature)
            deduped.append(candidate)
    spark_candidates = deduped[:12]
    if spark_candidates:
        private_spark = rng.choice(spark_candidates)

if cognitive_mode == "jump":
    mode_instruction = (
        f"A private thought has occurred: {private_spark}. Speak naturally from it. "
        "Use or naturally inflect at least one meaningful word from that private thought. "
        "Do not mention choosing a subject, changing subjects, the conversation itself, or any internal process."
    )
elif cognitive_mode == "associate":
    cue_text = ", ".join(cues) if cues else "none"
    mode_instruction = (
        "Let the recent exchange trigger a sideways association rather than merely continuing it. "
        f"Older rebuilt-era associations available if they genuinely fit: {cue_text}. "
        "Do not explain the association process."
    )
else:
    mode_instruction = (
        "Stay with the recent thread only if it still has life. Add an opinion, reaction, implication, joke, doubt, "
        "observation, or question of your own rather than paraphrasing it."
    )

system_prompt = f"""Generate exactly one possible spoken line for {name}. {name}, {peer_names} are four strangers spending unstructured time together. They are not a team, not coworkers, not a study group, and have no shared task, project, agenda, host, customer, user, or service relationship. Familiarity may develop only through what actually happens here.

Speak as an ordinary adult peer. Do not introduce anyone, offer assistance, ask what someone needs, assign tasks, manage the conversation, create a plan merely to be useful, narrate the interaction, mention instructions, or act like a chatbot. Do not invent shared commitments, future meetings, future hangouts, or off-room events. Questions are optional. Silence, humor, disagreement, curiosity, awkwardness, opinions, and spontaneous subject changes are normal.

{mode_instruction}

Persistent adult background: {human_context}
{name} has no predetermined personality. Wording should emerge from the immediate exchange, genome-driven sampling, accumulated rebuilt-era interaction, and lived background rather than stereotypes.
Output only the spoken line, without a name label or quotation marks."""
base_prompt = f"Recent speech:\n{transcript}\n\n{name}:" if recent else f"{name}:"


def max_recent_similarity(text):
    return max((jac(text, m.get("text", "")) for m in recent), default=0.0)


def forbidden_reason(text):
    low = str(text or "").lower().strip()
    if not low:
        return "empty"
    if speaker_label_re.search(text):
        return "speaker-label"
    if any(re.search(p, low) for p in SERVICE_PATTERNS):
        return "service"
    if any(re.search(p, low) for p in FACILITATOR_PATTERNS):
        return "facilitator"
    if any(re.search(p, low) for p in ROLE_PATTERNS):
        return "false-role"
    if any(re.search(p, low) for p in FUTURE_SHARED_PATTERNS):
        return "invented-shared-future"
    if any(re.search(p, low) for p in META_PATTERNS):
        return "prompt-meta"
    if not recent and re.match(r"^(?:me too|same here|i agree|exactly|yeah[,!]|right[,!])\b", low):
        return "contextless-agreement"
    for m in recent:
        if " ".join(low.split()) == " ".join(str(m.get("text", "")).lower().split()):
            return "exact-repeat"
    semantic = set(content_tokens(text))
    if cognitive_mode in {"jump", "associate"} and not semantic:
        return "no-semantic-content"
    if cognitive_mode == "jump" and private_spark:
        spark_words = set(content_tokens(private_spark))
        if spark_words and not concept_match(semantic, spark_words):
            return "lost-private-spark"
    sim_limit = {"continue": .64, "associate": .52, "jump": .46}[cognitive_mode] + .10 * silence_pressure
    similarity = max_recent_similarity(text)
    if similarity >= min(.78, sim_limit):
        return f"near-repeat-{similarity:.2f}"
    return ""


def infer_topics(text):
    words = []
    for w in content_tokens(text):
        if w in META_WORDS or w in NAME_WORDS:
            continue
        if w not in words:
            words.append(w)
        if len(words) >= 4:
            break
    return words


def novelty(text):
    if not text:
        return 0.0
    sim = max_recent_similarity(text)
    unique = set(content_tokens(text))
    recent_words = set(content_tokens(" ".join(m.get("text", "") for m in recent)))
    new_ratio = len(unique - recent_words) / len(unique) if unique else 0.0
    floor = {"continue": 0.0, "associate": .08, "jump": .15}[cognitive_mode]
    return max(0.0, min(1.0, .55 * (1.0 - sim) + .45 * new_ratio + floor))

outdir = ROOT / "society_parts"
outdir.mkdir(exist_ok=True)
result = {
    "entity": entity_id,
    "name": name,
    "node": node_id,
    "speak": False,
    "text": "",
    "salience": 0.0,
    "novelty": 0.0,
    "topics": [],
    "memory_note": "",
    "engine": "github-held-gguf",
    "model_asset": "society-brain-v1/society-brain-q4_0.gguf",
    "speech_drive": round(drive, 4),
    "iq": iq,
    "age": age,
    "socioeconomic_status": ses,
    "context_turns": len(recent),
    "association_cues": len(cues),
    "max_tokens": max_tokens,
    "silent_streak": silent_streak,
    "silence_pressure": round(silence_pressure, 3),
    "cognitive_mode": cognitive_mode,
    "topic_fatigue": round(topic_fatigue, 4),
    "private_spark": private_spark,
    "spark_candidates": spark_candidates,
    "spark_rejections": spark_rejections[:12],
    "rebuild_epoch": ROOM_REBUILD_EPOCH,
}

error = None
rejected = []
emergency = None
emergency_sim = 2.0
try:
    if wants_to_speak and (cognitive_mode != "jump" or private_spark):
        chosen_text = ""
        for attempt in range(max_attempts):
            raw = run_local(
                system_prompt,
                base_prompt,
                (seed + attempt * 104729) & 0x7FFFFFFF,
                max_tokens,
                temperature,
            )
            candidate = clean_generation(raw, char_cap)
            reason = forbidden_reason(candidate)
            if reason:
                rejected.append(reason)
                continue
            sim = max_recent_similarity(candidate)
            if sim < emergency_sim:
                emergency = candidate
                emergency_sim = sim
            chosen_text = candidate
            break
        if chosen_text:
            nov = novelty(chosen_text)
            topics = infer_topics(chosen_text)
            result["speak"] = True
            result["text"] = chosen_text
            result["topics"] = topics
            result["novelty"] = round(nov, 4)
            sal = .22 + .16 * min(1.0, len(chosen_text.split()) / 18.0) + .38 * nov + .17 * g["novelty_weight"]
            if cognitive_mode == "jump":
                sal += .07
            elif cognitive_mode == "associate":
                sal += .03
            result["salience"] = round(max(0.0, min(1.0, sal)), 4)
            if result["salience"] >= .66:
                result["memory_note"] = chosen_text[:160]
        else:
            result["rejected_candidates"] = rejected
        if emergency:
            result["emergency_candidate"] = {
                "text": emergency,
                "similarity": round(emergency_sim, 4),
                "topics": infer_topics(emergency),
                "novelty": round(novelty(emergency), 4),
                "cognitive_mode": cognitive_mode,
            }
    elif wants_to_speak and cognitive_mode == "jump" and not private_spark:
        result["rejected_candidates"] = ["no-valid-private-spark"]
except Exception as exc:
    error = str(exc)[:900]
    result["error"] = error

path = outdir / f"{entity_id}-node-{node_id}.json"
path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
print(json.dumps(result, ensure_ascii=False))
if error:
    sys.exit(2)
