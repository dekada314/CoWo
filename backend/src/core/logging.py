import logging
import os
from contextvars import ContextVar, Token
from dataclasses import dataclass
from logging.config import dictConfig
from pathlib import Path
from typing import Any

import structlog

from src.core.settings import LoggingSettings

trace_id_var: ContextVar[str | None] = ContextVar("trace_id", default=None)
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


@dataclass(frozen=True)
class LogContextTokens:
    trace_id: Token[str | None]
    request_id: Token[str | None]


class ErrorOnlyFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno >= logging.ERROR


def inject_log_context(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    trace_id = trace_id_var.get()
    request_id = request_id_var.get()
    if trace_id is not None:
        event_dict["trace_id"] = trace_id
    if request_id is not None:
        event_dict["request_id"] = request_id
    return event_dict


def start_log_context(
    *, trace_id: str, request_id: str | None = None
) -> LogContextTokens:
    return LogContextTokens(
        trace_id=trace_id_var.set(trace_id),
        request_id=request_id_var.set(request_id),
    )


def reset_log_context(tokens: LogContextTokens) -> None:
    request_id_var.reset(tokens.request_id)
    trace_id_var.reset(tokens.trace_id)


def configure_logging(service: str, settings: LoggingSettings) -> None:
    directory = Path(__file__).resolve().parents[3] / "logs"
    directory.mkdir(parents=True, exist_ok=True)
    process_name = f"{service}-{os.getpid()}"
    shared_processors = [
        inject_log_context,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]
    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    formatter = {
        "()": structlog.stdlib.ProcessorFormatter,
        "foreign_pre_chain": shared_processors,
        "processors": [
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
    }
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {
                "error_only": {"()": ErrorOnlyFilter},
            },
            "formatters": {"json": formatter},
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "json",
                    "stream": "ext://sys.stdout",
                },
                "application_file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "formatter": "json",
                    "filename": str(directory / f"{process_name}.jsonl"),
                    "maxBytes": settings.max_bytes,
                    "backupCount": settings.backup_count,
                    "encoding": "utf-8",
                },
                "error_file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "formatter": "json",
                    "filters": ["error_only"],
                    "filename": str(directory / f"{process_name}.error.jsonl"),
                    "maxBytes": settings.max_bytes,
                    "backupCount": settings.backup_count,
                    "encoding": "utf-8",
                },
            },
            "root": {
                "handlers": ["console", "application_file", "error_file"],
                "level": settings.level.upper(),
            },
            "loggers": {
                "aio_pika": {"level": "WARNING"},
                "aiormq": {"level": "WARNING"},
                "botocore": {"level": "WARNING"},
                "httpx": {"level": "WARNING"},
                "taskiq": {"level": "WARNING"},
                "uvicorn.access": {"level": "WARNING"},
            },
        }
    )
