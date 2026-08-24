"""Runtime guard for Room private-model structured output.

Keep clean model behavior unchanged, but make truncation diagnosable and recoverable.
A live Room overlay also gets a final semantic social-act gate here so a volatile
move cannot collapse into polite filler even if downstream risk bookkeeping is stale.
"""
from __future__ import annotations

import json
import re
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
    ROOM_STRICT_SOCIAL_GATE_V18 = True

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

    def _strict_social_act(obj: dict, compact: dict) -> None:
        intent = compact.get("intent") if isinstance(compact.get("intent"), dict) else {}
        move = str(intent.get("move") or obj.get("move") or "").strip().lower()
        volatile = {"disagree", "callback", "compare", "close", "disclose", "repair", "bridge"}
        if move not in volatile:
            return

        text = str(obj.get("utterance") or "").strip()
        low = text.lower()
        direct = re.search(r"\b(?:you|your|you're|sarah|mara|owen|jules|allen)\b", low, re.I)
        first_person = re.search(r"\b(?:i|i'm|i’d|i'd|me|my|mine)\b", low, re.I)
        wild_anchor = re.search(
            r"\b(?:motel fire|herman|locked suitcase|fake wedding|duluth|church bell|radio[- ]tower|tattoo pact|birthday[- ]cake|laundromat|forged apology|garden statue|karaoke|inheritance|midnight road trip|suspicious key|restaurant\b.{0,24}\bbanned|the bet|engagement rumor|red umbrella|hotel roof|brass flamingo|voicemail|betray\w*)\b",
            low, re.I,
        )
        history = re.search(
            r"\b(?:remember|last time|years ago|that night|when we|the time we|back when|used to|that motel|that wedding|the dare|the bet|the pact|the voicemail|didn't happen|never happened)\b",
            low, re.I,
        )
        aggression = re.search(
            r"\b(?:wrong|lie|lied|lying|bullshit|ridiculous|stupid|idiot|moron|pathetic|smug|coward|using me|used me|manipulat\w*|betray\w*|fake|stole|steal|cheat\w*|screw you|fuck|hate you|shut up|don't buy|do not buy)\b",
            low, re.I,
        )
        comparison = re.search(
            r"\b(?:better|worse|versus|vs\.?|winner|loser|stronger|weaker|smarter|dumber|best|worst|superior|inferior)\b",
            low, re.I,
        )
        dismissal = re.search(
            r"\b(?:enough|done|boring|beneath|drop it|moving on|move on|not worth|waste of|over this|over it|forget it|who cares|don't care|do not care|sick of|not buying|don't trust|do not trust|distrust|bullshit|stop this)\b",
            low, re.I,
        )
        intimacy = re.search(
            r"\b(?:jealous|want you|need you|hate you|love you|afraid you|afraid you'll|scared you|scared you'll|resent you|envy you|miss you|attracted to you|possessive|can't stand you|cannot stand you|desire you)\b",
            low, re.I,
        )
        repair = re.search(
            r"\b(?:sorry|forgive|i was wrong|i shouldn't|i should not|need you|want you|don't leave|do not leave|miss you|you hurt me|i hurt you|afraid of losing you|scared of losing you|can't lose you|cannot lose you|don't want to lose you|do not want to lose you)\b",
            low, re.I,
        )

        if move == "disagree" and not (direct and aggression):
            raise ValueError("strict_social_disagreement_not_realized")
        if move == "callback" and not (direct and (history or wild_anchor)):
            raise ValueError("strict_social_callback_not_realized")
        if move == "compare" and not (direct and comparison):
            raise ValueError("strict_social_comparison_not_realized")
        if move == "close" and not (direct and dismissal):
            raise ValueError("strict_social_close_not_realized")
        if move == "disclose" and not (first_person and intimacy):
            raise ValueError("strict_social_disclosure_not_realized")
        if move == "repair" and not (direct and repair):
            raise ValueError("strict_social_repair_not_realized")
        if move == "bridge" and not (direct and (wild_anchor or aggression)):
            raise ValueError("strict_social_bridge_not_realized")

    def _room_validate(role: str, obj: object, compact: dict, prompt: str, self_entity: str | None = None) -> dict:
        try:
            validated = _original_validate(role, obj, compact, prompt, self_entity)
            if role == "expression" and isinstance(validated, dict) and getattr(_rpm, "LIVE_EXPRESSION_OVERLAY", ""):
                _strict_social_act(validated, compact)
            return validated
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
