import json
import uuid
from pathlib import Path

from ai_rfp_excel.app.config import settings
from ai_rfp_excel.app.ingestion.models import (
    PageResult,
    PageType,
    ProcessingContext,
    ProcessingStatus,
)
from ai_rfp_excel.app.ingestion.ocr.processor import ocr_page, render_page_to_image
from ai_rfp_excel.app.ingestion.pdf.image_extractor import extract_images_from_page
from ai_rfp_excel.app.ingestion.pdf.router import PageRouter
from ai_rfp_excel.app.ingestion.pdf.table_extractor import extract_tables_from_page
from ai_rfp_excel.app.ingestion.pdf.text_extractor import extract_text_from_page

router = PageRouter()


def save_checkpoint(
    context: ProcessingContext,
    checkpoint_path: str | Path | None = None,
) -> str:
    if checkpoint_path is None:
        save_dir = Path(settings.PROCESSED_DIR) / "checkpoints"
        save_dir.mkdir(parents=True, exist_ok=True)
        file_path = save_dir / f"checkpoint_{context.run_id}.json"
    else:
        file_path = Path(checkpoint_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(context.to_checkpoint_dict(), f, indent=2, default=str)

    return str(file_path)


def load_checkpoint(checkpoint_path: str | Path) -> ProcessingContext:
    with open(checkpoint_path, encoding="utf-8") as f:
        data = json.load(f)
    return ProcessingContext.from_checkpoint_dict(data)


def process_page(pdf_path: str, page_number: int, context: ProcessingContext) -> PageResult:
    page_result = PageResult(page_number=page_number, page_type=PageType.NATIVE_TEXT)

    try:
        page_types = router.detect_page_type(pdf_path, page_number)
        if page_types:
            page_result.page_type = page_types[0]

        if router.should_extract_text(pdf_path, page_number):
            text_result = extract_text_from_page(pdf_path, page_number)
            page_result.native_text = text_result

        if router.should_extract_tables(pdf_path, page_number):
            tables = extract_tables_from_page(pdf_path, page_number)
            page_result.tables = tables
            context.extracted_tables.extend(tables)

        if router.should_extract_images(pdf_path, page_number):
            images = extract_images_from_page(pdf_path, page_number)
            page_result.images = images
            context.extracted_images.extend(images)

        if router.should_run_ocr(pdf_path, page_number):
            ocr_result = ocr_page(pdf_path, page_number)
            page_result.ocr_result = ocr_result
            context.ocr_results.append(ocr_result)

        if router.should_run_ocr(pdf_path, page_number) or page_result.images:
            image_path = render_page_to_image(pdf_path, page_number)
            page_result.rendered_path = image_path

    except Exception as e:
        page_result.errors.append(str(e))
        if page_number not in context.failed_pages:
            context.failed_pages.append(page_number)

    return page_result


def process_batch(
    pdf_path: str,
    page_numbers: list[int],
    context: ProcessingContext,
) -> list[PageResult]:
    results: list[PageResult] = []

    for page_num in page_numbers:
        result = process_page(pdf_path, page_num, context)
        results.append(result)
        context.processed_pages += 1

    return results


def process_pdf(
    pdf_path: str,
    user_id: str,
    batch_size: int = 10,
    resume_context: ProcessingContext | None = None,
    checkpoint_path: str | Path | None = None,
    auto_checkpoint: bool = True,
) -> ProcessingContext:
    try:
        import pypdfium2
        pdf_doc = pypdfium2.PdfDocument(pdf_path)
        total_pages = len(pdf_doc)
        pdf_doc.close()
    except Exception:
        try:
            import fitz
            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            doc.close()
        except Exception:
            total_pages = 1

    if resume_context is not None:
        context = resume_context
    elif checkpoint_path is not None and Path(checkpoint_path).exists():
        context = load_checkpoint(checkpoint_path)
    else:
        context = ProcessingContext(
            document_id=str(uuid.uuid4()),
            user_id=user_id,
            run_id=str(uuid.uuid4()),
            total_pages=total_pages,
            status=ProcessingStatus.EXTRACTING_TEXT,
        )

    processed_page_nums = {p.page_number for p in context.pdf_pages if not p.errors}

    for batch_start in range(0, total_pages, batch_size):
        batch_end = min(batch_start + batch_size, total_pages)
        page_numbers = [p for p in range(batch_start, batch_end) if p not in processed_page_nums]

        if not page_numbers:
            continue

        try:
            batch_results = process_batch(pdf_path, page_numbers, context)
            context.pdf_pages.extend(batch_results)
        except Exception as e:
            context.errors.append(f"Batch {batch_start}-{batch_end} failed: {e!s}")
            for p in page_numbers:
                if p not in context.failed_pages:
                    context.failed_pages.append(p)

        # Mid-pipeline checkpoint for crash recovery
        if auto_checkpoint:
            save_checkpoint(context, checkpoint_path)

    if context.failed_pages:
        context.status = ProcessingStatus.PARTIAL
    else:
        context.status = ProcessingStatus.COMPLETED

    if auto_checkpoint:
        save_checkpoint(context, checkpoint_path)

    return context


def retry_failed_pages(
    pdf_path: str,
    context: ProcessingContext,
    checkpoint_path: str | Path | None = None,
) -> ProcessingContext:
    pages_to_retry = list(context.failed_pages)
    if not pages_to_retry:
        return context

    context.failed_pages = []
    context.status = ProcessingStatus.EXTRACTING_TEXT

    existing_pages_by_num = {p.page_number: p for p in context.pdf_pages}

    for page_num in pages_to_retry:
        new_result = process_page(pdf_path, page_num, context)
        existing_pages_by_num[page_num] = new_result

    # Reconstruct sorted pdf_pages list
    context.pdf_pages = [existing_pages_by_num[p] for p in sorted(existing_pages_by_num.keys())]

    if context.failed_pages:
        context.status = ProcessingStatus.PARTIAL
    else:
        context.status = ProcessingStatus.COMPLETED

    save_checkpoint(context, checkpoint_path)
    return context

