#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path

from room_prompt_guard import prompt_leak_reason

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/society_node.py"

# The durable behavioral rules remain in code, but the people do not receive the
# long control/premise prose as model context. At runtime we remove that prose
# before executing the node generator. The model sees only conversation text,
# its own private spark/cues, and its name as a continuation marker.
source = SOURCE.read_text()

# Remove the prose instruction used to create the private spark pool. A bare
# bullet continuation gives the local model stochastic material without exposing
# a description of what the machinery is doing.
source, spark_replacements = re.subn(
    r'    spark_system = \(.*?\n    spark_prompt = "Ten unrelated subjects:"',
    lambda _m: '    spark_system = " "\n    spark_prompt = "• "',
    source,
    count=1,
    flags=re.S,
)

# Remove the long Room premise/personality/behavior prompt from the model input.
# Cognitive mode still matters through which context is supplied: jump gets only
# its private spark, associate gets sparse own-memory cues plus recent speech,
# continue gets recent speech. No explanatory control prose is shown to it.
replacement = '''system_prompt = " "
if cognitive_mode == "jump" and private_spark:
    base_prompt = f"{private_spark}\\n{name}:"
elif cognitive_mode == "associate" and cues:
    base_prompt = f"{' / '.join(cues)}\\n{transcript}\\n{name}:" if transcript else f"{' / '.join(cues)}\\n{name}:"
elif recent:
    base_prompt = f"{transcript}\\n{name}:"
else:
    base_prompt = f"{name}:"'''
source, prompt_replacements = re.subn(
    r'system_prompt = f""".*?"""\nbase_prompt = .*?\n\n\ndef max_recent_similarity',
    lambda _m: replacement + '\n\n\ndef max_recent_similarity',
    source,
    count=1,
    flags=re.S,
)

if spark_replacements != 1 or prompt_replacements != 1:
    raise RuntimeError(
        f"Room private-context transform failed: spark={spark_replacements} prompt={prompt_replacements}"
    )

# Compile before execution so a transform mistake fails explicitly here rather
# than creating a misleading stretch of Room silence.
compiled = compile(source, str(SOURCE), "exec")
namespace = {"__name__": "__main__", "__file__": str(SOURCE)}
try:
    exec(compiled, namespace, namespace)
except SystemExit as exc:
    if exc.code not in (None, 0):
        raise

# Independent output barrier: even if the local model somehow reconstructs or
# paraphrases implementation prose, it cannot vote, enter memory, or reach the
# transcript.
blocked_any = False
for path in sorted((ROOT / "society_parts").glob("*.json")):
    try:
        obj = json.loads(path.read_text())
    except Exception:
        continue

    dirty = False
    reason = prompt_leak_reason(obj.get("text", ""))
    emergency = obj.get("emergency_candidate") or {}
    emergency_reason = prompt_leak_reason(emergency.get("text", ""))

    if reason:
        obj["speak"] = False
        obj["text"] = ""
        obj["topics"] = []
        obj["memory_note"] = ""
        obj.pop("emergency_candidate", None)
        obj["prompt_leak_blocked"] = reason
        blocked_any = True
        dirty = True
    elif emergency_reason:
        obj.pop("emergency_candidate", None)
        obj["prompt_leak_emergency_blocked"] = emergency_reason
        blocked_any = True
        dirty = True

    if dirty:
        path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")

print("Room node prompt guard: clean" if not blocked_any else "Room node prompt guard: leak blocked")
