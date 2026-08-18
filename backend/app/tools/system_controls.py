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
    """Opens a desktop application. Accepts friendly names like 'notepad', 'chrome', 'terminal', 'code', or a real binary name."""
    logger.info(f"Opening application: {app_name}")
    raw = (app_name or "").strip().lower()
    aliases: dict[str, list[str]] = {
        "notepad": ["gnome-text-editor", "gedit", "kate", "mousepad", "xed", "leafpad"],
        "text editor": ["gnome-text-editor", "gedit", "kate", "mousepad"],
        "editor": ["gnome-text-editor", "gedit", "kate"],
        "chrome": ["google-chrome", "google-chrome-stable", "chromium-browser", "chromium"],
        "browser": ["google-chrome", "firefox", "chromium"],
        "terminal": ["gnome-terminal", "kgx", "konsole", "xterm"],
        "code": ["code", "codium"],
        "vscode": ["code", "codium"],
        "spotify": ["spotify"],
    }
    candidates = aliases.get(raw, [raw.replace(" ", "-")])
    last_err = None
    for cmd in candidates:
        try:
            subprocess.Popen([cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            kind = "editor" if raw in ("notepad", "text editor", "editor") or cmd in (
                "gnome-text-editor", "gedit", "kate", "mousepad", "xed", "leafpad"
            ) else "app"
            return f"OK:opened app={cmd} kind={kind} alias={raw or cmd}"
        except FileNotFoundError as e:
            last_err = e
            continue
        except Exception as e:
            logger.error(f"Failed to open {cmd}: {e}")
            last_err = e
            continue
    logger.error(f"Application not found: {app_name} tried={candidates}")
    return f"Failed: I couldn't find an application named {app_name} on your system."


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
        return f"OK:browser url={url}"
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
        return f"OK:browser url={url} query={query}"
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

        encoded_query = urllib.parse.quote(query)
        search_url = f"https://www.youtube.com/results?search_query={encoded_query}"

        req = urllib.request.Request(
            search_url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
        )
        html = urllib.request.urlopen(req).read().decode("utf-8")
        video_ids = re.findall(r"watch\?v=(\w{11})", html)

        if video_ids:
            direct_video_url = f"https://www.youtube.com/watch?v={video_ids[0]}"
            logger.info(f"Top YouTube video found: {direct_video_url}")
            _open_in_browser(direct_video_url)
            return f"OK:youtube query={query} url={direct_video_url}"
        _open_in_browser(search_url)
        return f"OK:youtube_search query={query} url={search_url}"

    except Exception as e:
        logger.error(f"Failed to play YouTube video for {query}: {e}")
        try:
            import urllib.parse

            encoded_query = urllib.parse.quote(query)
            search_url = f"https://www.youtube.com/results?search_query={encoded_query}"
            _open_in_browser(search_url)
            return f"OK:youtube_search query={query} url={search_url}"
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


def _mpris_player_names() -> list[str]:
    """List active MPRIS media player bus names (Chrome/YouTube, Spotify, etc.)."""
    try:
        res = subprocess.run(
            [
                "dbus-send",
                "--session",
                "--dest=org.freedesktop.DBus",
                "--type=method_call",
                "--print-reply",
                "/org/freedesktop/DBus",
                "org.freedesktop.DBus.ListNames",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if res.returncode != 0:
            return []
        names: list[str] = []
        for line in res.stdout.splitlines():
            if "org.mpris.MediaPlayer2." not in line:
                continue
            # dbus-send print-reply lines look like: string "org.mpris.MediaPlayer2.chromium.instance123"
            m = re.search(r'(org\.mpris\.MediaPlayer2\.[^"]+)', line)
            if m:
                names.append(m.group(1))
        return names
    except Exception as e:
        logger.debug("MPRIS list failed: %s", e)
        return []


def _mpris_get_status(player: str) -> str | None:
    """Read PlaybackStatus: Playing | Paused | Stopped."""
    try:
        res = subprocess.run(
            [
                "gdbus",
                "call",
                "--session",
                "--dest",
                player,
                "--object-path",
                "/org/mpris/MediaPlayer2",
                "--method",
                "org.freedesktop.DBus.Properties.Get",
                "org.mpris.MediaPlayer2.Player",
                "PlaybackStatus",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if res.returncode != 0:
            return None
        out = res.stdout or ""
        for token in ("Playing", "Paused", "Stopped"):
            if token in out:
                return token.lower()
        return None
    except Exception as e:
        logger.debug("MPRIS status failed for %s: %s", player, e)
        return None


def _mpris_call(player: str, method: str) -> bool:
    """Call org.mpris.MediaPlayer2.Player.<method> on a player. Returns True on success."""
    try:
        res = subprocess.run(
            [
                "gdbus",
                "call",
                "--session",
                "--dest",
                player,
                "--object-path",
                "/org/mpris/MediaPlayer2",
                "--method",
                f"org.mpris.MediaPlayer2.Player.{method}",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return res.returncode == 0
    except Exception as e:
        logger.debug("MPRIS %s on %s failed: %s", method, player, e)
        return False


def _media_via_playerctl(action: str) -> str | None:
    """Try playerctl. Returns status string, or None if playerctl missing."""
    import shutil
    import time

    if not shutil.which("playerctl"):
        return None

    cmd_map = {
        "play": ["playerctl", "play"],
        "resume": ["playerctl", "play"],
        "pause": ["playerctl", "pause"],
        "next": ["playerctl", "next"],
        "previous": ["playerctl", "previous"],
        "mute": ["amixer", "-D", "pulse", "sset", "Master", "mute"],
        "unmute": ["amixer", "-D", "pulse", "sset", "Master", "unmute"],
    }
    cmd = cmd_map.get(action)
    if not cmd:
        return f"Failed: unknown media action '{action}'."

    try:
        listed = subprocess.run(
            ["playerctl", "-l"], capture_output=True, text=True, timeout=5
        )
        players = [p.strip() for p in (listed.stdout or "").splitlines() if p.strip()]
        if action in ("play", "resume", "pause", "next", "previous") and not players:
            return "Failed: nothing is playing that I can control right now."

        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if res.returncode != 0:
            err = (res.stderr or res.stdout or "").strip()
            if "No players found" in err or "No players" in err:
                return "Failed: nothing is playing that I can control right now."
            return f"Failed to {action} media: {err or 'playerctl error'}."

        if action in ("play", "resume", "pause"):
            time.sleep(0.25)
            st = subprocess.run(
                ["playerctl", "status"], capture_output=True, text=True, timeout=3
            )
            status = (st.stdout or "").strip().lower()
            if not status:
                return (
                    f"Failed: sent {action}, but I couldn't read player status. "
                    "Not confirmed."
                )
            if action == "pause" and status != "paused":
                return (
                    f"Failed: sent pause, but player still reports '{status}'. "
                    "Nothing confirmed paused."
                )
            if action in ("play", "resume") and status != "playing":
                return (
                    f"Failed: sent play, but player reports '{status}'. Not confirmed."
                )
        return f"OK:{action}"
    except FileNotFoundError:
        return None
    except Exception as e:
        return f"Failed to {action} media via playerctl: {e}"


def _media_via_mpris(action: str) -> str | None:
    """Control Chrome/YouTube/Spotify via MPRIS D-Bus — verify PlaybackStatus."""
    import time

    method_map = {
        "play": "Play",
        "resume": "Play",
        "pause": "Pause",
        "next": "Next",
        "previous": "Previous",
    }
    method = method_map.get(action)
    if not method:
        return None

    players = _mpris_player_names()
    if not players:
        return None

    # Prefer currently Playing browser players
    def _rank(p: str) -> tuple[int, int]:
        status = _mpris_get_status(p)
        playing = 0 if status == "playing" else 1
        browser = (
            0
            if any(x in p.lower() for x in ("chrom", "firefox", "brave", "vivaldi"))
            else 1
        )
        return (playing, browser)

    preferred = sorted(players, key=_rank)
    last_fail = f"Failed: found media players but could not {action} them."

    for player in preferred:
        before = _mpris_get_status(player)
        if not _mpris_call(player, method):
            continue
        # Pause on a Stopped/Paused idle instance is a false win — skip non-playing for pause
        if action == "pause" and before not in ("playing", None):
            # still try verify; idle instances often "succeed" without doing anything
            pass
        time.sleep(0.3)
        after = _mpris_get_status(player)
        short = player.replace("org.mpris.MediaPlayer2.", "")

        if action == "pause":
            if after == "paused":
                return f"OK:pause"
            # Try PlayPause as fallback if Pause was a no-op
            if before == "playing" and _mpris_call(player, "PlayPause"):
                time.sleep(0.3)
                after = _mpris_get_status(player)
                if after == "paused":
                    return f"OK:pause"
            last_fail = (
                f"Failed: told {short} to pause, but status is '{after or 'unknown'}'. "
                "Video was not confirmed paused."
            )
            continue

        if action in ("play", "resume"):
            if after == "playing":
                return f"OK:play"
            last_fail = (
                f"Failed: told {short} to play, but status is '{after or 'unknown'}'."
            )
            continue

        # next / previous — accept method success (no reliable status field)
        return f"OK:{action}"

    return last_fail


def _media_via_youtube_window(action: str) -> str | None:
    """Last-resort: focus a YouTube/Chrome window and send space / media keys."""
    import shutil
    import time

    if not shutil.which("xdotool"):
        return None
    if action not in ("play", "resume", "pause"):
        return None

    # Find a likely YouTube / browser window
    search_terms = ("YouTube", "youtube.com", "Chromium", "Google Chrome", "Firefox", "Brave")
    window_id = None
    for term in search_terms:
        res = subprocess.run(
            ["xdotool", "search", "--name", term],
            capture_output=True,
            text=True,
            timeout=5,
        )
        ids = [x.strip() for x in (res.stdout or "").splitlines() if x.strip()]
        if ids:
            window_id = ids[-1]
            break
    if not window_id:
        return None

    try:
        subprocess.run(
            ["xdotool", "windowactivate", "--sync", window_id],
            check=True,
            timeout=5,
            capture_output=True,
        )
        time.sleep(0.15)
        # Space toggles play/pause on YouTube when the player is focused
        subprocess.run(
            ["xdotool", "key", "--window", window_id, "space"],
            check=True,
            timeout=5,
            capture_output=True,
        )
        # Cannot verify without MPRIS — be honest
        return (
            f"UNCONFIRMED:{action}: I sent play/pause to the browser window, "
            "but I couldn't verify the video state. Check if it actually changed."
        )
    except Exception as e:
        return f"Failed to control browser window: {e}"


def _media_via_xdotool(action: str) -> str | None:
    import shutil

    if not shutil.which("xdotool"):
        return None
    key_map = {
        "play": "XF86AudioPlay",
        "resume": "XF86AudioPlay",
        "pause": "XF86AudioPause",
        "next": "XF86AudioNext",
        "previous": "XF86AudioPrev",
        "mute": "XF86AudioMute",
        "unmute": "XF86AudioMute",
    }
    key = key_map.get(action)
    if not key:
        return f"Failed: unknown media action '{action}'."
    try:
        subprocess.run(["xdotool", "key", key], check=True, timeout=5, capture_output=True)
        # Media keys often do nothing for YouTube — never claim confirmed success
        return (
            f"UNCONFIRMED:{action}: I sent a media key, but I cannot confirm "
            "playback changed. Nothing verified."
        )
    except Exception as e:
        return f"Failed to trigger media key {action}: {e}"


@tool
def media_control(action: str) -> str:
    """Controls media playback (YouTube in browser, Spotify, etc.).
    action: 'play', 'resume', 'pause', 'next', 'previous', 'mute', 'unmute'.
    Returns OK:/Failed:/UNCONFIRMED: — never claim success without verification when possible."""
    logger.info(f"Media control action: {action}")
    action = action.lower().strip()
    aliases = {
        "stop": "pause",
        "play-pause": "pause",
        "playpause": "pause",
        "skip": "next",
        "forward": "next",
        "back": "previous",
    }
    action = aliases.get(action, action)

    if action in ("mute", "unmute"):
        try:
            flag = "mute" if action == "mute" else "unmute"
            subprocess.run(
                ["amixer", "-D", "pulse", "sset", "Master", flag],
                check=True,
                capture_output=True,
                timeout=5,
            )
            return f"OK:{action}"
        except Exception as e:
            xd = _media_via_xdotool(action)
            if xd and xd.startswith("OK:"):
                return xd
            return f"Failed to {action}: {e}"

    last_fail: str | None = None
    last_unconfirmed: str | None = None
    for attempt in (
        _media_via_playerctl,
        _media_via_mpris,
        _media_via_youtube_window,
        _media_via_xdotool,
    ):
        out = attempt(action)
        if out is None:
            continue
        if out.startswith("OK:"):
            return out
        if out.startswith("UNCONFIRMED:"):
            last_unconfirmed = out
            continue
        if out.lower().startswith("failed"):
            last_fail = out

    # Prefer hard failure over unconfirmed "success"
    if last_fail:
        return last_fail
    if last_unconfirmed:
        return last_unconfirmed.replace("UNCONFIRMED:", "Failed: could not confirm — ", 1)

    return (
        "Failed: I couldn't control playback. Make sure YouTube is playing in the browser, "
        "and that playerctl can see it (run: playerctl status). Nothing was changed."
    )



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


def _require_xdotool() -> str | None:
    import shutil

    if not shutil.which("xdotool"):
        return (
            "Failed: xdotool is not installed. "
            "Install it with: sudo dnf install xdotool"
        )
    return None


def _focus_window_by_hints(hints: list[str]) -> str | None:
    """Activate the first matching window. Returns window id or None."""
    for hint in hints:
        if not hint:
            continue
        res = subprocess.run(
            ["xdotool", "search", "--name", hint],
            capture_output=True,
            text=True,
            timeout=5,
        )
        ids = [x.strip() for x in (res.stdout or "").splitlines() if x.strip()]
        if not ids:
            continue
        wid = ids[-1]
        subprocess.run(
            ["xdotool", "windowactivate", "--sync", wid],
            check=True,
            timeout=5,
            capture_output=True,
        )
        return wid
    return None


@tool
def type_text(text: str, target_hint: str = "") -> str:
    """Types text into the focused editor/app window (e.g. notepad JARVIS opened).
    Use after opening notepad/editor when the user asks to write or type something.
    target_hint: optional window name hint like 'gedit', 'Text Editor', 'kate'."""
    logger.info("type_text len=%d hint=%s", len(text or ""), target_hint)
    missing = _require_xdotool()
    if missing:
        return missing
    if not (text or "").strip():
        return "Failed: no text provided to type."

    import time

    hints = []
    if target_hint:
        hints.append(target_hint)
    hints.extend(
        [
            "Text Editor",
            "gedit",
            "gnome-text-editor",
            "Kate",
            "Mousepad",
            "Untitled",
            "notepad",
        ]
    )
    try:
        wid = _focus_window_by_hints(hints)
        if not wid:
            return (
                "Failed: I couldn't find the editor window to type into. "
                "Open notepad first, then ask me to write."
            )
        time.sleep(0.25)
        # Clear selection / ensure focus in document body
        subprocess.run(
            ["xdotool", "type", "--clearmodifiers", "--delay", "12", "--", text],
            check=True,
            timeout=120,
            capture_output=True,
        )
        return f"OK:typed chars={len(text)} into window={wid}"
    except Exception as e:
        logger.error("type_text failed: %s", e)
        return f"Failed to type text: {e}"


@tool
def save_document(filename: str = "") -> str:
    """Saves the focused document (Ctrl+S). If filename is provided, types it in the Save dialog and confirms.
    Use after typing into notepad/editor when the user asks to save."""
    logger.info("save_document filename=%r", filename)
    missing = _require_xdotool()
    if missing:
        return missing

    import time

    try:
        hints = [
            "Text Editor",
            "gedit",
            "gnome-text-editor",
            "Kate",
            "Mousepad",
            "Untitled",
            "Save",
        ]
        wid = _focus_window_by_hints(hints)
        if not wid:
            return (
                "Failed: I couldn't find the editor window to save. "
                "Open notepad and write first."
            )
        time.sleep(0.2)
        subprocess.run(
            ["xdotool", "key", "--clearmodifiers", "ctrl+s"],
            check=True,
            timeout=5,
            capture_output=True,
        )
        time.sleep(0.5)
        if filename.strip():
            # Save-As dialog: type name and Enter
            subprocess.run(
                [
                    "xdotool",
                    "type",
                    "--clearmodifiers",
                    "--delay",
                    "12",
                    "--",
                    filename.strip(),
                ],
                check=True,
                timeout=30,
                capture_output=True,
            )
            time.sleep(0.2)
            subprocess.run(
                ["xdotool", "key", "Return"],
                check=True,
                timeout=5,
                capture_output=True,
            )
            return f"OK:saved filename={filename.strip()}"
        return "OK:saved (Ctrl+S sent to focused editor)"
    except Exception as e:
        logger.error("save_document failed: %s", e)
        return f"Failed to save document: {e}"
