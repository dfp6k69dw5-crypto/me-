#!/usr/bin/env python3
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-opus-4-6"


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_request(path):
    data = json.loads(pathlib.Path(path).read_text())
    if not isinstance(data, dict):
        raise ValueError("request must be a JSON object")
    prompt = str(data.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("request.prompt is required")
    return data, prompt


def build_user_text(data, prompt):
    context = data.get("context") or []
    if isinstance(context, str):
        context = [context]
    context = [str(x) for x in context if str(x).strip()]
    parts = [prompt]
    if context:
        parts.append("\nShared context from the collaborating agent/repository:\n" + "\n\n".join(context))
    return "\n".join(parts)


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: claude_bridge.py REQUEST_JSON OUT_JSON")

    request_path = pathlib.Path(sys.argv[1])
    out_path = pathlib.Path(sys.argv[2])
    data, prompt = read_request(request_path)

    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps({
            "ok": False,
            "error": "ANTHROPIC_API_KEY is not configured in GitHub Actions secrets",
            "request_file": str(request_path),
            "completed_at": utc_now(),
        }, indent=2) + "\n")
        raise SystemExit(2)

    model = str(data.get("model") or DEFAULT_MODEL)
    max_tokens = int(data.get("max_tokens") or 1800)
    max_tokens = max(64, min(max_tokens, 8192))
    system = str(data.get("system") or (
        "You are Claude collaborating with another AI agent through a GitHub mailbox. "
        "Be concrete, concise, and evidence-oriented. Distinguish observations from guesses. "
        "When reviewing a software problem, identify the likeliest cause, the safest next operation, "
        "and any tests that would falsify your diagnosis. Do not claim you changed files unless the request says you did."
    ))

    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": build_user_text(data, prompt)}],
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(API_URL, data=body, method="POST", headers={
        "content-type": "application/json",
        "x-api-key": key,
        "anthropic-version": API_VERSION,
    })

    result = {
        "ok": False,
        "request_file": str(request_path),
        "model": model,
        "completed_at": utc_now(),
    }
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            raw = json.loads(response.read().decode("utf-8"))
        text_parts = [b.get("text", "") for b in raw.get("content", []) if b.get("type") == "text"]
        result.update({
            "ok": True,
            "response": "\n".join(x for x in text_parts if x).strip(),
            "stop_reason": raw.get("stop_reason"),
            "usage": raw.get("usage"),
            "message_id": raw.get("id"),
        })
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        result.update({"error": f"Claude API HTTP {exc.code}", "detail": detail[:4000]})
    except Exception as exc:
        result.update({"error": f"{type(exc).__name__}: {exc}"})

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    if not result["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
