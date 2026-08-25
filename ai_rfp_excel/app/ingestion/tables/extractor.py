from pathlib import Path
from typing import Optional

from app.document.processing_context import TableData


class TableExtractor:
    def extract_tables(self, pdf_path: str, page_number: int) -> list[TableData]:
        tables = []

        try:
            tables.extend(self._extract_with_pdfplumber(pdf_path, page_number))
        except Exception:
            pass

        return tables

    def _extract_with_pdfplumber(self, pdf_path: str, page_number: int) -> list[TableData]:
        import pdfplumber

        tables = []

        with pdfplumber.open(pdf_path) as pdf:
            if page_number >= len(pdf.pages):
                return tables

            page = pdf.pages[page_number]
            extracted_tables = page.extract_tables()

            for idx, table in enumerate(extracted_tables):
                if not table or len(table) < 2:
                    continue

                headers = [str(cell) if cell else "" for cell in table[0]]
                rows = []
                for row in table[1:]:
                    rows.append([str(cell) if cell else "" for cell in row])

                tables.append(TableData(
                    table_id=f"T{page_number + 1:02d}-{idx + 1:02d}",
                    page_number=page_number + 1,
                    headers=headers,
                    rows=rows,
                ))

        return tables
