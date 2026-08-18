"""System info and maintenance — RAM, CPU, disk, cache, cleanup."""
import os
import shutil
import subprocess
from pathlib import Path

import psutil
from langchain_core.tools import tool
from app.core.logger import get_logger

logger = get_logger(__name__)


def _fmt_bytes(b: int) -> str:
    """Human-readable bytes."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(b) < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"


def _uptime_str() -> str:
    import time
    boot = psutil.boot_time()
    elapsed = int(time.time() - boot)
    h, rem = divmod(elapsed, 3600)
    m, _ = divmod(rem, 60)
    return f"{h}h {m}m"


def _dir_size(path: str) -> int:
    """Total size of a directory in bytes."""
    total = 0
    try:
        for dirpath, _, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                try:
                    total += os.path.getsize(fp)
                except OSError:
                    pass
    except OSError:
        pass
    return total


def _clean_directory_contents(path: Path) -> tuple[int, int]:
    """Delete the contents of a directory. Returns (deleted_entries, failed_entries)."""
    deleted = 0
    failed = 0
    for child in path.iterdir():
        try:
            if child.is_dir() and not child.is_symlink():
                shutil.rmtree(child)
            else:
                child.unlink()
            deleted += 1
        except Exception:
            failed += 1
    return deleted, failed


@tool
def system_info(action: str, confirmed: bool = False) -> str:
    """Get system info or perform maintenance.
    action: 'status', 'ram', 'cpu', 'disk', 'cache', 'clean_cache', 'clean_tmp'."""
    logger.info(f"system_info action={action}")
    action = action.lower().strip()

    if action == "status":
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        cpu = psutil.cpu_percent(interval=0.5)
        return (
            f"RAM: {_fmt_bytes(mem.used)}/{_fmt_bytes(mem.total)} ({mem.percent}% used), "
            f"CPU: {cpu}%, "
            f"Disk: {_fmt_bytes(disk.free)} free of {_fmt_bytes(disk.total)}, "
            f"Uptime: {_uptime_str()}"
        )

    if action == "ram":
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        return (
            f"RAM: {_fmt_bytes(mem.used)} used / {_fmt_bytes(mem.total)} total ({mem.percent}%), "
            f"Available: {_fmt_bytes(mem.available)}, "
            f"Swap: {_fmt_bytes(swap.used)} used / {_fmt_bytes(swap.total)} total"
        )

    if action == "cpu":
        cpu = psutil.cpu_percent(interval=1, percpu=True)
        load = os.getloadavg()
        avg = sum(cpu) / len(cpu) if cpu else 0
        return (
            f"CPU: {avg:.1f}% average across {len(cpu)} cores, "
            f"Load average: {load[0]:.2f} (1m), {load[1]:.2f} (5m), {load[2]:.2f} (15m)"
        )

    if action in ("disk", "storage"):
        partitions = psutil.disk_partitions()
        lines = []
        for p in partitions:
            if "loop" in p.device:
                continue
            try:
                usage = psutil.disk_usage(p.mountpoint)
                lines.append(
                    f"{p.mountpoint}: {_fmt_bytes(usage.free)} free / {_fmt_bytes(usage.total)} ({usage.percent}% used)"
                )
            except PermissionError:
                continue
        return "; ".join(lines) if lines else "Could not read disk info."

    if action == "cache":
        home = Path.home()
        cache_dir = str(home / ".cache")
        tmp_dir = "/tmp"
        cache_size = _dir_size(cache_dir)
        tmp_size = _dir_size(tmp_dir)
        result = f"~/.cache: {_fmt_bytes(cache_size)}, /tmp: {_fmt_bytes(tmp_size)}"
        # Check dnf cache
        try:
            res = subprocess.run(["du", "-sh", "/var/cache/dnf"], capture_output=True, text=True, timeout=5)
            if res.returncode == 0 and res.stdout.strip():
                result += f", DNF cache: {res.stdout.strip().split()[0]}"
        except Exception:
            pass
        return result

    if action == "clean_cache":
        home = Path.home()
        cache_dir = home / ".cache"
        size = _dir_size(str(cache_dir))
        if not confirmed:
            return f"NEEDS_PERMISSION:Delete ~/.cache ({_fmt_bytes(size)})"
        deleted, failed = _clean_directory_contents(cache_dir)
        return (
            f"Cleared ~/.cache. Deleted {deleted} entries"
            + (f", {failed} failed." if failed else ".")
        )

    if action == "clean_tmp":
        tmp_dir = Path("/tmp")
        size = _dir_size(str(tmp_dir))
        if not confirmed:
            return f"NEEDS_PERMISSION:Clean /tmp ({_fmt_bytes(size)})"
        deleted, failed = _clean_directory_contents(tmp_dir)
        return (
            f"Cleaned /tmp. Deleted {deleted} entries"
            + (f", {failed} failed." if failed else ".")
        )

    return f"Unknown system action: {action}. Use: status, ram, cpu, disk, cache, clean_cache, clean_tmp."
