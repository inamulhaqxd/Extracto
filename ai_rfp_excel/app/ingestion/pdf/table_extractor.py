import pdfplumber

from ai_rfp_excel.app.ingestion.models import ExtractedTable


def extract_tables_from_page(pdf_path: str, page_number: int) -> list[ExtractedTable]:
    tables: list[ExtractedTable] = []

    with pdfplumber.open(pdf_path) as pdf:
        if page_number >= len(pdf.pages):
            return tables

        page = pdf.pages[page_number]
        extracted_tables = page.extract_tables()

        for idx, table in enumerate(extracted_tables):
            if not table or len(table) < 2:
                continue

            headers = [str(cell) if cell else "" for cell in table[0]]
            rows: list[list[str]] = []
            for row in table[1:]:
                cells = [str(cell) if cell else "" for cell in row]
                rows.append(cells)

            table_id = f"T{page_number + 1:02d}-{idx + 1:02d}"

            tables.append(
                ExtractedTable(
                    page_number=page_number,
                    table_id=table_id,
                    headers=headers,
                    rows=rows,
                    bbox=None,
                )
            )

    return tables


def extract_tables_from_pdf(pdf_path: str) -> list[ExtractedTable]:
    results: list[ExtractedTable] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_num in range(len(pdf.pages)):
            page_tables = extract_tables_from_page(pdf_path, page_num)
            results.extend(page_tables)

    return results


def has_tables(pdf_path: str, page_number: int) -> bool:
    with pdfplumber.open(pdf_path) as pdf:
        if page_number >= len(pdf.pages):
            return False
        page = pdf.pages[page_number]
        tables = page.extract_tables()
        return bool(tables and any(t and len(t) >= 2 for t in tables))
