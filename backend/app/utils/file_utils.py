"""Filesystem helpers."""
from pathlib import Path
from typing import Union


def ensure_dir(path: Union[str, Path]) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def safe_join(base: Union[str, Path], *parts: str) -> Path:
    base_path = Path(base).resolve()
    target = (base_path.joinpath(*parts)).resolve()
    if not str(target).startswith(str(base_path)):
        raise ValueError("path escapes base directory")
    return target
