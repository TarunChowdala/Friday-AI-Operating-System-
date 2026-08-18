"""Media playback control (YouTube, Spotify, etc.) via playerctl/MPRIS/xdotool."""
import re
import subprocess
from langchain_core.tools import tool
from app.core.logger import get_logger

logger = get_logger(__name__)


def _mpris_player_names() -> list[str]:
    """List active MPRIS media player bus names (Chrome/YouTube, Spotify, etc.)."""
    try:
        res = subprocess.run(
            [
                "dbus-send", "--session", "--dest=org.freedesktop.DBus",
                "--type=method_call", "--print-reply",
                "/org/freedesktop/DBus", "org.freedesktop.DBus.ListNames",
            ],
            capture_output=True, text=True, timeout=5,
        )
        if res.returncode != 0:
            return []
        names: list[str] = []
        for line in res.stdout.splitlines():
            if "org.mpris.MediaPlayer2." not in line:
                continue
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
                "gdbus", "call", "--session", "--dest", player,
                "--object-path", "/org/mpris/MediaPlayer2",
                "--method", "org.freedesktop.DBus.Properties.Get",
                "org.mpris.MediaPlayer2.Player", "PlaybackStatus",
            ],
            capture_output=True, text=True, timeout=5,
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
    """Call org.mpris.MediaPlayer2.Player.<method> on a player."""
    try:
        res = subprocess.run(
            [
                "gdbus", "call", "--session", "--dest", player,
                "--object-path", "/org/mpris/MediaPlayer2",
                "--method", f"org.mpris.MediaPlayer2.Player.{method}",
            ],
            capture_output=True, text=True, timeout=5,
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
        listed = subprocess.run(["playerctl", "-l"], capture_output=True, text=True, timeout=5)
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
            st = subprocess.run(["playerctl", "status"], capture_output=True, text=True, timeout=3)
            status = (st.stdout or "").strip().lower()
            if not status:
                return f"Failed: sent {action}, but I couldn't read player status. Not confirmed."
            if action == "pause" and status != "paused":
                return f"Failed: sent pause, but player still reports '{status}'. Nothing confirmed paused."
            if action in ("play", "resume") and status != "playing":
                return f"Failed: sent play, but player reports '{status}'. Not confirmed."
        return f"OK:{action}"
    except FileNotFoundError:
        return None
    except Exception as e:
        return f"Failed to {action} media via playerctl: {e}"


def _media_via_mpris(action: str) -> str | None:
    """Control Chrome/YouTube/Spotify via MPRIS D-Bus — verify PlaybackStatus."""
    import time

    method_map = {"play": "Play", "resume": "Play", "pause": "Pause", "next": "Next", "previous": "Previous"}
    method = method_map.get(action)
    if not method:
        return None

    players = _mpris_player_names()
    if not players:
        return None

    def _rank(p: str) -> tuple[int, int]:
        status = _mpris_get_status(p)
        playing = 0 if status == "playing" else 1
        browser = 0 if any(x in p.lower() for x in ("chrom", "firefox", "brave", "vivaldi")) else 1
        return (playing, browser)

    preferred = sorted(players, key=_rank)
    last_fail = f"Failed: found media players but could not {action} them."

    for player in preferred:
        before = _mpris_get_status(player)
        if not _mpris_call(player, method):
            continue
        if action == "pause" and before not in ("playing", None):
            pass
        time.sleep(0.3)
        after = _mpris_get_status(player)
        short = player.replace("org.mpris.MediaPlayer2.", "")

        if action == "pause":
            if after == "paused":
                return "OK:pause"
            if before == "playing" and _mpris_call(player, "PlayPause"):
                time.sleep(0.3)
                after = _mpris_get_status(player)
                if after == "paused":
                    return "OK:pause"
            last_fail = f"Failed: told {short} to pause, but status is '{after or 'unknown'}'. Video was not confirmed paused."
            continue

        if action in ("play", "resume"):
            if after == "playing":
                return "OK:play"
            last_fail = f"Failed: told {short} to play, but status is '{after or 'unknown'}'."
            continue

        return f"OK:{action}"

    return last_fail


def _media_via_youtube_window(action: str) -> str | None:
    """Last-resort: focus a YouTube/Chrome window and send space."""
    import shutil
    import time

    if not shutil.which("xdotool"):
        return None
    if action not in ("play", "resume", "pause"):
        return None

    search_terms = ("YouTube", "youtube.com", "Chromium", "Google Chrome", "Firefox", "Brave")
    window_id = None
    for term in search_terms:
        res = subprocess.run(["xdotool", "search", "--name", term], capture_output=True, text=True, timeout=5)
        ids = [x.strip() for x in (res.stdout or "").splitlines() if x.strip()]
        if ids:
            window_id = ids[-1]
            break
    if not window_id:
        return None

    try:
        subprocess.run(["xdotool", "windowactivate", "--sync", window_id], check=True, timeout=5, capture_output=True)
        time.sleep(0.15)
        subprocess.run(["xdotool", "key", "--window", window_id, "space"], check=True, timeout=5, capture_output=True)
        return f"UNCONFIRMED:{action}: I sent play/pause to the browser window, but I couldn't verify the video state."
    except Exception as e:
        return f"Failed to control browser window: {e}"


def _media_via_xdotool(action: str) -> str | None:
    import shutil

    if not shutil.which("xdotool"):
        return None
    key_map = {
        "play": "XF86AudioPlay", "resume": "XF86AudioPlay",
        "pause": "XF86AudioPause", "next": "XF86AudioNext",
        "previous": "XF86AudioPrev", "mute": "XF86AudioMute", "unmute": "XF86AudioMute",
    }
    key = key_map.get(action)
    if not key:
        return f"Failed: unknown media action '{action}'."
    try:
        subprocess.run(["xdotool", "key", key], check=True, timeout=5, capture_output=True)
        return f"UNCONFIRMED:{action}: I sent a media key, but I cannot confirm playback changed."
    except Exception as e:
        return f"Failed to trigger media key {action}: {e}"


@tool
def media_control(action: str) -> str:
    """Controls media playback (YouTube in browser, Spotify, etc.).
    action: 'play', 'resume', 'pause', 'next', 'previous', 'mute', 'unmute'."""
    logger.info(f"Media control action: {action}")
    action = action.lower().strip()
    aliases = {"stop": "pause", "play-pause": "pause", "playpause": "pause", "skip": "next", "forward": "next", "back": "previous"}
    action = aliases.get(action, action)

    if action in ("mute", "unmute"):
        try:
            flag = "mute" if action == "mute" else "unmute"
            subprocess.run(["amixer", "-D", "pulse", "sset", "Master", flag], check=True, capture_output=True, timeout=5)
            return f"OK:{action}"
        except Exception as e:
            xd = _media_via_xdotool(action)
            if xd and xd.startswith("OK:"):
                return xd
            return f"Failed to {action}: {e}"

    last_fail: str | None = None
    last_unconfirmed: str | None = None
    for attempt in (_media_via_playerctl, _media_via_mpris, _media_via_youtube_window, _media_via_xdotool):
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

    if last_fail:
        return last_fail
    if last_unconfirmed:
        return last_unconfirmed.replace("UNCONFIRMED:", "Failed: could not confirm — ", 1)

    return "Failed: I couldn't control playback. Make sure YouTube is playing in the browser, and that playerctl can see it."
