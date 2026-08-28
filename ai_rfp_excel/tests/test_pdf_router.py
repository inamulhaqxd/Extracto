from unittest.mock import patch

from ai_rfp_excel.app.ingestion.models import PageType
from ai_rfp_excel.app.ingestion.pdf.router import PageRouter


def test_router_detect_native_text() -> None:
    router = PageRouter()
    with (
        patch("ai_rfp_excel.app.ingestion.pdf.router.has_text_content", return_value=True),
        patch("ai_rfp_excel.app.ingestion.pdf.router.has_tables", return_value=False),
        patch("ai_rfp_excel.app.ingestion.pdf.router.has_images", return_value=False),
        patch("ai_rfp_excel.app.ingestion.pdf.router.needs_ocr", return_value=False),
    ):
        types = router.detect_page_type("dummy.pdf", 0)
        assert types == [PageType.NATIVE_TEXT]
        assert router.should_extract_text("dummy.pdf", 0) is True
        assert router.should_extract_tables("dummy.pdf", 0) is False
        assert router.should_extract_images("dummy.pdf", 0) is False
        assert router.should_run_ocr("dummy.pdf", 0) is False


def test_router_detect_table() -> None:
    router = PageRouter()
    with (
        patch("ai_rfp_excel.app.ingestion.pdf.router.has_text_content", return_value=False),
        patch("ai_rfp_excel.app.ingestion.pdf.router.has_tables", return_value=True),
        patch("ai_rfp_excel.app.ingestion.pdf.router.has_images", return_value=False),
        patch("ai_rfp_excel.app.ingestion.pdf.router.needs_ocr", return_value=False),
    ):
        types = router.detect_page_type("dummy.pdf", 0)
        assert types == [PageType.TABLE]
        assert router.should_extract_text("dummy.pdf", 0) is False
        assert router.should_extract_tables("dummy.pdf", 0) is True
        assert router.should_extract_images("dummy.pdf", 0) is False
        assert router.should_run_ocr("dummy.pdf", 0) is False


def test_router_detect_image() -> None:
    router = PageRouter()
    with (
        patch("ai_rfp_excel.app.ingestion.pdf.router.has_text_content", return_value=False),
        patch("ai_rfp_excel.app.ingestion.pdf.router.has_tables", return_value=False),
        patch("ai_rfp_excel.app.ingestion.pdf.router.has_images", return_value=True),
        patch("ai_rfp_excel.app.ingestion.pdf.router.needs_ocr", return_value=False),
    ):
        types = router.detect_page_type("dummy.pdf", 0)
        assert types == [PageType.IMAGE]
        assert router.should_extract_text("dummy.pdf", 0) is False
        assert router.should_extract_tables("dummy.pdf", 0) is False
        assert router.should_extract_images("dummy.pdf", 0) is True
        assert router.should_run_ocr("dummy.pdf", 0) is False


def test_router_detect_scanned() -> None:
    router = PageRouter()
    with (
        patch("ai_rfp_excel.app.ingestion.pdf.router.has_text_content", return_value=False),
        patch("ai_rfp_excel.app.ingestion.pdf.router.has_tables", return_value=False),
        patch("ai_rfp_excel.app.ingestion.pdf.router.has_images", return_value=False),
        patch("ai_rfp_excel.app.ingestion.pdf.router.needs_ocr", return_value=True),
    ):
        types = router.detect_page_type("dummy.pdf", 0)
        assert types == [PageType.SCANNED]
        assert router.should_extract_text("dummy.pdf", 0) is False
        assert router.should_extract_tables("dummy.pdf", 0) is False
        assert router.should_extract_images("dummy.pdf", 0) is False
        assert router.should_run_ocr("dummy.pdf", 0) is True


def test_router_detect_mixed() -> None:
    router = PageRouter()
    with (
        patch("ai_rfp_excel.app.ingestion.pdf.router.has_text_content", return_value=True),
        patch("ai_rfp_excel.app.ingestion.pdf.router.has_tables", return_value=True),
        patch("ai_rfp_excel.app.ingestion.pdf.router.has_images", return_value=True),
        patch("ai_rfp_excel.app.ingestion.pdf.router.needs_ocr", return_value=False),
    ):
        types = router.detect_page_type("dummy.pdf", 0)
        assert types == [PageType.MIXED]
        assert router.should_extract_text("dummy.pdf", 0) is True
        assert router.should_extract_tables("dummy.pdf", 0) is True
        assert router.should_extract_images("dummy.pdf", 0) is True
        assert router.should_run_ocr("dummy.pdf", 0) is True



def test_router_detect_empty_defaults_to_native_text() -> None:
    router = PageRouter()
    with (
        patch("ai_rfp_excel.app.ingestion.pdf.router.has_text_content", return_value=False),
        patch("ai_rfp_excel.app.ingestion.pdf.router.has_tables", return_value=False),
        patch("ai_rfp_excel.app.ingestion.pdf.router.has_images", return_value=False),
        patch("ai_rfp_excel.app.ingestion.pdf.router.needs_ocr", return_value=False),
    ):
        types = router.detect_page_type("dummy.pdf", 0)
        assert types == [PageType.NATIVE_TEXT]
