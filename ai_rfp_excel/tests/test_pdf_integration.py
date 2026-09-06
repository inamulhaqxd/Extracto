import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

try:
    import fitz
except Exception:
    fitz = None

if fitz is None:
    pytestmark = pytest.mark.skip(reason="PyMuPDF / fitz C++ runtime not installed on host")

from PIL import Image, ImageDraw

from ai_rfp_excel.app.ingestion.models import ProcessingStatus
from ai_rfp_excel.app.ingestion.pdf.processor import process_pdf, retry_failed_pages


def create_sample_test_pdf(pdf_path: str) -> None:
    if fitz is None:
        return
    doc = fitz.open()

    # Page 1: Native Text
    p1 = doc.new_page(width=612, height=792)
    p1.insert_text((50, 50), "Technical Specification Document\nSection 1: General Requirements\nServer Model: PowerEdge R750\nRAM: 128GB DDR4\nStorage: 2x 1.92TB NVMe SSD", fontsize=12)

    # Page 2: Simple Table (drawn with text lines)
    p2 = doc.new_page(width=612, height=792)
    p2.insert_text((50, 50), "Table 1: Bill of Materials", fontsize=14)
    # Draw table lines and cell text
    p2.draw_rect(fitz.Rect(50, 100, 500, 300))
    p2.insert_text((60, 130), "Item No\tDescription\tQuantity\tUnit Price", fontsize=11)
    p2.insert_text((60, 170), "01\tDatabase Server\t2\t$5,000", fontsize=11)
    p2.insert_text((60, 210), "02\t10GbE Switch\t4\t$1,200", fontsize=11)

    # Page 3: Embedded Image
    p3 = doc.new_page(width=612, height=792)
    img = Image.new("RGB", (200, 100), color=(73, 109, 137))
    d = ImageDraw.Draw(img)
    d.text((10, 40), "Architecture Diagram", fill=(255, 255, 0))
    import io

    img_buf = io.BytesIO()
    img.save(img_buf, format="PNG")
    p3.insert_image(fitz.Rect(100, 100, 300, 200), stream=img_buf.getvalue())

    # Page 4: Another text/spec page
    p4 = doc.new_page(width=612, height=792)
    p4.insert_text((50, 50), "Section 4: Compliance and SLA\nUptime requirement: 99.99%\nBackup retention: 30 days", fontsize=12)

    doc.save(pdf_path)
    doc.close()



def test_pdf_ingestion_end_to_end() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        pdf_file = Path(tmp_dir) / "sample_rfp.pdf"
        chk_file = Path(tmp_dir) / "checkpoint_e2e.json"
        create_sample_test_pdf(str(pdf_file))

        context = process_pdf(
            pdf_path=str(pdf_file),
            user_id="user-integration-001",
            batch_size=2,
            checkpoint_path=chk_file,
            auto_checkpoint=True,
        )

        assert context.total_pages == 4
        assert context.processed_pages >= 4
        assert context.status in (ProcessingStatus.COMPLETED, ProcessingStatus.PARTIAL)
        assert len(context.pdf_pages) == 4

        # Page 0 has native text
        page_0 = context.pdf_pages[0]
        assert page_0.native_text is not None
        assert "Technical Specification" in page_0.native_text.text
        assert page_0.native_text.bbox is not None

        # Page 2 has images
        page_2 = context.pdf_pages[2]
        assert len(page_2.images) >= 1
        assert page_2.images[0].bbox is not None

        # Provenance records
        prov_records = context.get_provenance_records()
        assert len(prov_records) > 0
        for rec in prov_records:
            assert rec.document_id == context.document_id
            assert rec.confidence > 0.0

        # Checkpoint file exists
        assert chk_file.exists()


def test_pdf_ingestion_retry_workflow() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        pdf_file = Path(tmp_dir) / "sample_rfp_retry.pdf"
        chk_file = Path(tmp_dir) / "checkpoint_retry.json"
        create_sample_test_pdf(str(pdf_file))

        # First pass: simulate failure on page 1
        with patch("ai_rfp_excel.app.ingestion.pdf.processor.process_page") as mock_proc:
            def side_effect(path: str, page_num: int, ctx: object) -> object:
                from ai_rfp_excel.app.ingestion.models import PageResult, PageType
                if page_num == 1:
                    raise RuntimeError("Simulated transient page extraction failure")
                return PageResult(page_number=page_num, page_type=PageType.NATIVE_TEXT)

            mock_proc.side_effect = side_effect

            context = process_pdf(
                pdf_path=str(pdf_file),
                user_id="user-retry-test",
                batch_size=2,
                checkpoint_path=chk_file,
            )

            assert context.status == ProcessingStatus.PARTIAL
            assert 1 in context.failed_pages

        # Second pass: retry failed pages
        final_context = retry_failed_pages(
            pdf_path=str(pdf_file),
            context=context,
            checkpoint_path=chk_file,
        )

        assert final_context.status == ProcessingStatus.COMPLETED
        assert final_context.failed_pages == []
