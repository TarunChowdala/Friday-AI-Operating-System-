"""List and delete files under the user's home directory."""
from __future__ import annotations

import re
from pathlib import Path

from langchain_core.tools import tool

from app.core.logger import get_logger

logger = get_logger(__name__)

_HOME = Path.home().resolve()
_FOLDERS = {
    "downloads": _HOME / "Downloads",
    "download": _HOME / "Downloads",
    "desktop": _HOME / "Desktop",
    "pictures": _HOME / "Pictures",
    "picture": _HOME / "Pictures",
    "documents": _HOME / "Documents",
    "docs": _HOME / "Documents",
    "videos": _HOME / "Videos",
    "music": _HOME / "Music",
    "home": _HOME,
}
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".heic"}
_IMAGE_WORDS = {"image", "photo", "picture", "screenshot", "png", "jpg", "jpeg"}
_STOP = {
    "the",
    "a",
    "an",
    "file",
    "files",
    "folder",
    "from",
    "in",
    "my",
    "that",
    "this",
    "recent",
    "latest",
    "download",
    "downloads",
}


def _alnum(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _tokens(s: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", (s or "").lower()) if t and t not in _STOP]


def _resolve_folder(folder: str) -> Path | str:
    raw = (folder or "downloads").strip() or "downloads"
    key = raw.lower().rstrip("/")
    if key in _FOLDERS:
        path = _FOLDERS[key]
    else:
        path = Path(raw).expanduser()
    try:
        path = path.resolve()
    except Exception as e:
        return f"Failed: bad folder path {raw}: {e}"
    if path != _HOME and _HOME not in path.parents:
        return "Failed: I only touch files inside your home directory."
    if not path.is_dir():
        return f"Failed: folder not found: {path}"
    return path


def _is_image_query(query: str) -> bool:
    toks = {t for t in re.split(r"[^a-z0-9]+", (query or "").lower()) if t}
    return bool(toks & _IMAGE_WORDS)


def _matches(name: str, query: str) -> bool:
    toks = _tokens(query)
    if not toks:
        return True
    hay = _alnum(name)
    return all(_alnum(t) and _alnum(t) in hay for t in toks)


def _list_matches(folder: Path, query: str, images_only: bool) -> list[Path]:
    out: list[Path] = []
    try:
        children = list(folder.iterdir())
    except OSError as e:
        logger.warning("listdir failed for %s: %s", folder, e)
        return []
    for child in children:
        if not child.is_file() or child.is_symlink():
            continue
        if images_only and child.suffix.lower() not in _IMAGE_EXTS:
            continue
        if _matches(child.name, query):
            out.append(child)
    out.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return out


@tool
def manage_files(
    action: str,
    folder: str = "downloads",
    query: str = "",
    newest: bool = False,
    confirmed: bool = False,
) -> str:
    """List or delete files in a user folder. Use this instead of shell rm.

    action: 'list' or 'delete'
    folder: downloads/desktop/pictures/documents/home or an absolute path under home
    query: name fragment like CaptureX. Empty + newest=true picks the most recent file.
    newest: if true, only the most recently modified match
    """
    action = (action or "").lower().strip()
    query = (query or "").strip()
    logger.info(
        "manage_files action=%s folder=%s query=%s newest=%s",
        action,
        folder,
        query,
        newest,
    )

    resolved = _resolve_folder(folder)
    if isinstance(resolved, str):
        return resolved
    folder_path = resolved

    images_only = _is_image_query(query)
    name_query = " ".join(t for t in _tokens(query) if t not in _IMAGE_WORDS)
    matches = _list_matches(folder_path, name_query, images_only)

    if action == "list":
        if not matches:
            kind = "images" if images_only else "files"
            extra = f" matching {name_query}" if name_query else ""
            return f"No {kind}{extra} in {folder_path}."
        shown = matches[:8]
        lines = [f"{p.name}" for p in shown]
        more = len(matches) - len(shown)
        suffix = f" (+{more} more)" if more > 0 else ""
        return f"{len(matches)} match(es) in {folder_path}{suffix}: " + "; ".join(lines)

    if action != "delete":
        return "Failed: unknown action. Use list or delete."

    if not matches:
        kind = "image" if images_only else "file"
        extra = f" matching {name_query}" if name_query else ""
        return f"Failed: no {kind}{extra} in {folder_path}. Nothing deleted."

    if newest or (not name_query and len(matches) > 1):
        targets = [matches[0]]
    elif len(matches) > 1:
        names = "; ".join(p.name for p in matches[:6])
        return (
            f"Failed: {len(matches)} files match. Say which one, or ask for the newest. "
            f"Matches: {names}"
        )
    else:
        targets = matches

    target = targets[0]
    if not confirmed:
        return f"NEEDS_PERMISSION:Delete {target}"

    try:
        target.unlink()
    except PermissionError:
        owner = "unknown"
        try:
            import pwd

            owner = pwd.getpwuid(target.stat().st_uid).pw_name
        except Exception:
            pass
        return (
            f"Failed: {target.name} is owned by {owner}, so I can't delete it as your user. "
            "Nothing was removed."
        )
    except OSError as e:
        return f"Failed: could not delete {target.name}: {e}"

    if target.exists():
        return f"Failed: {target.name} is still there after delete."
    return f"Deleted {target.name} from {folder_path}."
