import unittest
from app.agents.executor_common import voice_line, _sanitize_for_voice


class TestVoiceSanitizer(unittest.TestCase):
    def test_sanitize_code_blocks(self):
        text = "### Ran Playwright code\n```js\nawait page.goto('https://www.youtube.com');\n```\n### Page\n- Page URL: https://www.youtube.com/"
        sanitized = _sanitize_for_voice(text)
        self.assertNotIn("```", sanitized)
        self.assertNotIn("###", sanitized)
        self.assertNotIn("await page", sanitized)

    def test_sanitize_raw_json(self):
        text = '{"action": "press_key", "message": "RemoteDesktop Start denied", "ok": false}'
        sanitized = _sanitize_for_voice(text)
        self.assertNotIn("{", sanitized)
        self.assertNotIn("}", sanitized)
        self.assertNotIn('"action"', sanitized)
        self.assertIn("denied", sanitized.lower())

    def test_playwright_navigate_voice_line(self):
        raw_playwright = "### Ran Playwright code\n```js\nawait page.goto('https://www.youtube.com');\n```\n### Page\n- Page URL: https://www.youtube.com/\n- Page Title: YouTube"
        voice = voice_line("playwright_navigate", {"url": "https://www.youtube.com"}, raw_playwright)
        self.assertNotIn("###", voice)
        self.assertNotIn("```", voice)
        self.assertNotIn("await", voice)
        self.assertIn("YouTube", voice)

    def test_jucce_press_key_failure_voice_line(self):
        raw_jucce_err = '{"action": "press_key", "implemented": true, "message": "Input was not sent because the remote desktop portal could not start; input was not replayed through ydotool: RemoteDesktop Start denied or cancelled with response code 1", "ok": false, "received": {"app_id": null, "key": "ctrl+t"}}'
        voice = voice_line("jucce_press_key", {"key": "ctrl+t"}, raw_jucce_err)
        self.assertNotIn("{", voice)
        self.assertNotIn("}", voice)
        self.assertNotIn('"action"', voice)
        self.assertIn("denied", voice.lower())
        self.assertIn("ctrl+t", voice)

    def test_jucce_press_key_success_voice_line(self):
        voice = voice_line("jucce_press_key", {"key": "ctrl+t"}, "OK:press_key completed")
        self.assertEqual(voice, "Pressed ctrl+t, Sir.")

    def test_new_tab_routing(self):
        from app.agents.router import _deterministic_route
        route = _deterministic_route("Already chrome is open, just open a new tab")
        self.assertEqual(route, "browser_executor")


if __name__ == "__main__":
    unittest.main()

