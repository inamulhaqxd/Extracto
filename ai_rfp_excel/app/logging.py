import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

import structlog

from ai_rfp_excel.app.config import settings


def setup_logging() -> None:
    log_level: int = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    root_logger.addHandler(console_handler)

    if settings.APP_ENV == "production":
        log_dir = Path("./data/logs")
        log_dir.mkdir(parents=True, exist_ok=True)

        file_handler = TimedRotatingFileHandler(
            filename=log_dir / "app.log",
            when="midnight",
            interval=1,
            backupCount=30,
            encoding="utf-8",
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(logging.Formatter("%(message)s"))
        root_logger.addHandler(file_handler)

        audit_handler = TimedRotatingFileHandler(
            filename=log_dir / "audit.log",
            when="midnight",
            interval=1,
            backupCount=90,
            encoding="utf-8",
        )
        audit_handler.setLevel(logging.INFO)
        audit_handler.setFormatter(logging.Formatter("%(message)s"))
        root_logger.addHandler(audit_handler)


logger = structlog.get_logger()
get_logger = structlog.get_logger

