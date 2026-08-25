import uuid

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
) -> ProcessingContext:
    import fitz

    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    doc.close()

    context = ProcessingContext(
        document_id=str(uuid.uuid4()),
        user_id=user_id,
        run_id=str(uuid.uuid4()),
        total_pages=total_pages,
        status=ProcessingStatus.EXTRACTING_TEXT,
    )

    for batch_start in range(0, total_pages, batch_size):
        batch_end = min(batch_start + batch_size, total_pages)
        page_numbers = list(range(batch_start, batch_end))

        try:
            batch_results = process_batch(pdf_path, page_numbers, context)
            context.pdf_pages.extend(batch_results)
        except Exception as e:
            context.errors.append(f"Batch {batch_start}-{batch_end} failed: {e!s}")
            context.failed_pages.extend(page_numbers)

    if context.failed_pages:
        context.status = ProcessingStatus.PARTIAL
    else:
        context.status = ProcessingStatus.COMPLETED

    return context
