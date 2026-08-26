#!/usr/bin/env python3
from pathlib import Path

p = Path('scripts/room_engine_v5_core.py')
s = p.read_text()
start_marker = '\ndef record(history, discourse, mind, message, node, cycle):'
end_marker = '\n\ndef commit(parts, key):'
start = s.index(start_marker)
end = s.index(end_marker, start)
replacement = r'''
_MEMORY_SCAFFOLD = {
    "i", "i'm", "i've", "i'll", "i'd", "you", "you're", "you've", "you'll", "you'd",
    "we", "we're", "we've", "we'll", "we'd", "they", "they're", "they've", "they'll", "they'd",
    "that's", "there's", "what's", "it's", "this", "that", "these", "those",
}
_MEMORY_SALIENT_MOVES = {"disclose", "repair", "callback", "disagree", "answer", "support"}


def _memory_content_tokens(text):
    return [word for word in toks(text) if word not in _MEMORY_SCAFFOLD]


def _memory_worthy_text(text, move=None):
    """Speech may be public without automatically becoming durable memory."""
    lexical = [w.strip("'-") for w in re.findall(r"[a-z][a-z'-]*", str(text or "").lower())]
    lexical = [w for w in lexical if w]
    if not lexical:
        return False
    content = _memory_content_tokens(text)
    if not content:
        return False
    if len(content) >= 2:
        return True
    if len(lexical) >= 5:
        return True
    return str(move or "").strip().lower() in _MEMORY_SALIENT_MOVES


def _memory_worthy(message):
    cognition = message.get("cognition") if isinstance(message, dict) else {}
    cognition = cognition if isinstance(cognition, dict) else {}
    return _memory_worthy_text(message.get("text", ""), cognition.get("move_type"))


def _prune_memory_state(mind):
    for entity in ORDER:
        state = mind.get("entities", {}).get(entity, {})
        memories = []
        for item in state.get("room_memories", []):
            if not isinstance(item, dict):
                continue
            if _memory_worthy_text(item.get("text", ""), item.get("move")):
                memories.append(item)
        state["room_memories"] = memories[-220:]

        self_history = []
        for item in state.get("self_history", []):
            if not isinstance(item, dict):
                continue
            if _memory_worthy_text(item.get("text", ""), item.get("move")):
                self_history.append(item)
        state["self_history"] = self_history[-220:]


def record(history, discourse, mind, message, node, cycle):
    history.append(message)
    discourse.setdefault("nodes", []).append(node)
    if not node.get("parent"):
        discourse.setdefault("roots", []).append(node["id"])

    _prune_memory_state(mind)
    worthy = _memory_worthy(message)

    entity_state = mind["entities"][message["speaker"]]
    entity_state["spoken"] = int(entity_state.get("spoken", 0)) + 1
    if worthy:
        entity_state.setdefault("self_history", []).append({
            "source": message["id"],
            "text": message["text"],
            "move": message["cognition"]["move_type"],
            "discourse": message["discourse_id"],
            "beat_id": message["beat_id"],
            "topic_episode": message["cognition"].get("topic_episode"),
            "topic_facet": message["cognition"].get("topic_facet"),
        })
        entity_state["self_history"] = entity_state["self_history"][-220:]

    for listener in ORDER:
        memories = mind["entities"][listener].setdefault("room_memories", [])
        if worthy:
            memories.append({
                "source": message["id"],
                "status": "observed",
                "speaker": message["speaker"],
                "text": message["text"][:300],
                "move": message["cognition"].get("move_type"),
                "discourse": message["discourse_id"],
                "beat_id": message["beat_id"],
                "topic_episode": message["cognition"].get("topic_episode"),
            })
            mind["entities"][listener]["room_memories"] = memories[-220:]
        mind["entities"][listener]["last_event"] = message["id"]
    observe_message(mind, message, cycle, {item["id"]: item for item in discourse.get("nodes", [])})
'''
p.write_text(s[:start] + '\n' + replacement.strip('\n') + s[end:])
