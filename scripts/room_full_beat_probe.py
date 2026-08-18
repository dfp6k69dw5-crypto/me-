#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / ".room_probe_model"
RUNTIME_DIR = MODEL_DIR / "runtime"
MODEL = MODEL_DIR / "society-brain-q4_0.gguf"
STATUS = ROOT / "room" / "private-full-beat-diagnostic.json"


def safe(text: str) -> str:
    out = str(text or "")
    for key in ("ROOM_PROMPT_PERCEPTION", "ROOM_PROMPT_DELIBERATION", "ROOM_PROMPT_EXPRESSION"):
        secret = os.environ.get(key, "")
        if secret:
            out = out.replace(secret, "[redacted]")
    return out[-1200:]


def write(data: dict) -> None:
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps(data, indent=2) + "\n")


def clean_base_env() -> dict:
    env = dict(os.environ)
    for k in ("ROOM_PROMPT_PERCEPTION", "ROOM_PROMPT_DELIBERATION", "ROOM_PROMPT_EXPRESSION", "ROOM_NODE_PROMPT"):
        env.pop(k, None)
    env["ROOM_MODEL_URL"] = "http://127.0.0.1:18080/completion"
    env["ROOM_CYCLE_KEY"] = "full-private-probe"
    return env


def node_prompt(n: int, phase: str) -> str:
    local = n % 3
    if phase == "sense" and local == 0:
        return os.environ.get("ROOM_PROMPT_PERCEPTION", "")
    if phase == "recurrent" and local == 1:
        return os.environ.get("ROOM_PROMPT_DELIBERATION", "")
    if phase == "recurrent" and local == 2:
        return os.environ.get("ROOM_PROMPT_EXPRESSION", "")
    return ""


def run_nodes(nodes: list[int], phase: str, bus: str | None = None) -> tuple[bool, dict]:
    procs = []
    for n in nodes:
        env = clean_base_env()
        env["ROOM_NODE_ID"] = str(n)
        env["ROOM_NODE_PROMPT"] = node_prompt(n, phase)
        cmd = ["python3", "scripts/room_engine_v5.py", "node", "--phase", phase]
        if bus:
            cmd += ["--bus", bus]
        procs.append((n, subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)))
    results = {}
    ok = True
    for n, p in procs:
        out, err = p.communicate(timeout=90)
        results[str(n)] = {"returncode": p.returncode, "stdout": safe(out), "stderr": safe(err)}
        if p.returncode != 0:
            ok = False
    return ok, results


def run_cmd(cmd: list[str]) -> tuple[bool, dict]:
    env = clean_base_env()
    p = subprocess.run(cmd, cwd=ROOT, env=env, text=True, capture_output=True, timeout=90)
    return p.returncode == 0, {"returncode": p.returncode, "stdout": safe(p.stdout), "stderr": safe(p.stderr)}


def main() -> int:
    result = {"server_ready": False, "phase": "starting"}
    write(result)
    bins = list(RUNTIME_DIR.rglob("llama-server"))
    if not MODEL.exists() or not bins:
        result.update({"phase": "setup", "error": "probe model/runtime missing"})
        write(result)
        return 0
    server = bins[0]
    server.chmod(0o755)
    server_env = clean_base_env()
    server_env.pop("ROOM_MODEL_URL", None)
    proc = subprocess.Popen([str(server), "-m", str(MODEL), "--host", "127.0.0.1", "--port", "18080", "-c", "8192", "-np", "4"], cwd=ROOT, env=server_env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(120):
            if proc.poll() is not None:
                break
            try:
                with urllib.request.urlopen("http://127.0.0.1:18080/health", timeout=1):
                    result["server_ready"] = True
                    break
            except Exception:
                time.sleep(1)
        if not result["server_ready"]:
            result.update({"phase": "server", "error": f"server_exit={proc.poll()}"})
            write(result)
            return 0

        shutil.rmtree(ROOT / "room_parts", ignore_errors=True)
        shutil.rmtree(ROOT / "room_work", ignore_errors=True)
        (ROOT / "room_parts").mkdir()
        (ROOT / "room_work").mkdir()

        result["phase"] = "sense"
        ok, detail = run_nodes(list(range(12)), "sense")
        result["sense"] = detail
        write(result)
        if not ok:
            result["status"] = "failed"
            write(result)
            return 0

        ok, detail = run_cmd(["python3", "scripts/room_engine_v5.py", "bus"])
        result["bus"] = detail
        write(result)
        if not ok:
            result.update({"phase": "bus", "status": "failed"})
            write(result)
            return 0

        result["phase"] = "deliberation"
        ok, detail = run_nodes([0, 1, 3, 4, 6, 7, 9, 10], "recurrent", "room_work/bus-sense.json")
        result["deliberation"] = detail
        write(result)
        if not ok:
            result["status"] = "failed"
            write(result)
            return 0

        ok, detail = run_cmd(["python3", "scripts/room_engine_v5.py", "bus2", "--bus", "room_work/bus-sense.json"])
        result["bus2"] = detail
        write(result)
        if not ok:
            result.update({"phase": "bus2", "status": "failed"})
            write(result)
            return 0

        result["phase"] = "expression"
        ok, detail = run_nodes([2, 5, 8, 11], "recurrent", "room_work/bus-recurrent.json")
        result["expression"] = detail
        write(result)
        if not ok:
            result["status"] = "failed"
            write(result)
            return 0

        result["phase"] = "commit"
        ok, detail = run_cmd(["python3", "scripts/room_engine_v5.py", "commit"])
        result["commit"] = detail
        result["status"] = "accepted" if ok else "failed"
        write(result)
        return 0
    except Exception as exc:
        result.update({"status": "failed", "error": safe(f"{type(exc).__name__}: {exc}")})
        write(result)
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
