import logging
import pytest
import structlog


from ai_rfp_excel.app.logging import setup_logging


def test_setup_logging_configures_structlog() -> None:
    setup_logging()

    logger = structlog.get_logger("test")
    assert logger is not None


def test_logging_level_respects_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    from ai_rfp_excel.app.config import settings

    monkeypatch.setattr(settings, "LOG_LEVEL", "DEBUG")
    setup_logging()

    root_logger = logging.getLogger()
    assert root_logger.level == logging.DEBUG

    monkeypatch.setattr(settings, "LOG_LEVEL", "INFO")
    setup_logging()

