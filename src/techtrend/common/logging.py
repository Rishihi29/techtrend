"""Structured JSON logging (structlog).

Production services emit machine-parseable logs; human-readable console
rendering is enabled automatically for local development.
"""

from __future__ import annotations

import logging
import sys

import structlog

from techtrend.config.settings import get_settings


def configure_logging() -> None:
    settings = get_settings()
    renderer = (
        structlog.dev.ConsoleRenderer()
        if settings.environment == "local"
        else structlog.processors.JSONRenderer()
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
