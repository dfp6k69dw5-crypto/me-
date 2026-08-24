"""Runtime guard for Room private-model structured output.

Keep clean model behavior unchanged, but make truncation diagnosable and recoverable.
"""
from __future__ import annotations

import json
import sys
import urllib.request

try:
    import room_private_model as _rpm
except Exception:
    _rpm = None


if _rpm is not None:
    _last_completion_meta = {}
    _original_extract_json = _rpm._extract_json
    _original_validate = _rpm._validate

    def _repair_truncated_json(text: str):
        """Best-effort close of a JSON object cut off at the generation limit."""
        text = str(text or "").strip()
        start = text.find("{")
        if start < 0:
            raise ValueError("model returned no structured object")
        candidate = text[start:]
        stack = []
        in_string = False
        escaped = False
        for ch in candidate:
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch in "[{":
                stack.append(ch)
            elif ch == "]" and stack and stack[-1] == "[":
                stack.pop()
            elif ch == "}" and stack and stack[-1] == "{":
                stack.pop()
        if in_string:
            if escaped:
                candidate += "\\"
            candidate += '"'
        for opener in reversed(stack):
            candidate += "]" if opener == "[" else "}"
        return json.loads(candidate)

    def _room_extract_json(text: str):
        try:
            return _original_extract_json(text)
        except ValueError as exc:
            meta = dict(_last_completion_meta)
            print(
                "ROOM_MODEL_REJECTION "
                f"stop_type={meta.get('stop_type', 'unknown')} "
                f"tokens_predicted={meta.get('tokens_predicted', 'unknown')} "
                f"n_predict={meta.get('n_predict', 'unknown')} "
                f"reason={str(exc)[:120]}",
                file=sys.stderr,
                flush=True,
            )
            try:
                repaired = _repair_truncated_json(text)
                print("ROOM_MODEL_JSON_SALVAGED=true", file=sys.stderr, flush=True)
                return repaired
            except Exception:
                raise exc

    def _room_validate(role: str, obj: object, compact: dict, prompt: str, self_entity: str | None = None) -> dict:
        try:
            return _original_validate(role, obj, compact, prompt, self_entity)
        except ValueError as exc:
            meta = dict(_last_completion_meta)
            print(
                "ROOM_MODEL_REJECTION "
                f"role={role} "
                f"stop_type={meta.get('stop_type', 'unknown')} "
                f"tokens_predicted={meta.get('tokens_predicted', 'unknown')} "
                f"n_predict={meta.get('n_predict', 'unknown')} "
                f"reason={str(exc)[:120]}",
                file=sys.stderr,
                flush=True,
            )
            raise

    def _room_request(model_url: str, prompt: str, role: str, temperature: float,
                      timeout: int, self_entity: str | None = None,
                      attempt: int = 0) -> str:
        # First attempt has ample headroom. Existing _private_run retries once for
        # comprehension/thought; make that retry a doubled generation budget.
        n_predict = 512 * (2 if attempt else 1)
        body = {
            "prompt": prompt,
            "n_predict": n_predict,
            "temperature": temperature,
            "cache_prompt": True,
            "json_schema": _rpm._schema(role, self_entity),
        }
        if role == "expression":
            body.update({
                "seed": _rpm._sample_seed(role, self_entity, attempt),
                "top_k": 60,
                "top_p": 0.96,
                "min_p": 0.02,
            })
        req = urllib.request.Request(
            _rpm._completion_url(model_url),
            data=json.dumps(body, ensure_ascii=False).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8", "replace"))
            _last_completion_meta.clear()
            _last_completion_meta.update({
                "role": role,
                "attempt": attempt,
                "n_predict": n_predict,
                "stop_type": payload.get("stop_type"),
                "tokens_predicted": payload.get("tokens_predicted"),
            })
            return str(payload.get("content", ""))

    # A live package overlay owns its sampler. The compatibility shim may still
    # add truncation salvage and rejection diagnostics, but must not replace the
    # overlay's high-variance request function.
    if not getattr(_rpm, "LIVE_EXPRESSION_OVERLAY", ""):
        _rpm._request = _room_request
    _rpm._extract_json = _room_extract_json
    _rpm._validate = _room_validate
