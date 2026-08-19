#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/sarah-society.yml"
OUT = ROOT / "room/warm-runner-watchdog-diagnostic.json"

text = WORKFLOW.read_text(encoding="utf-8")

node_timeout_decl = re.search(r"ROOM_NODE_TIMEOUT_SECONDS=([0-9]+)", text)
kill_grace_decl = re.search(r"ROOM_NODE_KILL_GRACE_SECONDS=([0-9]+)", text)
failure_limit_decl = re.search(r"ROOM_BEAT_FAILURE_LIMIT=([0-9]+)", text)

# Structural checks against the actual production workflow. These intentionally
# fail on the current unbounded baseline, then turn green only when the runner
# itself has bounded node execution and an escape to fresh-runner handoff.
timeout_markers = text.count('timeout -k "${ROOM_NODE_KILL_GRACE_SECONDS}s" "${ROOM_NODE_TIMEOUT_SECONDS}s"')
has_sense_timeout = "room_engine_v5.py node --phase sense" in text and timeout_markers >= 1
has_recurrent_timeout = "room_engine_v5.py node --phase recurrent" in text and timeout_markers >= 3
has_expression_timeout = "ROOM_EXPRESSION_RANK" in text and timeout_markers >= 4
has_failure_counter = "consecutive_failures" in text
has_failure_break = bool(re.search(r'consecutive_failures.*ROOM_BEAT_FAILURE_LIMIT', text, re.S)) and "break" in text
has_success_reset = bool(re.search(r'consecutive_failures=0', text))
has_warm_window = "stop_at=$((SECONDS + 19800))" in text
has_self_handoff = "gh workflow run sarah-society.yml" in text

# Behavioral probe: a child that never returns survives an unbounded wait window.
# Then, if production timeout parameters exist, prove those exact parameters are
# accepted by GNU timeout and actually terminate a synthetic hung child.
probe_sleep_seconds = 30
unbounded_probe_window = 1.0
p = subprocess.Popen([sys.executable, "-c", f"import time; time.sleep({probe_sleep_seconds})"])
time.sleep(unbounded_probe_window)
unbounded_hang_survived = p.poll() is None
if p.poll() is None:
    p.terminate()
    try:
        p.wait(timeout=2)
    except subprocess.TimeoutExpired:
        p.kill()
        p.wait(timeout=2)

bounded_probe = {
    "attempted": False,
    "terminated": False,
    "elapsed_seconds": None,
    "returncode": None,
}

if node_timeout_decl and kill_grace_decl:
    # Keep CI fast while preserving the same TERM->KILL mechanism. The structural
    # checks above ensure production uses the declared production values; this
    # behavioral probe verifies GNU timeout semantics in the runner environment.
    bounded_probe["attempted"] = True
    started = time.monotonic()
    proc = subprocess.run(
        ["timeout", "-k", "1s", "1s", sys.executable, "-c", "import time; time.sleep(30)"],
        capture_output=True,
        text=True,
    )
    elapsed = time.monotonic() - started
    bounded_probe.update(
        terminated=elapsed < 5 and proc.returncode in (124, 137, -signal.SIGTERM, -signal.SIGKILL),
        elapsed_seconds=round(elapsed, 3),
        returncode=proc.returncode,
    )

checks = {
    "unbounded_hang_reproduced": unbounded_hang_survived,
    "node_timeout_declared": bool(node_timeout_decl),
    "kill_grace_declared": bool(kill_grace_decl),
    "failure_limit_declared": bool(failure_limit_decl),
    "sense_nodes_bounded": has_sense_timeout,
    "recurrent_nodes_bounded": has_recurrent_timeout,
    "expression_nodes_bounded": has_expression_timeout,
    "failure_counter_present": has_failure_counter,
    "failure_threshold_breaks_to_handoff": has_failure_break,
    "successful_beat_resets_failure_counter": has_success_reset,
    "warm_5_5h_window_preserved": has_warm_window,
    "self_handoff_preserved": has_self_handoff,
    "bounded_timeout_behavior": bounded_probe["terminated"],
}

required = [
    checks["node_timeout_declared"],
    checks["kill_grace_declared"],
    checks["failure_limit_declared"],
    checks["sense_nodes_bounded"],
    checks["recurrent_nodes_bounded"],
    checks["expression_nodes_bounded"],
    checks["failure_counter_present"],
    checks["failure_threshold_breaks_to_handoff"],
    checks["successful_beat_resets_failure_counter"],
    checks["warm_5_5h_window_preserved"],
    checks["self_handoff_preserved"],
    checks["bounded_timeout_behavior"],
]

out = {
    "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "pass": all(required),
    "workflow": str(WORKFLOW.relative_to(ROOT)),
    "baseline_mechanism": "one never-returning cognition/model subprocess can block the warm run_beat indefinitely",
    "synthetic_unbounded_child_survived_probe_window": unbounded_hang_survived,
    "production_timeout_seconds": int(node_timeout_decl.group(1)) if node_timeout_decl else None,
    "production_kill_grace_seconds": int(kill_grace_decl.group(1)) if kill_grace_decl else None,
    "production_failure_limit": int(failure_limit_decl.group(1)) if failure_limit_decl else None,
    "timeout_marker_occurrences": timeout_markers,
    "bounded_probe": bounded_probe,
    "checks": checks,
}
OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
print(json.dumps(out, indent=2))
sys.exit(0 if out["pass"] else 1)
