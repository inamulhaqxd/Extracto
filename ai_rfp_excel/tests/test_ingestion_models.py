from ai_rfp_excel.app.ingestion.models import (
    ExtractedImage,
    ExtractedTable,
    ExtractedText,
    OCRResult,
    PageResult,
    PageType,
    ProcessingContext,
    ProcessingStatus,
)


def test_page_type_enum() -> None:
    assert PageType.NATIVE_TEXT.value == "native_text"
    assert PageType.TABLE.value == "table"
    assert PageType.IMAGE.value == "image"
    assert PageType.SCANNED.value == "scanned"
    assert PageType.MIXED.value == "mixed"


def test_processing_status_enum() -> None:
    assert ProcessingStatus.PENDING.value == "pending"
    assert ProcessingStatus.COMPLETED.value == "completed"
    assert ProcessingStatus.FAILED.value == "failed"
    assert ProcessingStatus.PARTIAL.value == "partial"


def test_extracted_text_model() -> None:
    text = ExtractedText(page_number=1, text="Hello world")
    assert text.page_number == 1
    assert text.text == "Hello world"
    assert text.source == "native_pdf"
    assert text.confidence == 1.0


def test_extracted_table_model() -> None:
    table = ExtractedTable(
        page_number=1,
        table_id="T01-01",
        headers=["Col1", "Col2"],
        rows=[["A", "B"]],
    )
    assert table.page_number == 1
    assert table.table_id == "T01-01"
    assert len(table.headers) == 2
    assert len(table.rows) == 1


def test_extracted_image_model() -> None:
    image = ExtractedImage(
        page_number=1,
        image_id="IMG01-01",
        image_path="/path/to/image.png",
    )
    assert image.page_number == 1
    assert image.image_id == "IMG01-01"


def test_ocr_result_model() -> None:
    ocr = OCRResult(page_number=1, text="OCR text", confidence=0.95)
    assert ocr.page_number == 1
    assert ocr.confidence == 0.95
    assert ocr.engine == "tesseract"


def test_page_result_model() -> None:
    result = PageResult(page_number=1, page_type=PageType.NATIVE_TEXT)
    assert result.page_number == 1
    assert result.page_type == PageType.NATIVE_TEXT
    assert result.tables == []
    assert result.images == []
    assert result.errors == []


def test_processing_context_model() -> None:
    context = ProcessingContext(
        document_id="doc-123",
        user_id="user-123",
        run_id="run-123",
    )
    assert context.document_id == "doc-123"
    assert context.status == ProcessingStatus.PENDING
    assert context.total_pages == 0
    assert context.processed_pages == 0
    assert context.failed_pages == []
