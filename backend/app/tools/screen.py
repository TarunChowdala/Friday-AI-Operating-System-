"""Screenshot and screen analysis (Wayland + X11 support)."""
import os
import subprocess
from langchain_core.tools import tool
from app.core.logger import get_logger

logger = get_logger(__name__)


@tool
def capture_screen_and_analyze(prompt: str = "Describe what is currently visible on the screen") -> str:
    """Takes a screenshot of the user's desktop screen and uses vision AI to analyze what is currently displayed."""
    logger.info("Capturing screen for analysis...")
    try:
        import tempfile
        from app.core.config import get_settings

        cfg = get_settings()
        temp_dir = tempfile.gettempdir()
        screenshot_path = os.path.join(temp_dir, "friday_screen.png")

        captured = False
        capture_cmds = [
            f"gnome-screenshot -f {screenshot_path}",
            f"import -window root {screenshot_path}",
            f"grim {screenshot_path}",
            f"scrot -o {screenshot_path}",
        ]
        for cmd in capture_cmds:
            try:
                res = subprocess.run(cmd, shell=True, capture_output=True, timeout=10)
                if res.returncode == 0 and os.path.exists(screenshot_path):
                    captured = True
                    break
            except (subprocess.TimeoutExpired, Exception):
                continue

        if not captured:
            try:
                dbus_cmd = (
                    'gdbus call --session --dest org.gnome.Shell '
                    '--object-path /org/gnome/Shell/Screenshot '
                    '--method org.gnome.Shell.Screenshot.Screenshot '
                    f'false true "{screenshot_path}"'
                )
                res = subprocess.run(dbus_cmd, shell=True, capture_output=True, timeout=10)
                if res.returncode == 0 and os.path.exists(screenshot_path):
                    captured = True
            except Exception:
                pass

        if not captured:
            return "Screen capture failed: Install gnome-screenshot (`sudo dnf install gnome-screenshot`) or grim for Wayland."

        if cfg.GEMINI_API_KEY:
            try:
                import google.generativeai as genai
                from PIL import Image

                genai.configure(api_key=cfg.GEMINI_API_KEY)
                model = genai.GenerativeModel('gemini-1.5-flash')
                img = Image.open(screenshot_path)

                response = model.generate_content([
                    f"You are JARVIS AI. The user asks: '{prompt}'. Analyze this screenshot and answer directly.",
                    img
                ])
                return response.text
            except Exception as vision_err:
                logger.error(f"Gemini vision analysis failed: {vision_err}")

        return f"Screenshot saved to {screenshot_path}. (Vision model requires GEMINI_API_KEY configured)."

    except Exception as e:
        logger.error(f"Screen capture failed: {e}")
        return f"Screen capture error: {e}"
