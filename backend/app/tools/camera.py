"""Camera control — open/close GNOME Camera, capture a still photo."""
from __future__ import annotations

import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import psutil
from langchain_core.tools import tool

from app.core.logger import get_logger

logger = get_logger(__name__)

_CAMERA_APPS = ["snapshot", "cheese"]
_CAMERA_PROCESS_NAMES = {"snapshot", "cheese", "org.gnome.Snapshot"}


def _pictures_dir() -> Path:
    pictures = Path.home() / "Pictures"
    pictures.mkdir(parents=True, exist_ok=True)
    return pictures


def _video_devices() -> list[str]:
    devices = []
    for i in range(8):
        path = f"/dev/video{i}"
        if os.path.exists(path):
            devices.append(path)
    return devices


def _capture_photo(out_path: Path) -> str | None:
    """Capture one frame via ffmpeg. Returns error string or None on success."""
    if not shutil.which("ffmpeg"):
        return "ffmpeg is not installed."

    last_err = "No camera device found."
    for device in _video_devices():
        try:
            res = subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-f",
                    "v4l2",
                    "-i",
                    device,
                    "-frames:v",
                    "1",
                    str(out_path),
                ],
                capture_output=True,
                text=True,
                timeout=12,
            )
            if res.returncode == 0 and out_path.exists() and out_path.stat().st_size > 0:
                return None
            last_err = (res.stderr or res.stdout or "capture failed").strip()[:200]
        except Exception as e:
            last_err = str(e)
    return last_err


def _camera_pids() -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            name = (proc.info.get("name") or "").strip()
            if name in _CAMERA_PROCESS_NAMES:
                found.append((proc.pid, name))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return found


@tool
def camera_control(action: str, confirmed: bool = False) -> str:
    """Control the webcam/camera app.
    action: 'open' (launch Camera), 'close' (quit Camera — needs confirmation),
    'photo' / 'click' / 'capture' (take a still photo to Pictures)."""
    action = (action or "").lower().strip()
    logger.info("camera_control action=%s", action)

    if action in ("open", "launch", "start"):
        for cmd in _CAMERA_APPS:
            if not shutil.which(cmd):
                continue
            try:
                subprocess.Popen([cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return f"OK:opened camera app={cmd}"
            except Exception as e:
                logger.error("Failed to open %s: %s", cmd, e)
                continue
        return "Failed: I couldn't find a camera app (snapshot or cheese) on your system."

    if action in ("close", "quit"):
        pids = _camera_pids()
        if not pids:
            return "Failed: the camera app does not appear to be running."
        names = ", ".join(sorted({name for _, name in pids}))
        if not confirmed:
            return f"NEEDS_PERMISSION:Close camera app ({names})"
        closed = 0
        for pid, name in pids:
            try:
                psutil.Process(pid).terminate()
                closed += 1
            except Exception as e:
                logger.error("Failed to close %s pid=%s: %s", name, pid, e)
        if closed:
            return f"OK:closed camera count={closed}"
        return "Failed: I found the camera app but couldn't close it."

    if action in ("photo", "click", "capture", "take_photo", "take photo"):
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        out_path = _pictures_dir() / f"jarvis-{stamp}.jpg"
        err = _capture_photo(out_path)
        if err:
            return f"Failed: I couldn't take a photo. {err}"
        return f"OK:photo path={out_path}"

    return "Unknown camera action. Use: open, close, photo."
