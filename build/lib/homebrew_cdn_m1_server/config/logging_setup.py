from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import override


class _DemoteApschedulerSchedulerInfoFilter(logging.Filter):
    @override
    def filter(self, record: logging.LogRecord) -> bool:
        if (
            record.name in {"apscheduler.scheduler", "apscheduler.executors.default"}
            and record.levelno == logging.INFO
        ):
            record.levelno = logging.DEBUG
            record.levelname = logging.getLevelName(logging.DEBUG)
        return True


def configure_logging(level: str, error_log_path: Path) -> None:
    error_log_path.parent.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.handlers.clear()

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    console.setLevel(getattr(logging, level.upper(), logging.INFO))

    error_file = RotatingFileHandler(
        error_log_path,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    error_file.setFormatter(formatter)
    error_file.setLevel(logging.WARNING)

    root.addHandler(console)
    root.addHandler(error_file)

    # APScheduler emits noisy operational logs at INFO; demote them to DEBUG
    # before handler-level filtering so they disappear when LOG_LEVEL=info.
    for logger_name in ("apscheduler.scheduler", "apscheduler.executors.default"):
        logger = logging.getLogger(logger_name)
        logger.filters.clear()
        logger.addFilter(_DemoteApschedulerSchedulerInfoFilter())
