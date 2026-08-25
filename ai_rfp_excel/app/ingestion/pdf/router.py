from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from app.document.processing_context import PageContent


class PDFParser(ABC):
    @abstractmethod
    def can_parse(self, page_number: int) -> bool:
        pass

    @abstractmethod
    def parse(self, pdf_path: str, page_number: int) -> Optional[PageContent]:
        pass


class PyMuPDFParser(PDFParser):
    def can_parse(self, page_number: int) -> bool:
        return True

    def parse(self, pdf_path: str, page_number: int) -> Optional[PageContent]:
        import fitz

        doc = fitz.open(pdf_path)
        if page_number >= len(doc):
            doc.close()
            return None

        page = doc[page_number]
        text = page.get_text()

        doc.close()

        if not text.strip():
            return None

        return PageContent(
            page_number=page_number + 1,
            content_type="text",
            text=text,
            extraction_method="pymupdf",
            confidence=1.0,
        )


class PDFRouter:
    def __init__(self):
        self.parsers: list[PDFParser] = [PyMuPDFParser()]

    def add_parser(self, parser: PDFParser):
        self.parsers.append(parser)

    def parse_page(self, pdf_path: str, page_number: int) -> list[PageContent]:
        results = []

        for parser in self.parsers:
            if parser.can_parse(page_number):
                result = parser.parse(pdf_path, page_number)
                if result:
                    results.append(result)

        return results

    def parse_all_pages(self, pdf_path: str) -> list[PageContent]:
        import fitz

        doc = fitz.open(pdf_path)
        page_count = len(doc)
        doc.close()

        all_pages = []
        for page_num in range(page_count):
            page_results = self.parse_page(pdf_path, page_num)
            all_pages.extend(page_results)

        return all_pages
