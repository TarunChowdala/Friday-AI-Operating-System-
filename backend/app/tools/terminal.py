"""Run shell commands with permission checks for dangerous operations."""
import os
import re
import subprocess
from langchain_core.tools import tool
from app.core.logger import get_logger

logger = get_logger(__name__)

# Expand ~ even inside quotes. bash does not expand "~/Downloads/file".
_TILDE_RE = re.compile(r"(?<!\w)~(?:/[^\s\"']*)?")


def expand_command_homes(command: str) -> str:
    return _TILDE_RE.sub(lambda m: os.path.expanduser(m.group(0)), command or "")


@tool
def run_terminal_command(command: str, confirmed: bool = False) -> str:
    """Executes a shell/terminal command on the system and returns its output (stdout/stderr).
    Dangerous commands (rm, kill, etc.) will be blocked unless pre-approved via permission system.
    Prefer manage_files for deleting user files — do not guess rm paths."""
    from app.core.permissions import is_dangerous

    command = expand_command_homes(command)
    logger.info(f"Executing terminal command: {command}")

    if is_dangerous(command) and not confirmed:
        return f"NEEDS_PERMISSION:This command is dangerous: {command}"

    try:
        res = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=15)
        out = (res.stdout or "").strip()
        err = (res.stderr or "").strip()
        if res.returncode != 0:
            detail = err or out or "no output"
            return f"Failed: command exited {res.returncode}: {detail[:1000]}"
        if out:
            return f"Command output:\n{out[:1000]}"
        if err:
            return f"Command error:\n{err[:1000]}"
        return "Command executed successfully with no text output."
    except subprocess.TimeoutExpired:
        return "Command timed out after 15 seconds."
    except Exception as e:
        logger.error(f"Failed to execute command '{command}': {e}")
        return f"Failed: execution error: {e}"
