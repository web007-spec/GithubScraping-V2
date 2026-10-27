"""Loguru logging setup."""

import sys
from pathlib import Path

from loguru import logger

from app.config.settings import Settings, get_settings


def setup_logging(settings: Settings | None = None) -> None:
    """Configure console and rotating file logging."""
    settings = settings or get_settings()
    settings.log_dir.mkdir(parents=True, exist_ok=True)

    logger.remove()
    logger.add(
        sys.stderr,
        level=settings.log_level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
        serialize=False,
    )
    logger.add(
        settings.log_dir / "indexer_{time:YYYY-MM-DD}.log",
        level=settings.log_level,
        rotation="00:00",
        retention="30 days",
        compression="zip",
        serialize=True,
        enqueue=True,
    )
