import uuid
from pathlib import Path
from typing import Any

import openpyxl
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from ai_rfp_excel.app.excel.models import (
    ColumnType,
    DetectedColumn,
    ExcelRequirement,
    ExcelSection,
    SheetAnalysis,
    WorkbookAnalysis,
)
from ai_rfp_excel.app.excel.utils import calculate_workbook_hash, validate_excel_file

REQUIREMENT_KEYWORDS = {
    "requirement",
    "requirements",
    "specification",
    "specifications",
    "description",
    "feature",
    "features",
    "item",
    "items",
    "clause",
    "criteria",
    "specs",
    "technical specification",
    "technical requirement",
    "scope",
}

COMPLIANCE_KEYWORDS = {
    "compliance",
    "compliant",
    "complied",
    "status",
    "meet",
    "meets",
    "y/n",
    "c/nc",
    "conformity",
    "fulfillment",
    "complied / not complied",
    "compliance (yes/no)",
}

REMARKS_KEYWORDS = {
    "remarks",
    "remark",
    "comments",
    "comment",
    "notes",
    "note",
    "clarification",
    "explanation",
    "deviation",
    "response",
    "reference",
    "evidence",
}

SECTION_KEYWORDS = {
    "section",
    "category",
    "module",
    "area",
    "group",
    "domain",
    "component",
}

INDEX_KEYWORDS = {
    "s.no",
    "s.no.",
    "s/n",
    "sr.no",
    "sr no",
    "no.",
    "no",
    "#",
    "item no",
    "item #",
    "sl",
    "sl.",
    "sl.no",
}

KNOWN_VENDOR_NAMES = {
    "vendor",
    "supplier",
    "bidder",
    "oem",
    "dwp",
    "premier",
    "dell",
    "hpe",
    "cisco",
    "lenovo",
    "supermicro",
    "huawei",
    "netapp",
    "pure storage",
    "ibm",
    "product",
    "proposed",
    "offered",
    "solution",
}


