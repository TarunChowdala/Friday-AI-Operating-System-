"""Host OS detection and JUCCE adapter selection."""
from __future__ import annotations

import platform

from app.tools.jucce.adapters import (
    ComputerControlAdapter,
    LinuxComputerUseAdapter,
    UnsupportedComputerControlAdapter,
)


def detect_host_os() -> str:
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    if system == "windows":
        return "windows"
    if system == "linux":
        return "linux"
    return system or "unknown"


def get_computer_control_adapter() -> ComputerControlAdapter:
    host_os = detect_host_os()
    if host_os == "linux":
        return LinuxComputerUseAdapter()
    return UnsupportedComputerControlAdapter(host_os)
