from dataclasses import dataclass, field
from typing import Optional

import openpyxl
from openpyxl.worksheet.worksheet import Worksheet


@dataclass
class SheetInfo:
    name: str
    index: int
    has_requirements: bool = False
    requirement_count: int = 0
    headers: list[str] = field(default_factory=list)
    vendor_columns: list[str] = field(default_factory=list)
    merged_cells: list[str] = field(default_factory=list)
    hidden_rows: list[int] = field(default_factory=list)
    hidden_columns: list[str] = field(default_factory=list)
    dimensions: str = ""


@dataclass
class RequirementInfo:
    sheet_name: str
    row: int
    section: Optional[str]
    requirement_text: str
    source_cell: str
    source_range: Optional[str] = None


class ExcelAnalyzer:
    def __init__(self):
        self.workbook = None
        self.sheets: list[SheetInfo] = []
        self.requirements: list[RequirementInfo] = []

    def analyze(self, excel_path: str) -> dict:
        self.workbook = openpyxl.load_workbook(excel_path, data_only=True)

        self.sheets = []
        self.requirements = []

        for idx, sheet_name in enumerate(self.workbook.sheetnames):
            sheet = self.workbook[sheet_name]
            sheet_info = self._analyze_sheet(sheet, idx)
            self.sheets.append(sheet_info)

            if sheet_info.has_requirements:
                self._detect_requirements(sheet, sheet_name)

        return {
            "sheet_count": len(self.sheets),
            "sheets": [self._sheet_to_dict(s) for s in self.sheets],
            "total_requirements": len(self.requirements),
            "requirements": [self._requirement_to_dict(r) for r in self.requirements],
        }

    def _analyze_sheet(self, sheet: Worksheet, index: int) -> SheetInfo:
        sheet_info = SheetInfo(
            name=sheet.title,
            index=index,
            dimensions=str(sheet.dimensions),
        )

        sheet_info.merged_cells = [
            str(merge) for merge in sheet.merged_cells.ranges
        ]

        for row_idx in range(1, sheet.max_row + 1):
            if sheet.row_dimensions[row_idx].hidden:
                sheet_info.hidden_rows.append(row_idx)

        for col_idx in range(1, sheet.max_column + 1):
            col_letter = openpyxl.utils.get_column_letter(col_idx)
            if sheet.column_dimensions[col_letter].hidden:
                sheet_info.hidden_columns.append(col_letter)

        headers = self._detect_headers(sheet)
        sheet_info.headers = headers

        sheet_info.vendor_columns = self._detect_vendor_columns(headers)

        sheet_info.has_requirements = self._has_requirements(sheet, headers)
        if sheet_info.has_requirements:
            sheet_info.requirement_count = self._count_requirements(sheet)

        return sheet_info

    def _detect_headers(self, sheet: Worksheet) -> list[str]:
        headers = []

        for row_idx in range(1, min(6, sheet.max_row + 1)):
            row_headers = []
            for col_idx in range(1, sheet.max_column + 1):
                cell = sheet.cell(row=row_idx, column=col_idx)
                if cell.value and isinstance(cell.value, str):
                    row_headers.append(str(cell.value).strip())

            if len(row_headers) >= 2:
                headers = row_headers
                break

        return headers

    def _detect_vendor_columns(self, headers: list[str]) -> list[str]:
        vendor_keywords = [
            "vendor", "provider", "supplier", "manufacturer",
            "company", "brand", "distributor",
        ]
        vendor_columns = []

        for idx, header in enumerate(headers):
            header_lower = header.lower()
            if any(keyword in header_lower for keyword in vendor_keywords):
                vendor_columns.append(header)
            elif idx > 0 and not self._is_requirement_text(header):
                if header_lower not in ["requirement", "specification", "description", "item"]:
                    vendor_columns.append(header)

        return vendor_columns

    def _has_requirements(self, sheet: Worksheet, headers: list[str]) -> bool:
        requirement_keywords = [
            "requirement", "specification", "minimum", "maximum",
            "should", "must", "shall", "need", "mandatory",
            "compliance", "compliant", "criteria",
        ]

        for row_idx in range(1, min(20, sheet.max_row + 1)):
            for col_idx in range(1, sheet.max_column + 1):
                cell = sheet.cell(row=row_idx, column=col_idx)
                if cell.value and isinstance(cell.value, str):
                    cell_lower = cell.value.lower()
                    if any(keyword in cell_lower for keyword in requirement_keywords):
                        return True

        return False

    def _count_requirements(self, sheet: Worksheet) -> int:
        count = 0
        for row_idx in range(1, sheet.max_row + 1):
            for col_idx in range(1, sheet.max_column + 1):
                cell = sheet.cell(row=row_idx, column=col_idx)
                if cell.value and isinstance(cell.value, str):
                    if self._is_requirement_text(cell.value):
                        count += 1
                        break

        return count

    def _is_requirement_text(self, text: str) -> bool:
        text_lower = text.lower()
        patterns = [
            "minimum", "maximum", "at least", "at most",
            "should be", "must be", "shall be",
            ">= ", "<= ", "= ", "> ", "< ",
            "gb", "tb", "mb", "cores", "ghz", "mhz",
        ]
        return any(pattern in text_lower for pattern in patterns)

    def _detect_requirements(self, sheet: Worksheet, sheet_name: str):
        current_section = None
        header_row = 1

        for row_idx in range(header_row + 1, sheet.max_row + 1):
            row_values = []
            for col_idx in range(1, sheet.max_column + 1):
                cell = sheet.cell(row=row_idx, column=col_idx)
                row_values.append(str(cell.value) if cell.value else "")

            if self._is_section_header(row_values):
                current_section = self._extract_section_name(row_values)
                continue

            for col_idx, cell_value in enumerate(row_values):
                if cell_value and self._is_requirement_text(cell_value):
                    col_letter = openpyxl.utils.get_column_letter(col_idx + 1)
                    self.requirements.append(RequirementInfo(
                        sheet_name=sheet_name,
                        row=row_idx,
                        section=current_section,
                        requirement_text=cell_value,
                        source_cell=f"{col_letter}{row_idx}",
                    ))

    def _is_section_header(self, row_values: list[str]) -> bool:
        non_empty = [v for v in row_values if v.strip()]
        if len(non_empty) != 1:
            return False
        text = non_empty[0].strip()
        if len(text) < 3:
            return False
        if text.isupper() and len(text) > 3:
            return True
        if text.startswith(("Section", "Category", "Part", "Chapter")):
            return True
        if text.endswith(":") and len(text) < 50:
            return True
        if text.startswith("Section ") or text.startswith("Category "):
            return True
        return False

    def _extract_section_name(self, row_values: list[str]) -> str:
        for value in row_values:
            if value.strip():
                return value.strip()
        return ""

    def _sheet_to_dict(self, sheet: SheetInfo) -> dict:
        return {
            "name": sheet.name,
            "index": sheet.index,
            "has_requirements": sheet.has_requirements,
            "requirement_count": sheet.requirement_count,
            "headers": sheet.headers,
            "vendor_columns": sheet.vendor_columns,
            "merged_cells": sheet.merged_cells,
            "hidden_rows": sheet.hidden_rows,
            "hidden_columns": sheet.hidden_columns,
            "dimensions": sheet.dimensions,
        }

    def _requirement_to_dict(self, req: RequirementInfo) -> dict:
        return {
            "sheet_name": req.sheet_name,
            "row": req.row,
            "section": req.section,
            "requirement_text": req.requirement_text,
            "source_cell": req.source_cell,
            "source_range": req.source_range,
        }

    def close(self):
        if self.workbook:
            self.workbook.close()
