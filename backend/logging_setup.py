"""Log su file + console per debug backend."""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

BACKEND_ROOT = Path(__file__).resolve().parent
LOG_DIR = BACKEND_ROOT / "logs"


def setup_logging() -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / "backend.log"

    logger.remove()
    logger.add(
        sys.stderr,
        level="INFO",
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    )
    logger.add(
        log_file,
        level="DEBUG",
        rotation="10 MB",
        retention=10,
        encoding="utf-8",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
    )
    logger.info("Log file: {}", log_file)
    return log_file
