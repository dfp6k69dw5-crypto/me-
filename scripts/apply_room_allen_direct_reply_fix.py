#!/usr/bin/env python3
from pathlib import Path

path = Path('scripts/room_engine_v5_core.py')
text = path.read_text()
old = '''    elif role == "expression":
        perception = rp(bus_data, entity, "comprehension")["private"].get("social_observation")
        thought = (bus_data.get("recurrent", {}).get(entity, {}) or {}).get("thought", {})
        deliberation = (thought.get("private") or {}).get("deliberation")
        job = conversation_job(entity, key)
        collapsed = context_collapsed(base.get("context"))
        prior_turns = prior_expression_messages(node)
        expression_context = ([] if collapsed else list(base.get("context") or [])[-5:]) + prior_turns
        expression_topic = dict(base.get("topic") or {})
        if collapsed:
            fresh_subject = breakout_subject(key)
            expression_topic.update({
                "root": fresh_subject,
                "current_facet": fresh_subject,
                "facets": [],
                "visited_facets": [],
                "shared_references": [],
                "unresolved": [],
                "status": "active",
            })
        else:
            fresh_subject = None
        if isinstance(deliberation, dict):
            deliberation = dict(deliberation)
            original_goal = str(deliberation.get("new_information_goal") or "").strip()
            if collapsed:
                deliberation["action"] = "BRIDGE"
                deliberation["focus"] = fresh_subject
                original_goal = ""
            deliberation["new_information_goal"] = (original_goal + " " if original_goal else "") + "Distinct contribution: " + job
            deliberation["conversation_job"] = job
        expression = model_run("expression", {
            "entity": entity,
            "profile": P[entity],
            "social_observation": perception,
            "deliberation": deliberation,
            "conversation_job": job,
            "event": expression_context[-1] if expression_context else (None if collapsed else base.get("event")),
            "context": expression_context,
            "topic": expression_topic,
            "partner": base.get("partner"),
            "relationship": base.get("relationship"),
            "mandatory_speech": True,
        })
        ready = float(source["public"].get("readiness", 0.5))
        generation_rank = int(os.environ.get("ROOM_EXPRESSION_RANK", str(ORDER.index(entity))))
        intent = {
'''
new = '''    elif role == "expression":
        perception = rp(bus_data, entity, "comprehension")["private"].get("social_observation")
        thought = (bus_data.get("recurrent", {}).get(entity, {}) or {}).get("thought", {})
        deliberation = (thought.get("private") or {}).get("deliberation")
        generation_rank = int(os.environ.get("ROOM_EXPRESSION_RANK", str(ORDER.index(entity))))
        latest_event = base.get("event") if isinstance(base.get("event"), dict) else None
        direct_allen_reply = bool(
            generation_rank == 0
            and base.get("partner") == "allen"
            and latest_event
            and latest_event.get("speaker") == "allen"
        )
        job = "" if direct_allen_reply else conversation_job(entity, key)
        collapsed = False if direct_allen_reply else context_collapsed(base.get("context"))
        prior_turns = [] if direct_allen_reply else prior_expression_messages(node)
        expression_context = ([] if collapsed else list(base.get("context") or [])[-5:]) + prior_turns
        expression_topic = dict(base.get("topic") or {})
        if collapsed:
            fresh_subject = breakout_subject(key)
            expression_topic.update({
                "root": fresh_subject,
                "current_facet": fresh_subject,
                "facets": [],
                "visited_facets": [],
                "shared_references": [],
                "unresolved": [],
                "status": "active",
            })
        else:
            fresh_subject = None
        if isinstance(deliberation, dict):
            deliberation = dict(deliberation)
            original_goal = str(deliberation.get("new_information_goal") or "").strip()
            if direct_allen_reply:
                deliberation["action"] = "ANSWER"
                deliberation["preferred_partner"] = "allen"
                deliberation["new_information_goal"] = ""
                deliberation.pop("conversation_job", None)
            else:
                if collapsed:
                    deliberation["action"] = "BRIDGE"
                    deliberation["focus"] = fresh_subject
                    original_goal = ""
                deliberation["new_information_goal"] = (original_goal + " " if original_goal else "") + "Distinct contribution: " + job
                deliberation["conversation_job"] = job
        expression = model_run("expression", {
            "entity": entity,
            "profile": P[entity],
            "social_observation": perception,
            "deliberation": deliberation,
            "conversation_job": job,
            "event": expression_context[-1] if expression_context else (None if collapsed else base.get("event")),
            "context": expression_context,
            "topic": expression_topic,
            "partner": base.get("partner"),
            "relationship": base.get("relationship"),
            "mandatory_speech": True,
        })
        if direct_allen_reply and isinstance(expression, dict):
            expression = dict(expression)
            expression["target"] = "allen"
            expression["move"] = "answer"
        ready = float(source["public"].get("readiness", 0.5))
        intent = {
'''
if old not in text:
    raise SystemExit('expected expression routing block not found')
text = text.replace(old, new, 1)
path.write_text(text)
print('patched Allen rank-0 direct reply routing')
