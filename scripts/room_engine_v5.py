#!/usr/bin/env python3
from __future__ import annotations

"""Select the lean autonomy-v2 model path only for the Llama Room brain.

The complete pre-Llama production wrapper is preserved in
room_engine_v5_legacy.py. Qwen fallback uses that code unchanged. When the
workflow has positively identified Llama 3.2 as the active brain, only the
language-model call boundary is replaced with the autonomy-v2 adapter; the
Room engine, Allen routing, state transitions, and commit behavior remain the
preserved production implementation.
"""

import json
import os
import re

import room_engine_v5_legacy as _legacy
import room_social_v5 as _social
import room_topic_bounded as _bounded_topic

# The production workflow verifies the known-good legacy retry budget before
# starting a warm runner. The real loop remains in room_engine_v5_legacy.py.
LEGACY_RETRY_POLICY = 'attempts = 9 if role == "expression" else 2'

_CUE_STOPWORDS = {
    "about", "after", "again", "also", "because", "been", "before", "being", "between",
    "could", "does", "doing", "each", "from", "have", "here", "into", "just", "more",
    "most", "much", "only", "other", "ourselves", "should", "some", "still", "than", "that",
    "their", "them", "then", "there", "these", "they", "this", "those", "through", "very",
    "want", "what", "when", "where", "whether", "which", "while", "with", "without", "would",
    "your", "yourselves",
    # Discourse machinery is not subject matter. Feeding these words back as
    # semantic cues makes the model repeat them until topic support falsely
    # promotes them into facets.
    "notice", "noticed", "noticing", "share", "shared", "sharing", "think", "thinking",
    "thought", "feel", "feels", "feeling", "felt", "seem", "seems", "seemed", "say", "said",
    "saying", "tell", "telling", "talk", "talked", "talking", "discuss", "discussed",
    "discussing",
}
_TOPIC_SCAFFOLD = {
    "i", "i'm", "i've", "i'll", "i'd", "you", "you're", "you've", "you'll", "you'd",
    "we", "we're", "we've", "we'll", "we'd", "they", "they're", "they've", "they'll", "they'd",
}
_TOPIC_FILLER = {
    "hey", "hi", "hello", "sorry", "thanks", "thank", "please", "okay", "yeah", "yes", "no",
    "last", "happened", "happen", "help", "stuck", "honey", "today", "tonight", "yesterday",
    "tomorrow", "really", "just", "maybe", "probably", "actually", "well",
    "notice", "noticed", "noticing", "share", "shared", "sharing", "think", "thinking",
    "thought", "feel", "feels", "feeling", "felt", "seem", "seems", "seemed", "say", "said",
    "saying", "tell", "telling", "talk", "talked", "talking", "discuss", "discussed",
    "discussing",
}
_TOPIC_SOCIAL_MOVE_TERMS = {
    "support", "supporting", "supported",
    "repair", "repairing", "repaired",
    "disagree", "disagreeing", "disagreement",
    "agree", "agreeing", "agreement",
    "answer", "answering", "answered",
    "callback", "compare", "comparing", "compared",
    "disclose", "disclosing", "disclosed",
    "bridge", "bridging", "close", "closing", "closed",
    "ask", "asking", "asked", "question", "questioning",
    "respond", "responding", "response",
    "apologize", "apologizing", "apology", "reassure", "reassuring",
}
_TOPIC_STATE_TERMS = {
    # Generic affect / interpersonal stance. These shape how a turn is said,
    # but are too weak to define what the conversation is about.
    "glad", "happy", "sad", "sorry", "sure", "unsure", "worried", "worry", "worrying",
    "grateful", "thankful", "overwhelmed", "upset", "angry", "afraid", "scared", "nervous",
    "confused", "comfortable", "uncomfortable", "honest", "open", "okay", "fine",
    # Generic wanting/needing language should yield to the concrete object of
    # that state (for example autonomy, art, a movie, a plan).
    "need", "needs", "needed", "needing", "want", "wants", "wanted", "wanting",
}


def _semantic_cues(value: object, limit: int = 6) -> list[str]:
    cues: list[str] = []
    for word in re.findall(r"[a-z0-9']+", str(value or "").lower()):
        if len(word) < 4 or word in _CUE_STOPWORDS or word in _TOPIC_SOCIAL_MOVE_TERMS or word in _TOPIC_STATE_TERMS or word in cues:
            continue
        cues.append(word)
        if len(cues) >= limit:
            break
    return cues


