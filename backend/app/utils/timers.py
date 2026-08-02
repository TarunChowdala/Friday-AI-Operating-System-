"""Timing helpers."""
import time
from contextlib import contextmanager
from typing import Iterator


@contextmanager
def stopwatch() -> Iterator[dict]:
    data = {"ms": 0.0}
    start = time.perf_counter()
    try:
        yield data
    finally:
        data["ms"] = (time.perf_counter() - start) * 1000
