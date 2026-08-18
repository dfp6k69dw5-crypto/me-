#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import room_skill_exec as router


class RoomSkillRouterTests(unittest.TestCase):
    def names(self, role: str, text: str):
        selected, available = router.select_skills(role, router._norm(text), "test-cycle")
        self.assertGreaterEqual(available, 7)
        self.assertLessEqual(len(selected), router.MAX_SKILLS)
        return [item["name"] for item in selected]

    def test_technical_context_routes_technical_skill(self):
        self.assertIn("technical-systems", self.names("thought", "The GitHub workflow and AI model are failing on the audio system."))

    def test_emotional_context_routes_attunement(self):
        self.assertIn("emotional-attunement", self.names("comprehension", "She felt hurt and worried about trust in the relationship."))

    def test_unrelated_context_can_route_nothing(self):
        selected, _ = router.select_skills("thought", "lampshade violet corridor", "test-cycle")
        self.assertEqual(selected, [])

    def test_prompt_is_unchanged_when_no_context_match(self):
        env = {
            "ROOM_NODE_PROMPT": "BASE",
            "ROOM_NODE_ID": "1",
            "ROOM_CYCLE_KEY": "test-cycle",
            "ROOM_ATTENTION_AUDIT": "0",
        }
        routed = router.prepare_environment(env, "lampshade violet corridor")
        self.assertEqual(routed["ROOM_NODE_PROMPT"], "BASE")

    def test_selected_skill_is_temporary_and_capped(self):
        env = {
            "ROOM_NODE_PROMPT": "BASE",
            "ROOM_NODE_ID": "1",
            "ROOM_CYCLE_KEY": "test-cycle",
            "ROOM_ATTENTION_AUDIT": "0",
        }
        routed = router.prepare_environment(env, "github computer software system model ai audio physics code evidence cause")
        self.assertTrue(routed["ROOM_NODE_PROMPT"].startswith("BASE\nTEMPORARY_TASK_SKILLS"))
        self.assertLessEqual(len(routed["ROOM_NODE_PROMPT"]) - len("BASE\n"), router.MAX_ADDED_CHARS)


if __name__ == "__main__":
    unittest.main()
