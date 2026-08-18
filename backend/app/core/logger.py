"""Centralized logging setup."""
import logging
import sys
from datetime import datetime
from pathlib import Path

from app.core.config import get_settings


class _MsFormatter(logging.Formatter):
    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        dt = datetime.fromtimestamp(record.created)
        return dt.strftime("%Y-%m-%d %H:%M:%S.") + f"{int(record.msecs):03d}"


def get_logger(name: str) -> logging.Logger:
    cfg = get_settings()
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, cfg.LOG_LEVEL.upper(), logging.INFO))
    logger.propagate = False

    fmt = _MsFormatter("[%(asctime)s] %(levelname)-8s %(name)s — %(message)s")

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    logger.addHandler(console)

    log_dir = Path(cfg.LOGS_PATH)
    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_dir / "friday.log")
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    return logger
