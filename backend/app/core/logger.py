"""Centralized logging setup."""
import logging
import sys
from pathlib import Path

from app.core.config import get_settings


def get_logger(name: str) -> logging.Logger:
    cfg = get_settings()
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, cfg.LOG_LEVEL.upper(), logging.INFO))
    logger.propagate = False

    fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)-8s %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    logger.addHandler(console)

    log_dir = Path(cfg.LOGS_PATH)
    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_dir / "friday.log")
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    return logger
