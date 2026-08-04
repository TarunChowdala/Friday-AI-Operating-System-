import subprocess
import re
from langchain_core.tools import tool
from app.core.logger import get_logger

logger = get_logger(__name__)

@tool
def change_volume(level: int) -> str:
    """Changes the system volume. Use this when the user asks to increase, decrease, or set the volume. The level must be an integer between 0 and 100."""
    logger.info(f"Changing volume to {level}%")
    try:
        # Works on most modern Linux systems (PulseAudio/PipeWire)
        subprocess.run(["amixer", "-D", "pulse", "sset", "Master", f"{level}%"], check=True)
        return f"Successfully set volume to {level}%."
    except Exception as e:
        logger.error(f"Failed to change volume: {e}")
        return f"Failed to set volume: {e}"

@tool
def open_application(app_name: str) -> str:
    """Opens a desktop application on the user's computer. The app_name should be a lowercase system command (e.g., 'google-chrome', 'spotify', 'code', 'gnome-terminal')."""
    logger.info(f"Opening application: {app_name}")
    try:
        # Run in background so it doesn't block FRIDAY
        subprocess.Popen([app_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"Successfully opened {app_name}."
    except FileNotFoundError:
        logger.error(f"Application not found: {app_name}")
        return f"I couldn't find an application named {app_name} on your system."
    except Exception as e:
        logger.error(f"Failed to open {app_name}: {e}")
        return f"Failed to open {app_name}."


def _open_in_browser(target_url: str):
    """Helper to open URL cleanly in existing running Chrome window or default browser without profile prompt."""
    try:
        # First attempt google-chrome command directly so it reuses active open Chrome profile window
        subprocess.Popen(["google-chrome", target_url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        # Fallback to xdg-open or python webbrowser module
        try:
            subprocess.Popen(["xdg-open", target_url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            import webbrowser
            webbrowser.open(target_url)

@tool
def open_url(url: str) -> str:
    """Opens a specified URL in the default web browser (e.g. Chrome)."""
    logger.info(f"Opening URL: {url}")
    try:
        if not url.startswith("http://") and not url.startswith("https://"):
            url = f"https://{url}"
        _open_in_browser(url)
        return f"Successfully opened {url} in browser."
    except Exception as e:
        logger.error(f"Failed to open URL {url}: {e}")
        return f"Failed to open URL: {e}"


@tool
def search_google(query: str) -> str:
    """Searches Google in the user's active/default browser window for the given query."""
    logger.info(f"Searching Google for: {query}")
    try:
        import urllib.parse
        encoded_query = urllib.parse.quote(query)
        url = f"https://www.google.com/search?q={encoded_query}"
        _open_in_browser(url)
        return f"Successfully opened Google search for '{query}'."
    except Exception as e:
        logger.error(f"Failed to search Google for {query}: {e}")
        return f"Failed to search Google: {e}"


@tool
def play_youtube(query: str) -> str:
    """Searches YouTube and directly plays the top matching video in the browser."""
    logger.info(f"Playing YouTube query: {query}")
    try:
        import urllib.parse
        import urllib.request
        import re

        encoded_query = urllib.parse.quote(query)
        search_url = f"https://www.youtube.com/results?search_query={encoded_query}"
        
        # Fetch the HTML of YouTube search results page to get top video ID
        req = urllib.request.Request(
            search_url, 
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        html = urllib.request.urlopen(req).read().decode('utf-8')
        
        # Find video IDs in page source
        video_ids = re.findall(r"watch\?v=(\w{11})", html)
        
        if video_ids:
            # First match is top search result!
            direct_video_url = f"https://www.youtube.com/watch?v={video_ids[0]}"
            logger.info(f"Top YouTube video found: {direct_video_url}")
            _open_in_browser(direct_video_url)
            return f"Playing top video for '{query}' on YouTube."
        else:
            # Fallback to search results page if extraction fails
            _open_in_browser(search_url)
            return f"Opened YouTube search for '{query}'."

    except Exception as e:
        logger.error(f"Failed to play YouTube video for {query}: {e}")
        # Fallback to search page
        try:
            encoded_query = urllib.parse.quote(query)
            _open_in_browser(f"https://www.youtube.com/results?search_query={encoded_query}")
            return f"Opened YouTube search for '{query}'."
        except Exception:
            return f"Failed to play YouTube video: {e}"


@tool
def run_terminal_command(command: str) -> str:
    """Executes a safe shell/terminal command on the system and returns its output (stdout/stderr)."""
    logger.info(f"Executing terminal command: {command}")
    try:
        # Run command with a 15-second timeout
        res = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=15)
        out = res.stdout.strip()
        err = res.stderr.strip()
        if out:
            return f"Command output:\n{out[:1000]}"
        elif err:
            return f"Command error:\n{err[:1000]}"
        return "Command executed successfully with no text output."
    except subprocess.TimeoutExpired:
        return "Command timed out after 15 seconds."
    except Exception as e:
        logger.error(f"Failed to execute command '{command}': {e}")
        return f"Execution error: {e}"


@tool
def media_control(action: str) -> str:
    """Controls media playback. action can be: 'play', 'pause', 'next', 'previous', 'mute', 'unmute'."""
    logger.info(f"Media control action: {action}")
    action = action.lower().strip()
    try:
        # Try playerctl first (works across Spotify, Chrome, VLC, Rhythmbox, etc.)
        cmd_map = {
            "play": ["playerctl", "play-pause"],
            "pause": ["playerctl", "pause"],
            "next": ["playerctl", "next"],
            "previous": ["playerctl", "previous"],
            "mute": ["amixer", "-D", "pulse", "sset", "Master", "mute"],
            "unmute": ["amixer", "-D", "pulse", "sset", "Master", "unmute"]
        }
        cmd = cmd_map.get(action, ["playerctl", "play-pause"])
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"Successfully executed media action: {action}."
    except Exception:
        # Fallback to xdotool key events if playerctl is not installed
        try:
            key_map = {
                "play": "XF86AudioPlay",
                "pause": "XF86AudioPause",
                "next": "XF86AudioNext",
                "previous": "XF86AudioPrev",
                "mute": "XF86AudioMute",
                "unmute": "XF86AudioMute"
            }
            key = key_map.get(action, "XF86AudioPlay")
            subprocess.run(["xdotool", "key", key], check=True)
            return f"Successfully triggered media key: {action}."
        except Exception as e:
            return f"Failed to execute media control action: {e}"


@tool
def clipboard_control(action: str, text: str = "") -> str:
    """Gets or sets the system clipboard content. action can be 'get' or 'set'."""
    logger.info(f"Clipboard action: {action}")
    try:
        if action.lower() == "get":
            # Read from clipboard via xclip / xsel / powershell
            res = subprocess.run(["xclip", "-selection", "clipboard", "-o"], capture_output=True, text=True)
            if res.returncode == 0 and res.stdout:
                return f"Clipboard content: {res.stdout.strip()}"
            res_sel = subprocess.run(["xsel", "-b", "-o"], capture_output=True, text=True)
            if res_sel.returncode == 0 and res_sel.stdout:
                return f"Clipboard content: {res_sel.stdout.strip()}"
            return "Clipboard is empty or xclip/xsel is unavailable."
        elif action.lower() == "set":
            if not text:
                return "No text provided to copy to clipboard."
            p = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE)
            p.communicate(input=text.encode('utf-8'))
            return f"Copied text to clipboard: '{text[:50]}...'"
        return "Invalid clipboard action. Use 'get' or 'set'."
    except Exception as e:
        logger.error(f"Clipboard error: {e}")
        return f"Clipboard error: {e}"


@tool
def capture_screen_and_analyze(prompt: str = "Describe what is currently visible on the screen") -> str:
    """Takes a screenshot of the user's desktop screen and uses vision AI to analyze what is currently displayed."""
    logger.info("Capturing screen for analysis...")
    try:
        import os
        import tempfile
        from app.core.config import get_settings

        cfg = get_settings()
        temp_dir = tempfile.gettempdir()
        screenshot_path = os.path.join(temp_dir, "friday_screen.png")

        # Capture desktop screenshot using scrot, gnome-screenshot, or import
        captured = False
        for cmd in [
            f"scrot -o {screenshot_path}",
            f"gnome-screenshot -f {screenshot_path}",
            f"import -window root {screenshot_path}"
        ]:
            res = subprocess.run(cmd, shell=True, capture_output=True)
            if res.returncode == 0 and os.path.exists(screenshot_path):
                captured = True
                break

        if not captured:
            return "Screen capture failed: Could not find scrot, gnome-screenshot, or ImageMagick on your system."

        # If Gemini API Key exists, pass screenshot image directly to Gemini 1.5 Flash Vision
        if cfg.GEMINI_API_KEY:
            try:
                import google.generativeai as genai
                from PIL import Image

                genai.configure(api_key=cfg.GEMINI_API_KEY)
                model = genai.GenerativeModel('gemini-1.5-flash')
                img = Image.open(screenshot_path)
                
                response = model.generate_content([
                    f"You are FRIDAY AI. The user asks: '{prompt}'. Analyze this screenshot and answer directly.",
                    img
                ])
                return response.text
            except Exception as vision_err:
                logger.error(f"Gemini vision analysis failed: {vision_err}")

        return f"Screenshot saved to {screenshot_path}. (Vision model requires GEMINI_API_KEY configured)."

    except Exception as e:
        logger.error(f"Screen capture failed: {e}")
        return f"Screen capture error: {e}"




