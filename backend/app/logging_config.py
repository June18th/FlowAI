from __future__ import annotations

import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

import structlog

LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
MAX_BYTES = 50 * 1024 * 1024
BACKUP_COUNT = 30
LOG_FILENAME = "flowagent"

CONSOLE_DATE = "%Y-%m-%d %H:%M:%S"

COLORS = {
    "DEBUG": "\033[36m",     # cyan
    "INFO": "\033[32m",      # green
    "WARNING": "\033[33m",   # yellow
    "ERROR": "\033[31m",     # red
    "CRITICAL": "\033[35m",  # magenta
}
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"


class ColoredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        color = COLORS.get(record.levelname, "")
        orig_levelname = record.levelname
        orig_name = record.name
        record.levelname = f"{BOLD}{color}[{orig_levelname}]{RESET}"
        record.name = f"{DIM}{orig_name}{RESET}"
        result = super().format(record)
        record.levelname = orig_levelname
        record.name = orig_name
        return result

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        orig = super().formatTime(record, datefmt)
        return f"{DIM}{orig}{RESET}"


class DailyRotatingFileHandler(logging.Handler):
    def __init__(self, max_bytes: int = MAX_BYTES, backup_count: int = BACKUP_COUNT):
        super().__init__()
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self._current_date: str = ""
        self._handler: RotatingFileHandler | None = None
        LOG_DIR.mkdir(parents=True, exist_ok=True)

    def _get_filename(self) -> str:
        today = datetime.now().strftime("%Y-%m-%d")
        return str(LOG_DIR / f"{LOG_FILENAME}-{today}.log")

    def _ensure_handler(self) -> None:
        today = datetime.now().strftime("%Y-%m-%d")
        if today != self._current_date:
            if self._handler:
                self._handler.close()
            self._handler = RotatingFileHandler(
                filename=self._get_filename(),
                maxBytes=self.max_bytes,
                backupCount=self.backup_count,
                encoding="utf-8",
            )
            self._handler.setFormatter(self.formatter)
            self._handler.setLevel(self.level)
            self._current_date = today

    def emit(self, record: logging.LogRecord) -> None:
        self._ensure_handler()
        if self._handler:
            self._handler.emit(record)

    def close(self) -> None:
        if self._handler:
            self._handler.close()
        super().close()


def setup_logging() -> None:
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(logging.INFO)

    # Console — plain format
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(ColoredFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt=CONSOLE_DATE,
    ))
    root_logger.addHandler(console_handler)

    # File — daily + size rotation, JSON
    file_handler = DailyRotatingFileHandler()
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(
        '{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}',
        datefmt="%Y-%m-%dT%H:%M:%S",
    ))
    root_logger.addHandler(file_handler)

    # Silence noisy libs
    for lib in ("sqlalchemy.engine", "httpx", "httpcore", "boto3", "botocore", "redis", "asyncio"):
        logging.getLogger(lib).setLevel(logging.WARNING)

    # Structlog wired to stdlib
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


logger: structlog.stdlib.BoundLogger = structlog.get_logger("flowagent")
