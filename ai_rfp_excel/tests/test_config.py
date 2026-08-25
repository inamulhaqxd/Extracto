import os
from pathlib import Path

from ai_rfp_excel.app.config import Settings


def test_settings_loads_defaults() -> None:
    settings = Settings()
    assert settings.APP_NAME == "AI RFP Excel Generator"
    assert settings.DEBUG is True
    assert settings.POSTGRES_PORT == 5432


def test_settings_env_override(monkeypatch: object) -> None:
    import pytest

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("APP_NAME", "Test App")
    monkeypatch.setenv("DEBUG", "false")

    settings = Settings()
    assert settings.APP_NAME == "Test App"
    assert settings.DEBUG is False

    monkeypatch.undo()


def test_allowed_extensions_list() -> None:
    settings = Settings()
    extensions = settings.ALLOWED_EXTENSIONS_LIST
    assert ".pdf" in extensions
    assert ".xlsx" in extensions
    assert ".xls" in extensions


def test_ensure_data_dirs(tmp_path: Path) -> None:
    settings = Settings()
    settings.UPLOAD_DIR = str(tmp_path / "uploads")
    settings.EXTRACTED_DIR = str(tmp_path / "extracted")
    settings.IMAGES_DIR = str(tmp_path / "images")
    settings.OCR_DIR = str(tmp_path / "ocr")
    settings.PROCESSED_DIR = str(tmp_path / "processed")
    settings.GENERATED_DIR = str(tmp_path / "generated")

    settings.ensure_data_dirs()

    assert (tmp_path / "uploads").is_dir()
    assert (tmp_path / "extracted").is_dir()
    assert (tmp_path / "images").is_dir()
    assert (tmp_path / "ocr").is_dir()
    assert (tmp_path / "processed").is_dir()
    assert (tmp_path / "generated").is_dir()
