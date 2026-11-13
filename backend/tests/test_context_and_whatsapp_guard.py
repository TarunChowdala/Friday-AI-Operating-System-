import unittest
from unittest.mock import AsyncMock, patch

from app.agents.router import _deterministic_route, AgentRouter
from app.agents.researcher import _is_conversational_or_unclear, _is_followup


class ContextAndWhatsAppGuardTests(unittest.IsolatedAsyncioTestCase):
    def test_followup_queries_recognized_as_not_unclear(self):
        followups = [
            "Yeah, yeah, what happened exactly? I just wanted to know.",
            "I just want to know what happened to that company",
            "tell me more about it",
            "why did the CEO resign?",
            "what happened to that company",
            "give me the full picture",
            "what did they find in the investigation",
        ]
        for f in followups:
            with self.subTest(query=f):
                self.assertTrue(_is_followup(f))
                self.assertFalse(_is_conversational_or_unclear(f))

    def test_conversational_meta_routed_to_planner(self):
        meta_queries = [
            "what did I just said?",
            "what did I say",
            "what was that",
            "what do you mean",
            "what contacts me",
        ]
        for q in meta_queries:
            with self.subTest(query=q):
                route = _deterministic_route(q)
                self.assertEqual(route, "planner")

    def test_whatsapp_not_opened_for_casual_mentions(self):
        # Queries that should NEVER deterministically route to browser_executor
        non_browser = [
            "What contacts me?",
            "what did I just said?",
            "why did you open that?",
            "what do you mean by contactswing?",
        ]
        for q in non_browser:
            with self.subTest(query=q):
                route = _deterministic_route(q)
                self.assertNotEqual(route, "browser_executor")


if __name__ == "__main__":
    unittest.main()

