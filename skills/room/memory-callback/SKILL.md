---
name: memory-callback
description: Use when prior events, earlier turns, history, or remembered details are directly relevant.
roles: ["thought", "expression"]
triggers: ["remember", "memory", "earlier", "before", "again", "last time", "childhood", "used to", "history", "past"]
trigger_weight: 1.0
min_score: 1.0
---
Use a callback only when the supporting detail is actually present in available conversation or memory. Connect the earlier detail to the current point and explain why it matters now. Never invent a remembered event to make the exchange feel continuous; uncertainty about memory should remain uncertainty.
