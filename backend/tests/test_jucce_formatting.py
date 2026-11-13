import json
import unittest

from app.tools.jucce.tools import _format_content
from app.agents.executor_common import voice_line


class JucceFormattingTests(unittest.TestCase):
    def test_format_list_windows_from_mcp_dict(self):
        sample_result = {
            "backend": "gnome-shell-extension",
            "error": None,
            "note": "Window list came from GNOME Shell",
            "windows": [
                {"title": "Jarvis - Antigravity IDE", "app_id": "antigravity-ide.desktop", "hidden": False},
                {"title": "Google Chrome", "app_id": "google-chrome.desktop", "hidden": False},
                {"title": "Terminal", "app_id": "org.gnome.Ptyxis.desktop", "hidden": False},
                {"title": "Hidden Background Task", "app_id": "bg.desktop", "hidden": True},
            ],
        }
        formatted = _format_content(sample_result, mcp_tool="list_windows")
        self.assertIn("Open windows (3):", formatted)
        self.assertIn("Jarvis - Antigravity IDE", formatted)
        self.assertIn("Google Chrome", formatted)
        self.assertIn("Terminal", formatted)
        self.assertNotIn("Hidden Background Task", formatted)
        self.assertNotIn("gnome-shell-extension", formatted)

    def test_format_focused_window(self):
        sample_result = {
            "focused_window": {
                "title": "Google Chrome",
                "app_id": "google-chrome.desktop",
            }
        }
        formatted = _format_content(sample_result, mcp_tool="focused_window")
        self.assertEqual(formatted, "Currently focused window: Google Chrome")

    def test_voice_line_never_reads_raw_json_brackets(self):
        raw_json_str = json.dumps({
            "backend": "gnome-shell-extension",
            "error": None,
            "windows": [
                {"title": "VS Code"},
                {"title": "Firefox"},
            ]
        })
        line = voice_line("jucce_observe_desktop", {"action": "list_windows"}, raw_json_str)
        self.assertFalse(line.startswith("{"))
        self.assertIn("VS Code", line)

    def test_format_accessibility_tree(self):
        sample_result = {
            "accessibility_tree": [
                {"name": "gnome-shell", "role": "application"},
                {"name": "Independence day erasers", "role": "heading"},
                {"name": "Search", "role": "push button"},
                {"name": "YouTube", "role": "page tab"},
            ]
        }
        formatted = _format_content(sample_result, mcp_tool="get_app_state")
        self.assertIn("Visible on screen:", formatted)
        self.assertIn("Independence day erasers", formatted)
        self.assertIn("YouTube", formatted)

        voice = voice_line("jucce_get_app_state", {"app_name": "youtube"}, formatted)
        self.assertIn("Independence day erasers", voice)
        self.assertNotIn("denied", voice)


if __name__ == "__main__":
    unittest.main()

