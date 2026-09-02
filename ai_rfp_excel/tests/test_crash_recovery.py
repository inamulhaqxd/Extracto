import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

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
from ai_rfp_excel.app.ingestion.pdf.processor import (
    load_checkpoint,
    process_pdf,
    retry_failed_pages,
    save_checkpoint,
)


def test_save_and_load_checkpoint() -> None:
    context = ProcessingContext(
        document_id="doc-test-123",
        user_id="user-test-123",
        run_id="run-test-123",
        total_pages=5,
        processed_pages=3,
        failed_pages=[4],
        status=ProcessingStatus.PARTIAL,
    )
    page_0 = PageResult(
        page_number=0,
        page_type=PageType.NATIVE_TEXT,
        native_text=ExtractedText(page_number=0, text="Hello page 0"),
    )
    context.pdf_pages.append(page_0)

    with tempfile.TemporaryDirectory() as tmp_dir:
        chk_file = Path(tmp_dir) / "test_checkpoint.json"
        saved_path = save_checkpoint(context, chk_file)
        assert Path(saved_path).exists()

        loaded_context = load_checkpoint(saved_path)
        assert loaded_context.document_id == context.document_id
        assert loaded_context.user_id == context.user_id
        assert loaded_context.run_id == context.run_id
        assert loaded_context.total_pages == 5
        assert loaded_context.processed_pages == 3
        assert loaded_context.failed_pages == [4]
        assert loaded_context.status == ProcessingStatus.PARTIAL
        assert len(loaded_context.pdf_pages) == 1
        assert loaded_context.pdf_pages[0].native_text is not None
        assert loaded_context.pdf_pages[0].native_text.text == "Hello page 0"


def test_retry_failed_pages() -> None:
    context = ProcessingContext(
        document_id="doc-test-456",
        user_id="user-test-456",
        run_id="run-test-456",
        total_pages=2,
        processed_pages=2,
        failed_pages=[1],
        status=ProcessingStatus.PARTIAL,
    )
    page_0 = PageResult(
        page_number=0,
        page_type=PageType.NATIVE_TEXT,
        native_text=ExtractedText(page_number=0, text="Page 0 succeeded"),
    )
    page_1_failed = PageResult(
        page_number=1,
        page_type=PageType.NATIVE_TEXT,
        errors=["Simulated error during first attempt"],
    )
    context.pdf_pages = [page_0, page_1_failed]

    def mock_process_page(pdf_path: str, page_number: int, ctx: ProcessingContext) -> PageResult:
        return PageResult(
            page_number=page_number,
            page_type=PageType.NATIVE_TEXT,
            native_text=ExtractedText(page_number=page_number, text="Page 1 successfully retried"),
        )

    with (
        tempfile.TemporaryDirectory() as tmp_dir,
        patch("ai_rfp_excel.app.ingestion.pdf.processor.process_page", side_effect=mock_process_page),
    ):
        chk_file = Path(tmp_dir) / "retry_checkpoint.json"
        updated_context = retry_failed_pages("dummy.pdf", context, checkpoint_path=chk_file)

        assert updated_context.failed_pages == []
        assert updated_context.status == ProcessingStatus.COMPLETED
        assert len(updated_context.pdf_pages) == 2
        assert updated_context.pdf_pages[1].native_text is not None
        assert updated_context.pdf_pages[1].native_text.text == "Page 1 successfully retried"
        assert Path(chk_file).exists()


def test_provenance_tracking() -> None:
    context = ProcessingContext(
        document_id="doc-prov-001",
        user_id="user-prov-001",
        run_id="run-prov-001",
        total_pages=2,
    )
    page_0 = PageResult(
        page_number=0,
        page_type=PageType.MIXED,
        native_text=ExtractedText(
            page_number=0,
            text="Specification for Server X",
            bbox={"x0": 10, "top": 20, "x1": 500, "bottom": 700, "width": 490, "height": 680},
        ),
        tables=[
            ExtractedTable(
                page_number=0,
                table_id="T01-01",
                headers=["Item", "Qty"],
                rows=[["CPU", "2"]],
                bbox={"x0": 50, "top": 100, "x1": 400, "bottom": 300, "width": 350, "height": 200},
            )
        ],
        images=[
            ExtractedImage(
                page_number=0,
                image_id="IMG01-01",
                image_path="/data/images/img1.png",
                bbox={"x": 50, "y": 400, "width": 200, "height": 150},
            )
        ],
    )
    page_1 = PageResult(
        page_number=1,
        page_type=PageType.SCANNED,
        ocr_result=OCRResult(
            page_number=1,
            text="Scanned OCR text",
            confidence=0.88,
            engine="paddleocr",
            bbox={"x0": 0, "top": 0, "x1": 600, "bottom": 800, "width": 600, "height": 800},
        ),
    )
    context.pdf_pages = [page_0, page_1]

    records = context.get_provenance_records()
    assert len(records) == 4

    types = {r.entity_type for r in records}
    assert types == {"text", "table", "image", "ocr"}

    text_record = next(r for r in records if r.entity_type == "text")
    assert text_record.document_id == "doc-prov-001"
    assert text_record.page_number == 0
    assert text_record.bbox is not None
    assert text_record.bbox["width"] == 490

    table_record = next(r for r in records if r.entity_type == "table")
    assert table_record.entity_id == "T01-01"
    assert table_record.confidence == 1.0

    ocr_record = next(r for r in records if r.entity_type == "ocr")
    assert ocr_record.extraction_method == "paddleocr"
    assert ocr_record.confidence == 0.88


def test_process_pdf_with_resume() -> None:
    with patch("ai_rfp_excel.app.ingestion.pdf.processor.get_pdf_page_count", return_value=3):
        # Initial context with page 0 already done
        initial_context = ProcessingContext(
            document_id="doc-resume-999",
            user_id="user-resume-999",
            run_id="run-resume-999",
            total_pages=3,
            processed_pages=1,
        )
        initial_context.pdf_pages.append(
            PageResult(
                page_number=0,
                page_type=PageType.NATIVE_TEXT,
                native_text=ExtractedText(page_number=0, text="Already processed"),
            )
        )

        with (
            tempfile.TemporaryDirectory() as tmp_dir,
            patch("ai_rfp_excel.app.ingestion.pdf.processor.process_page") as mock_proc_page,
        ):
            mock_proc_page.side_effect = lambda path, p_num, ctx: PageResult(
                page_number=p_num,
                page_type=PageType.NATIVE_TEXT,
                native_text=ExtractedText(page_number=p_num, text=f"Processed page {p_num}"),
            )

            chk_path = Path(tmp_dir) / "checkpoint.json"
            final_ctx = process_pdf(
                "dummy.pdf",
                user_id="user-resume-999",
                batch_size=2,
                resume_context=initial_context,
                checkpoint_path=chk_path,
                auto_checkpoint=True,
            )

            assert final_ctx.status == ProcessingStatus.COMPLETED
            # Should have processed pages 1 and 2 (page 0 was skipped)
            assert mock_proc_page.call_count == 2
            assert len(final_ctx.pdf_pages) == 3
