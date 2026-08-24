"""Runtime guard for Room private-model structured output.

Python automatically imports sitecustomize from the script directory.  The Room's
small local model was truncating comprehension JSON at the old 192-token budget,
so every cognition worker gets a larger structured-output allowance without
changing conversational behavior or the checked-in Room state.
"""
from __future__ import annotations

import json
import urllib.request

try:
    import room_private_model as _rpm
except Exception:
    _rpm = None


if _rpm is not None:
    def _room_request(model_url: str, prompt: str, role: str, temperature: float,
                      timeout: int, self_entity: str | None = None,
                      attempt: int = 0) -> str:
        body = {
            "prompt": prompt,
            "n_predict": {
                "comprehension": 512,
                "thought": 512,
                "expression": 384,
            }.get(role, 384),
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
            return str(payload.get("content", ""))

    _rpm._request = _room_request