class ExcelAnalyzer:
    def analyze_workbook(
        self,
        file_path: str,
        workbook_id: str | None = None,
        version: int = 1,
    ) -> WorkbookAnalysis:
        valid, error_msg = validate_excel_file(file_path)
        if not valid:
            raise ValueError(error_msg or "Invalid Excel file")

        wb_path = Path(file_path)
        file_hash = calculate_workbook_hash(file_path)
        file_size = wb_path.stat().st_size
        wb_id = workbook_id or str(uuid.uuid4())

        wb = openpyxl.load_workbook(file_path, data_only=True)
        sheet_names = list(wb.sheetnames)

        sheets: list[SheetAnalysis] = []
        total_reqs = 0

        for idx, s_name in enumerate(sheet_names):
            ws = wb[s_name]
            sheet_analysis = self.analyze_sheet(ws, sheet_name=s_name, sheet_index=idx)
            sheets.append(sheet_analysis)
            total_reqs += len(sheet_analysis.requirements)

        wb.close()

        return WorkbookAnalysis(
            workbook_id=wb_id,
            filename=wb_path.name,
            file_hash=file_hash,
            file_size=file_size,
            version=version,
            total_sheets=len(sheet_names),
            sheet_names=sheet_names,
            sheets=sheets,
            total_requirements=total_reqs,
        )

    def analyze_sheet(
        self,
        ws: Worksheet,
        sheet_name: str,
        sheet_index: int,
    ) -> SheetAnalysis:
        dimensions = self._detect_dimensions(ws)
        merged_cells = self._detect_merged_cells(ws)
        hidden_rows, hidden_columns = self._detect_hidden_rows_and_cols(ws)

        header_row, columns = self._detect_headers_and_columns(ws)

        sections, requirements = self._detect_sections_and_requirements(
            ws=ws,
            header_row=header_row,
            columns=columns,
            sheet_name=sheet_name,
            sheet_index=sheet_index,
        )

        return SheetAnalysis(
            sheet_name=sheet_name,
            sheet_index=sheet_index,
            dimensions=dimensions,
            merged_cells=merged_cells,
            hidden_rows=hidden_rows,
            hidden_columns=hidden_columns,
            header_row=header_row,
            columns=columns,
            sections=sections,
            requirements=requirements,
        )

    def _detect_dimensions(self, ws: Worksheet) -> dict[str, int]:
        min_row = ws.min_row or 1
        max_row = ws.max_row or 1
        min_col = ws.min_column or 1
        max_col = ws.max_column or 1

        return {
            "min_row": min_row,
            "max_row": max_row,
            "min_column": min_col,
            "max_column": max_col,
        }

    def _detect_merged_cells(self, ws: Worksheet) -> list[dict[str, Any]]:
        merged_list: list[dict[str, Any]] = []
        for rng in ws.merged_cells.ranges:
            merged_list.append(
                {
                    "range": str(rng),
                    "min_row": rng.min_row,
                    "max_row": rng.max_row,
                    "min_col": rng.min_col,
                    "max_col": rng.max_col,
                    "top_left_cell": f"{get_column_letter(rng.min_col)}{rng.min_row}",
                }
            )
        return merged_list

    def _detect_hidden_rows_and_cols(
        self, ws: Worksheet
    ) -> tuple[list[int], list[str]]:
        hidden_rows: list[int] = []
        for r_idx, dimension in ws.row_dimensions.items():
            if dimension.hidden:
                hidden_rows.append(int(r_idx))

        hidden_cols: list[str] = []
        for col_letter, dimension in ws.column_dimensions.items():
            if dimension.hidden:
                hidden_cols.append(str(col_letter))

        return sorted(hidden_rows), sorted(hidden_cols)

    def _detect_headers_and_columns(
        self, ws: Worksheet
    ) -> tuple[int | None, list[DetectedColumn]]:
        max_row_to_scan = min(25, ws.max_row or 1)
        best_header_row: int | None = None
        best_score = -1
        best_columns: list[DetectedColumn] = []

        for r in range(ws.min_row or 1, max_row_to_scan + 1):
            row_cells = [ws.cell(row=r, column=c) for c in range(ws.min_column or 1, (ws.max_column or 1) + 1)]
            row_texts = [str(cell.value).strip() for cell in row_cells if cell.value is not None]

            if not row_texts:
                continue

            current_score = 0
            detected: list[DetectedColumn] = []

            for cell in row_cells:
                if cell.value is None:
                    continue
                val_clean = str(cell.value).strip().lower()
                if not val_clean:
                    continue

                col_idx = cell.column
                col_letter = get_column_letter(col_idx)
                header_text = str(cell.value).strip()

                col_type, vendor_name = self._classify_column(val_clean, header_text)

                if col_type == ColumnType.REQUIREMENT:
                    current_score += 10
                elif col_type in (ColumnType.COMPLIANCE, ColumnType.REMARKS, ColumnType.VENDOR):
                    current_score += 5
                elif col_type in (ColumnType.INDEX, ColumnType.SECTION):
                    current_score += 3
                else:
                    current_score += 1

                detected.append(
                    DetectedColumn(
                        column_letter=col_letter,
                        column_index=col_idx,
                        header_name=header_text,
                        column_type=col_type,
                        vendor_name=vendor_name,
                    )
                )

            # Requires at least one requirement-like or multi-column structure
            has_req = any(c.column_type == ColumnType.REQUIREMENT for c in detected)
            has_vendor_or_compliance = any(
                c.column_type in (ColumnType.VENDOR, ColumnType.COMPLIANCE, ColumnType.REMARKS) for c in detected
            )

            if (has_req or has_vendor_or_compliance or len(detected) >= 2) and current_score > best_score:
                best_score = current_score
                best_header_row = r
                best_columns = detected

        if best_header_row is None and (ws.max_column or 1) >= 1:
            # Fallback: assume row 1 if data exists
            best_header_row = 1
            best_columns = []
            for c in range(ws.min_column or 1, (ws.max_column or 1) + 1):
                val = ws.cell(row=1, column=c).value
                header_text = str(val).strip() if val is not None else f"Column {get_column_letter(c)}"
                col_type, v_name = self._classify_column(header_text.lower(), header_text)
                best_columns.append(
                    DetectedColumn(
                        column_letter=get_column_letter(c),
                        column_index=c,
                        header_name=header_text,
                        column_type=col_type,
                        vendor_name=v_name,
                    )
                )

        return best_header_row, best_columns

    def _classify_column(
        self,
        val_clean: str,
        header_text: str,
    ) -> tuple[ColumnType, str | None]:
        # Check requirement
        if any(kw in val_clean for kw in REQUIREMENT_KEYWORDS):
            return ColumnType.REQUIREMENT, None

        # Check compliance
        if any(kw in val_clean for kw in COMPLIANCE_KEYWORDS):
            return ColumnType.COMPLIANCE, None

        # Check remarks
        if any(kw in val_clean for kw in REMARKS_KEYWORDS):
            return ColumnType.REMARKS, None

        # Check index
        if any(val_clean == kw or val_clean.startswith(f"{kw} ") for kw in INDEX_KEYWORDS):
            return ColumnType.INDEX, None

        # Check section
        if any(kw in val_clean for kw in SECTION_KEYWORDS):
            return ColumnType.SECTION, None

        # Check vendor / product
        if any(vk in val_clean for vk in KNOWN_VENDOR_NAMES) or (
            len(val_clean) <= 30 and not val_clean.isdigit()
        ):
            return ColumnType.VENDOR, header_text

        return ColumnType.UNKNOWN, None

    def _detect_sections_and_requirements(
        self,
        ws: Worksheet,
        header_row: int | None,
        columns: list[DetectedColumn],
        sheet_name: str,
        sheet_index: int,
    ) -> tuple[list[ExcelSection], list[ExcelRequirement]]:
        start_row = (header_row or 0) + 1
        max_row = ws.max_row or 1

        req_cols = [c for c in columns if c.column_type == ColumnType.REQUIREMENT]
        vendor_cols = [c for c in columns if c.column_type == ColumnType.VENDOR]
        compliance_cols = [c for c in columns if c.column_type == ColumnType.COMPLIANCE]
        remarks_cols = [c for c in columns if c.column_type == ColumnType.REMARKS]

        # If no explicit requirement column was found, pick the first non-index text column
        if not req_cols and columns:
            candidate = next((c for c in columns if c.column_type != ColumnType.INDEX), columns[0])
            req_col_idx = candidate.column_index
            req_col_letter = candidate.column_letter
        elif req_cols:
            req_col_idx = req_cols[0].column_index
            req_col_letter = req_cols[0].column_letter
        else:
            req_col_idx = 1
            req_col_letter = "A"

        sections: list[ExcelSection] = []
        requirements: list[ExcelRequirement] = []

        current_section: ExcelSection | None = None
        current_section_name: str | None = None
        current_subsection_name: str | None = None

        req_counter = 1

        for r in range(start_row, max_row + 1):
            row_cells = {c: ws.cell(row=r, column=c) for c in range(ws.min_column or 1, (ws.max_column or 1) + 1)}
            non_empty = {c: cell for c, cell in row_cells.items() if cell.value is not None and str(cell.value).strip()}

            if not non_empty:
                continue

            first_col_cell = row_cells.get(ws.min_column or 1)
            first_val = str(first_col_cell.value).strip() if first_col_cell and first_col_cell.value is not None else ""
            req_cell = row_cells.get(req_col_idx)
            req_text = str(req_cell.value).strip() if req_cell and req_cell.value is not None else ""

            # Check if row is a Section Header:
            # - Text in a dedicated index/section column with bold or section keywords
            # - Or row has bold styling and no vendor/compliance data
            # - Or text starts with numbering like "1.0", "Section", "Category"
            is_section_header = False

            if first_val and (ws.min_column or 1) != req_col_idx:
                # First column is distinct from requirement column (e.g. index/section column)
                if len(non_empty) == 1:
                    is_section_header = True
                elif first_col_cell and first_col_cell.font and first_col_cell.font.bold and not req_text:
                    is_section_header = True
            elif first_val and (ws.min_column or 1) == req_col_idx:
                # First column IS the requirement column
                # Check for explicit section indicators (e.g. "Section", "Category", bold styling with short title)
                first_lower = first_val.lower()
                has_section_kw = any(first_lower.startswith(kw) for kw in ("section ", "category ", "part ", "module "))
                is_bold = bool(first_col_cell and first_col_cell.font and first_col_cell.font.bold)
                has_no_vendor_data = not any(vc.column_index in non_empty for vc in vendor_cols) and not any(
                    cc.column_index in non_empty for cc in compliance_cols
                )

                if has_section_kw or (is_bold and has_no_vendor_data and len(first_val.split()) <= 6):
                    is_section_header = True

            if is_section_header:
                section_title = first_val or (str(next(iter(non_empty.values())).value).strip())
                if current_section is not None:
                    current_section.end_row = r - 1

                current_section_name = section_title
                current_subsection_name = None
                current_section = ExcelSection(
                    name=section_title,
                    start_row=r,
                )
                sections.append(current_section)
                continue

            # Otherwise, extract requirement
            if not req_text and len(non_empty) == 1:
                # If only one cell has text anywhere in row, could be subsection
                single_cell_val = str(next(iter(non_empty.values())).value).strip()
                current_subsection_name = single_cell_val
                if current_section:
                    current_section.subsections.append(single_cell_val)
                continue


            if not req_text:
                # Fallback to any non-empty column text
                for c_idx, cell in non_empty.items():
                    if str(cell.value).strip():
                        req_text = str(cell.value).strip()
                        req_col_letter = get_column_letter(c_idx)
                        break

            if not req_text:
                continue

            source_coord = f"{req_col_letter}{r}"
            req_id = f"REQ-S{sheet_index + 1:02d}-{req_counter:03d}"
            req_counter += 1

            # Map target coordinates for vendors, compliance, remarks
            vendor_cells: dict[str, str] = {}
            for vc in vendor_cols:
                v_name = vc.vendor_name or vc.header_name
                vendor_cells[v_name] = f"{vc.column_letter}{r}"

            compliance_cells: dict[str, str] = {}
            for cc in compliance_cols:
                compliance_cells[cc.header_name] = f"{cc.column_letter}{r}"

            remarks_cells: dict[str, str] = {}
            for rc in remarks_cols:
                remarks_cells[rc.header_name] = f"{rc.column_letter}{r}"

            raw_row_data = {
                get_column_letter(c): cell.value for c, cell in non_empty.items()
            }

            requirement_item = ExcelRequirement(
                requirement_id=req_id,
                sheet_name=sheet_name,
                row_number=r,
                section=current_section_name,
                subsection=current_subsection_name,
                requirement_text=req_text,
                source_cell=source_coord,
                vendor_cells=vendor_cells,
                compliance_cells=compliance_cells,
                remarks_cells=remarks_cells,
                raw_values=raw_row_data,
            )

            requirements.append(requirement_item)
            if current_section is not None:
                current_section.requirements.append(requirement_item)

        if current_section is not None and current_section.end_row is None:
            current_section.end_row = max_row

        return sections, requirements