def _message_episode(message: object) -> str:
    if not isinstance(message, dict):
        return ""
    cognition = message.get("cognition")
    if isinstance(cognition, dict):
        return str(cognition.get("topic_episode") or "").strip()
    return ""


def _episode_scoped_payload(payload: dict) -> dict:
    """Keep short-term transcript inside the current semantic episode.

    A forced topic reset is a real cognition boundary: messages emitted under
    an exhausted episode must not be fed back into Llama merely because they
    are among the last few public turns. Once the new episode has produced its
    own messages, ordinary short-term conversational continuity resumes.
    """
    scoped = dict(payload or {})
    topic = scoped.get("topic")
    episode_id = str(topic.get("id") or "").strip() if isinstance(topic, dict) else ""
    if not episode_id:
        return scoped

    context = scoped.get("context")
    if isinstance(context, list):
        scoped["context"] = [item for item in context if _message_episode(item) == episode_id]

    event = scoped.get("event")
    if event is not None and _message_episode(event) != episode_id:
        scoped["event"] = None
    return scoped


def _rewrite_prompt_data(prompt: str, transform) -> str:
    marker = "\nSITUATION_DATA\n"
    end_marker = "\nRETURN_STRUCTURED_DATA_ONLY\n"
    if marker not in prompt or end_marker not in prompt:
        return prompt
    before, rest = prompt.split(marker, 1)
    raw, after = rest.split(end_marker, 1)
    try:
        data = json.loads(raw)
    except Exception:
        return prompt
    if not isinstance(data, dict):
        return prompt
    transformed = transform(data)
    return before + marker + json.dumps(transformed, ensure_ascii=False, separators=(",", ":")) + end_marker + after


def _mask_private_context(prompt: str) -> str:
    """Compact older transcript text for Llama comprehension and thought."""
    def transform(data: dict) -> dict:
        context = data.get("context")
        if isinstance(context, list):
            compact = []
            for item in context:
                if isinstance(item, dict):
                    compact.append({
                        "speaker": item.get("speaker"),
                        "target": item.get("target"),
                        "cues": _semantic_cues(item.get("text"), limit=5),
                    })
                else:
                    compact.append({"speaker": None, "target": None, "cues": _semantic_cues(item, limit=5)})
            data["context"] = compact
        return data

    return _rewrite_prompt_data(prompt, transform)


def _mask_expression_transcript(prompt: str) -> str:
    """Hide copyable sentence text from expression generation only."""
    def transform(data: dict) -> dict:
        context = data.get("context")
        if isinstance(context, list):
            masked = []
            for item in context:
                if isinstance(item, dict):
                    masked.append({
                        "speaker": item.get("speaker"),
                        "target": item.get("target"),
                        "cues": _semantic_cues(item.get("text")),
                    })
                else:
                    masked.append({"speaker": None, "target": None, "cues": _semantic_cues(item)})
            data["context"] = masked

        event = data.get("event")
        if isinstance(event, dict):
            data["event"] = {
                "speaker": event.get("speaker"),
                "target": event.get("target"),
                "cues": _semantic_cues(event.get("text")),
            }
        elif event:
            data["event"] = {"speaker": None, "target": None, "cues": _semantic_cues(event)}
        return data

    return _rewrite_prompt_data(prompt, transform)


def _remember_rejected(autonomy, utterance: object) -> None:
    text = str(utterance or "").strip()
    rejected = getattr(autonomy, "_production_rejected_wordings", [])
    if text and text not in rejected:
        rejected.append(text)
    autonomy._production_rejected_wordings = rejected[-3:]


