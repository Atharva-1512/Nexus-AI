"""
NEXUS AI — Structured Logging Configuration
JSON-formatted structured logs for production; human-readable for development.
"""

import logging
import sys
from typing import Any

from app.core.config import settings


class _JsonFormatter(logging.Formatter):
    """
    Emit logs as JSON lines for machine-readable production output.
    Integrates cleanly with log aggregation tools (ELK, Loki, CloudWatch).
    """

    def format(self, record: logging.LogRecord) -> str:
        import json
        import traceback

        log_entry: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Attach exception info if present
        if record.exc_info:
            log_entry["exception"] = traceback.format_exception(*record.exc_info)

        # Attach any extra fields passed via logging.extra
        for key, value in record.__dict__.items():
            if key not in {
                "msg", "args", "levelname", "levelno", "pathname", "filename",
                "module", "exc_info", "exc_text", "stack_info", "lineno",
                "funcName", "created", "msecs", "relativeCreated", "thread",
                "threadName", "processName", "process", "name", "message",
            }:
                if not key.startswith("_"):
                    log_entry[key] = value

        return json.dumps(log_entry, default=str, ensure_ascii=False)


class _DevFormatter(logging.Formatter):
    """Human-readable coloured formatter for development."""

    COLORS = {
        "DEBUG":    "\033[36m",   # Cyan
        "INFO":     "\033[32m",   # Green
        "WARNING":  "\033[33m",   # Yellow
        "ERROR":    "\033[31m",   # Red
        "CRITICAL": "\033[35m",   # Magenta
    }
    RESET = "\033[0m"
    BOLD  = "\033[1m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.RESET)
        level = f"{color}{self.BOLD}{record.levelname:<8}{self.RESET}"
        name  = f"\033[34m{record.name}{self.RESET}"
        msg   = record.getMessage()
        base  = f"{self.formatTime(record)} | {level} | {name} | {msg}"

        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)

        return base


def setup_logging() -> None:
    """
    Configure the root logger.
    - Development: human-readable coloured console output.
    - Production:  JSON structured output to stdout.
    """
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stdout)

    if settings.is_development:
        handler.setFormatter(_DevFormatter(datefmt="%H:%M:%S"))
    else:
        handler.setFormatter(_JsonFormatter(datefmt="%Y-%m-%dT%H:%M:%S"))

    # Remove any existing handlers from root logger to avoid duplication
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    # Silence overly verbose third-party loggers
    for noisy in ("uvicorn.access", "httpx", "httpcore", "kafka"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("fastapi").setLevel(log_level)
