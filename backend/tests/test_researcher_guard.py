import unittest
from app.agents.researcher import _is_conversational_or_unclear, ResearcherAgent


class ResearcherGuardTests(unittest.IsolatedAsyncioTestCase):
    def test_conversational_queries_detected_by_guard(self):
        conversational_queries = [
            "good morning",
            "hello",
            "hey there",
            "hi",
            "who are you",
            "where are you",
            "where's avis",
            "can you keep up with chat?",
            "just greeting you",
            "thank you",
            "hi jarvis",
        ]
        for q in conversational_queries:
            with self.subTest(query=q):
                self.assertTrue(_is_conversational_or_unclear(q))

    def test_real_research_queries_pass_guard(self):
        real_queries = [
            "latest stock price of Apple",
            "cricket world cup winner 2023",
            "who is the prime minister of Canada",
            "weather forecast for Hyderabad tomorrow",
        ]
        for q in real_queries:
            with self.subTest(query=q):
                self.assertFalse(_is_conversational_or_unclear(q))

    async def test_researcher_run_asks_clarification_on_conversational_query(self):
        agent = ResearcherAgent()
        res = await agent.run("good morning jarvis")
        self.assertIn("clarify what you'd like me to search for", res["result"])


if __name__ == "__main__":
    unittest.main()

