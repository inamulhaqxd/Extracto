from ai_rfp_excel.app.ingestion.models import PageType
from ai_rfp_excel.app.ingestion.ocr.processor import needs_ocr
from ai_rfp_excel.app.ingestion.pdf.image_extractor import has_images
from ai_rfp_excel.app.ingestion.pdf.table_extractor import has_tables
from ai_rfp_excel.app.ingestion.pdf.text_extractor import has_text_content


class PageRouter:
    def detect_page_type(self, pdf_path: str, page_number: int) -> list[PageType]:
        page_types: list[PageType] = []

        has_text = has_text_content(pdf_path, page_number)
        has_tbl = has_tables(pdf_path, page_number)
        has_img = has_images(pdf_path, page_number)
        needs_ocr_page = needs_ocr(pdf_path, page_number)

        if has_text:
            page_types.append(PageType.NATIVE_TEXT)
        if has_tbl:
            page_types.append(PageType.TABLE)
        if has_img:
            page_types.append(PageType.IMAGE)
        if needs_ocr_page:
            page_types.append(PageType.SCANNED)

        if len(page_types) > 1:
            return [PageType.MIXED]
        elif not page_types:
            return [PageType.NATIVE_TEXT]
        else:
            return page_types

    def should_extract_text(self, pdf_path: str, page_number: int) -> bool:
        page_types = self.detect_page_type(pdf_path, page_number)
        return PageType.NATIVE_TEXT in page_types or PageType.MIXED in page_types

    def should_extract_tables(self, pdf_path: str, page_number: int) -> bool:
        page_types = self.detect_page_type(pdf_path, page_number)
        return PageType.TABLE in page_types or PageType.MIXED in page_types

    def should_extract_images(self, pdf_path: str, page_number: int) -> bool:
        page_types = self.detect_page_type(pdf_path, page_number)
        return PageType.IMAGE in page_types or PageType.MIXED in page_types

    def should_run_ocr(self, pdf_path: str, page_number: int) -> bool:
        page_types = self.detect_page_type(pdf_path, page_number)
        return PageType.SCANNED in page_types or PageType.MIXED in page_types