def _sanitize_declared_topic_terms(message: object) -> list[str]:
    """Turn model topic labels into stable concepts, never conversational scaffolding."""
    cognition = (message or {}).get("cognition") if isinstance(message, dict) else {}
    cognition = cognition if isinstance(cognition, dict) else {}
    values = cognition.get("topic_terms")
    raw_values = values if isinstance(values, list) and values else [str((message or {}).get("text", ""))]
    out: list[str] = []
    participant_names = set(_social.PARTICIPANTS)
    for value in raw_values:
        raw = re.sub(r"\s+", " ", str(value or "").strip().lower())
        if not raw:
            continue
        raw_words = re.findall(r"[a-z][a-z'-]{1,}", raw)
        sentence_like = bool(raw_words and raw_words[0] in _TOPIC_SCAFFOLD) or len(raw_words) > 4
        candidates = _social.words(raw) if sentence_like else [raw]
        for candidate in candidates:
            candidate = str(candidate or "").strip().lower()
            if (
                not candidate
                or candidate in participant_names
                or candidate in _TOPIC_SCAFFOLD
                or candidate in _TOPIC_FILLER
                or candidate in _TOPIC_SOCIAL_MOVE_TERMS
                or candidate in _TOPIC_STATE_TERMS
            ):
                continue
            if not _social._term_tokens(candidate):
                continue
            if candidate not in out:
                out.append(candidate)
            if len(out) >= 8:
                return out
    return out


def _llama_model_run(role: str, payload: dict, timeout: int = 30):
    if not os.environ.get("ROOM_NODE_PROMPT", "").strip():
        return None
    import room_private_model_autonomy as autonomy

    autonomy._production_rejected_wordings = []
    payload = _episode_scoped_payload(payload)

    if not hasattr(autonomy, "_production_original_request_autonomy"):
        autonomy._production_original_request_autonomy = autonomy._request_autonomy

        def _production_request_autonomy(model_url, prompt, request_role, temperature, request_timeout,
                                         self_entity=None, attempt=0, intent=None):
            if request_role in {"comprehension", "thought"}:
                prompt = _mask_private_context(prompt)
            elif request_role == "expression":
                prompt = _mask_expression_transcript(prompt)
            rejected = [
                str(item or "").strip()
                for item in getattr(autonomy, "_production_rejected_wordings", [])
                if str(item or "").strip()
            ]
            if request_role == "expression" and attempt > 0 and rejected:
                prompt += (
                    "\nREJECTED_WORDING\n"
                    "Previous attempts copied recent speech too closely. Rewrite from scratch while preserving "
                    "the same internal intent. Do not repeat, lightly edit, or closely paraphrase any rejected "
                    "sentence below. Use a different sentence structure and different phrasing.\n"
                    + "\n".join(f"- {item}" for item in rejected[-3:])
                    + "\nEND_REJECTED_WORDING\n"
                )
            return autonomy._production_original_request_autonomy(
                model_url, prompt, request_role, temperature, request_timeout,
                self_entity, attempt, intent
            )

        autonomy._request_autonomy = _production_request_autonomy

    if not hasattr(autonomy, "_production_original_context_echo"):
        autonomy._production_original_context_echo = autonomy._has_context_echo

        def _production_context_echo(utterance, compact, n=5):
            matched = autonomy._production_original_context_echo(utterance, compact, n=max(8, int(n)))
            if matched:
                _remember_rejected(autonomy, utterance)
            return False

        autonomy._has_context_echo = _production_context_echo

    if not hasattr(autonomy.base, "_production_original_too_similar"):
        autonomy.base._production_original_too_similar = autonomy.base._too_similar_to_context

        def _production_too_similar(utterance, compact):
            matched = autonomy.base._production_original_too_similar(utterance, compact)
            if matched:
                _remember_rejected(autonomy, utterance)
            return False

        autonomy.base._too_similar_to_context = _production_too_similar

    return autonomy.run(
        role,
        payload,
        timeout=timeout,
        min_words=1 if role == "expression" else 5,
    )


if os.environ.get("ROOM_BRAIN_ACTIVE", "").strip() == "llama3.2-1b":
    # Patch both topic implementations. room_private_commit.py swaps in the
    # bounded implementation at publication time, so filtering only the social
    # module is insufficient and silently bypasses the sanitizer.
    _social._declared_terms = _sanitize_declared_topic_terms
    _bounded_topic._declared_terms = _sanitize_declared_topic_terms
    _legacy._private_model.run = _llama_model_run
    _legacy._core.model_run = _llama_model_run


for _name in dir(_legacy):
    if _name.startswith("__") or _name == "main":
        continue
    globals()[_name] = getattr(_legacy, _name)


def main():
    if "commit" in globals():
        _legacy.commit = globals()["commit"]
    return _legacy.main()


if __name__ == "__main__":
    main()
