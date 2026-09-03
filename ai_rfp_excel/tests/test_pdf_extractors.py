import sys
from types import ModuleType
from typing import Any
from unittest.mock import MagicMock, patch

try:
    import fitz  # noqa: F401
except Exception:
    mock_fitz_module = ModuleType("fitz")
    mock_fitz_module.open = MagicMock()  # type: ignore
    sys.modules["fitz"] = mock_fitz_module

from ai_rfp_excel.app.ingestion.models import OCRResult
from ai_rfp_excel.app.ingestion.ocr.processor import needs_ocr, ocr_page, ocr_with_tesseract
from ai_rfp_excel.app.ingestion.pdf.image_extractor import has_images
from ai_rfp_excel.app.ingestion.pdf.table_extractor import _detect_merged_cells, has_tables
from ai_rfp_excel.app.ingestion.pdf.text_extractor import extract_text_from_page, has_text_content


def test_detect_merged_cells_horizontal() -> None:
    raw_table: list[list[Any]] = [
        ["Header 1", "Header 2", "Header 3"],
        ["Merged Cell Text", None, None],
        ["A", "B", "C"],
    ]
    merged = _detect_merged_cells(raw_table)
    assert len(merged) == 1
    assert merged[0]["row"] == 1
    assert merged[0]["col"] == 0
    assert merged[0]["colspan"] == 3
    assert merged[0]["value"] == "Merged Cell Text"


def test_detect_merged_cells_vertical() -> None:
    raw_table: list[list[Any]] = [
        ["Category", "Item", "Price"],
        ["Hardware", "Server", "$1000"],
        [None, "Switch", "$500"],
    ]
    merged = _detect_merged_cells(raw_table)
    assert len(merged) >= 1
    vert = [m for m in merged if m["rowspan"] > 1]
    assert len(vert) == 1
    assert vert[0]["row"] == 1
    assert vert[0]["col"] == 0
    assert vert[0]["rowspan"] == 2
    assert vert[0]["value"] == "Hardware"


def test_detect_merged_cells_empty_or_none() -> None:
    assert _detect_merged_cells([]) == []
    assert _detect_merged_cells([["Single row"]]) == []


def test_has_text_content() -> None:
    with patch("fitz.open") as mock_open:
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_page.get_text.return_value = "This is a sufficiently long text for the page check."
        mock_doc.__getitem__.return_value = mock_page
        mock_open.return_value = mock_doc

        assert has_text_content("dummy.pdf", 0, min_chars=10) is True
        assert has_text_content("dummy.pdf", 0, min_chars=100) is False


def test_extract_text_with_bbox() -> None:
    with patch("fitz.open") as mock_open:
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_page.get_text.return_value = "Sample text"
        mock_rect = MagicMock()
        mock_rect.x0 = 0.0
        mock_rect.y0 = 0.0
        mock_rect.x1 = 612.0
        mock_rect.y1 = 792.0
        mock_rect.width = 612.0
        mock_rect.height = 792.0
        mock_page.rect = mock_rect
        mock_doc.__getitem__.return_value = mock_page
        mock_open.return_value = mock_doc

        result = extract_text_from_page("dummy.pdf", 0)
        assert result.page_number == 0
        assert result.text == "Sample text"
        assert result.confidence == 1.0
        assert result.bbox is not None
        assert result.bbox["width"] == 612.0


def test_has_images() -> None:
    with patch("fitz.open") as mock_open:
        mock_doc = MagicMock()
        mock_doc.__len__.return_value = 1
        mock_page = MagicMock()
        mock_page.get_images.return_value = [(1, 0, 100, 100, 8, "DeviceRGB", "", "img1", "FlateDecode")]
        mock_doc.__getitem__.return_value = mock_page
        mock_open.return_value = mock_doc

        assert has_images("dummy.pdf", 0) is True

        mock_page.get_images.return_value = []
        assert has_images("dummy.pdf", 0) is False


def test_has_tables() -> None:
    with patch("pdfplumber.open") as mock_open:
        mock_pdf = MagicMock()
        mock_pdf.pages = [MagicMock()]
        mock_table = MagicMock()
        mock_table.extract.return_value = [["H1", "H2"], ["R1", "R2"]]
        mock_pdf.pages[0].find_tables.return_value = [mock_table]
        mock_open.return_value.__enter__.return_value = mock_pdf

        assert has_tables("dummy.pdf", 0) is True


def test_ocr_tesseract_success() -> None:
    with (
        patch("PIL.Image.open"),
        patch("pytesseract.image_to_string", return_value="Recognized OCR text"),
        patch("pytesseract.image_to_data", return_value={"conf": ["95", "90", "85"]}),
    ):
        res = ocr_with_tesseract("dummy.png")
        assert res.engine == "tesseract"
        assert res.text == "Recognized OCR text"
        assert res.confidence == 0.9


def test_ocr_paddleocr_fallback_when_tesseract_low_confidence() -> None:
    with (
        patch(
            "ai_rfp_excel.app.ingestion.ocr.processor.render_page_to_image",
            return_value="dummy_page.png",
        ),
        patch(
            "ai_rfp_excel.app.ingestion.ocr.processor.ocr_with_tesseract",
            return_value=OCRResult(page_number=0, text="blurry text", confidence=0.3, engine="tesseract"),
        ),
        patch(
            "ai_rfp_excel.app.ingestion.ocr.processor.ocr_with_paddleocr",
            return_value=OCRResult(
                page_number=0,
                text="High quality extracted Paddle text",
                confidence=0.92,
                engine="paddleocr",
            ),
        ),
    ):
        res = ocr_page("dummy.pdf", 0, min_confidence=0.6)
        assert res.engine == "paddleocr"
        assert res.confidence == 0.92
        assert "Paddle text" in res.text


def test_ocr_paddleocr_not_called_when_tesseract_high_confidence() -> None:
    with (
        patch(
            "ai_rfp_excel.app.ingestion.ocr.processor.render_page_to_image",
            return_value="dummy_page.png",
        ),
        patch(
            "ai_rfp_excel.app.ingestion.ocr.processor.ocr_with_tesseract",
            return_value=OCRResult(page_number=0, text="Clear text", confidence=0.95, engine="tesseract"),
        ),
        patch("ai_rfp_excel.app.ingestion.ocr.processor.ocr_with_paddleocr") as mock_paddle,
    ):
        res = ocr_page("dummy.pdf", 0, min_confidence=0.6)
        assert res.engine == "tesseract"
        assert res.confidence == 0.95
        mock_paddle.assert_not_called()


def test_needs_ocr() -> None:
    with patch("fitz.open") as mock_open:
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_page.get_text.return_value = "Short"
        mock_doc.__getitem__.return_value = mock_page
        mock_open.return_value = mock_doc

        assert needs_ocr("dummy.pdf", 0, text_threshold=50) is True

        mock_page.get_text.return_value = "This is a very long text that clearly exceeds fifty characters easily."
        assert needs_ocr("dummy.pdf", 0, text_threshold=50) is False
