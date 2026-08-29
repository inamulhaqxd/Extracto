from typing import Any

import pdfplumber

from ai_rfp_excel.app.ingestion.models import ExtractedTable


def _detect_merged_cells(raw_table: list[list[Any]]) -> list[dict[str, Any]]:
    merged_cells: list[dict[str, Any]] = []
    if not raw_table or len(raw_table) < 2:
        return merged_cells

    num_rows = len(raw_table)
    num_cols = max(len(r) for r in raw_table) if raw_table else 0
    covered_cells: set[tuple[int, int]] = set()

    for r_idx, row in enumerate(raw_table):
        for c_idx, cell in enumerate(row):
            # Check for horizontal span (e.g. trailing None in row after a valid cell)
            if cell is not None and str(cell).strip() != "" and (r_idx, c_idx) not in covered_cells:
                colspan = 1
                while (c_idx + colspan < len(row)) and (row[c_idx + colspan] is None):
                    covered_cells.add((r_idx, c_idx + colspan))
                    colspan += 1
                if colspan > 1:
                    merged_cells.append(
                        {
                            "row": r_idx,
                            "col": c_idx,
                            "rowspan": 1,
                            "colspan": colspan,
                            "value": str(cell).strip(),
                        }
                    )

    # Check for vertical spans (None in same column in subsequent rows)
    for c_idx in range(num_cols):
        r_idx = 0
        while r_idx < num_rows:
            if (
                c_idx < len(raw_table[r_idx])
                and raw_table[r_idx][c_idx] is not None
                and (r_idx, c_idx) not in covered_cells
            ):
                cell_val = str(raw_table[r_idx][c_idx]).strip()
                if cell_val:
                    rowspan = 1
                    while (
                        (r_idx + rowspan < num_rows)
                        and (c_idx < len(raw_table[r_idx + rowspan]))
                        and (raw_table[r_idx + rowspan][c_idx] is None)
                        and ((r_idx + rowspan, c_idx) not in covered_cells)
                    ):
                        rowspan += 1
                    if rowspan > 1:
                        for span_i in range(1, rowspan):
                            covered_cells.add((r_idx + span_i, c_idx))
                        merged_cells.append(
                            {
                                "row": r_idx,
                                "col": c_idx,
                                "rowspan": rowspan,
                                "colspan": 1,
                                "value": cell_val,
                            }
                        )
                    r_idx += rowspan
                    continue
            r_idx += 1

    return merged_cells



def extract_tables_from_page(pdf_path: str, page_number: int) -> list[ExtractedTable]:
    tables: list[ExtractedTable] = []

    with pdfplumber.open(pdf_path) as pdf:
        if page_number >= len(pdf.pages):
            return tables

        page = pdf.pages[page_number]
        table_objects = page.find_tables()

        if table_objects:
            for idx, table_obj in enumerate(table_objects):
                raw_table = table_obj.extract()
                if not raw_table or len(raw_table) < 2:
                    continue

                headers = [str(cell).strip() if cell is not None else "" for cell in raw_table[0]]
                rows: list[list[str]] = []
                for row in raw_table[1:]:
                    cells = [str(cell).strip() if cell is not None else "" for cell in row]
                    rows.append(cells)

                table_id = f"T{page_number + 1:02d}-{idx + 1:02d}"

                bbox_dict: dict[str, Any] = {
                    "x0": round(float(table_obj.bbox[0]), 2),
                    "top": round(float(table_obj.bbox[1]), 2),
                    "x1": round(float(table_obj.bbox[2]), 2),
                    "bottom": round(float(table_obj.bbox[3]), 2),
                    "width": round(float(table_obj.bbox[2] - table_obj.bbox[0]), 2),
                    "height": round(float(table_obj.bbox[3] - table_obj.bbox[1]), 2),
                }

                merged_cells = _detect_merged_cells(raw_table)

                tables.append(
                    ExtractedTable(
                        page_number=page_number,
                        table_id=table_id,
                        headers=headers,
                        rows=rows,
                        merged_cells=merged_cells if merged_cells else None,
                        bbox=bbox_dict,
                    )
                )
        else:
            # Fallback to direct extract_tables if find_tables returned empty
            extracted_tables = page.extract_tables()
            for idx, table in enumerate(extracted_tables):
                if not table or len(table) < 2:
                    continue

                headers = [str(cell).strip() if cell is not None else "" for cell in table[0]]
                rows = [[str(cell).strip() if cell is not None else "" for cell in row] for row in table[1:]]
                table_id = f"T{page_number + 1:02d}-{idx + 1:02d}"
                merged_cells = _detect_merged_cells(table)

                tables.append(
                    ExtractedTable(
                        page_number=page_number,
                        table_id=table_id,
                        headers=headers,
                        rows=rows,
                        merged_cells=merged_cells if merged_cells else None,
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
        table_objects = page.find_tables()
        if table_objects:
            return any(t.extract() and len(t.extract()) >= 2 for t in table_objects)
        tables = page.extract_tables()
        return bool(tables and any(t and len(t) >= 2 for t in tables))

