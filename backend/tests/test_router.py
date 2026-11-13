import unittest
from app.agents.router import _deterministic_route


class RouterDeterministicTests(unittest.TestCase):
    def test_greetings_and_conversation_route_to_planner(self):
        greetings = [
            "good morning",
            "good morning jarvis",
            "hello",
            "hey there",
            "hi",
            "I just greeted you",
            "i am just greeting you",
            "who are you",
            "what are you",
            "where are you",
            "can you keep up with chat?",
            "are you online",
        ]
        for query in greetings:
            with self.subTest(query=query):
                self.assertEqual(_deterministic_route(query), "planner")

    def test_actions_with_conversational_prefixes_route_to_executor(self):
        action_queries = [
            ("yeah open camera", "desktop_executor"),
            ("ok open notepad", "desktop_executor"),
            ("ok now what you need to do is what are the windows open in current system", "desktop_executor"),
            ("what windows are open", "desktop_executor"),
            ("what app am i in", "desktop_executor"),
            ("pause", "desktop_executor"),
            ("pause the song", "desktop_executor"),
            ("open youtube", "browser_executor"),
            ("search for python in chrome", "browser_executor"),
            ("run command ls -la", "system_executor"),
            ("delete file in downloads", "system_executor"),
            ("ram status", "system_executor"),
        ]
        for query, expected_agent in action_queries:
            with self.subTest(query=query):
                self.assertEqual(_deterministic_route(query), expected_agent)

    def test_explicit_research_routes_to_researcher(self):
        research_queries = [
            "search the web for latest cricket news",
            "who won the cricket match today",
            "what is the latest stock price of Apple",
        ]
        for query in research_queries:
            with self.subTest(query=query):
                self.assertEqual(_deterministic_route(query), "researcher")


if __name__ == "__main__":
    unittest.main()

