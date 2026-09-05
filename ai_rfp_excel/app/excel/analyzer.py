"""
Excel Workbook Analyzer.
Delegates to PRD-compliant Step 2 Dynamic Analyzer.
Strict typing only — zero Any (Rule 4).
"""

from __future__ import annotations

import uuid
from pathlib import Path

from ai_rfp_excel.app.excel.models import (
    ColumnType,
    DetectedColumn,
    ExcelRequirement,
    ExcelSection,
    SheetAnalysis,
    WorkbookAnalysis,
)
from ai_rfp_excel.app.excel.utils import calculate_workbook_hash, validate_excel_file
from ai_rfp_excel.app.pipeline.step2_excel_analyzer import (
    WorkbookAnalysis as PipelineWorkbookAnalysis,
)
from ai_rfp_excel.app.pipeline.step2_excel_analyzer import (
    analyze_workbook as pipeline_analyze_workbook,
)


class ExcelAnalyzer:
    """Dynamic Excel workbook analyzer delegating to Step 2 pipeline."""

    def analyze_workbook(
        self,
        file_path: str,
        workbook_id: str | None = None,
        version: int = 1,
    ) -> WorkbookAnalysis:
        path = Path(file_path)
        validate_excel_file(str(path))
        file_hash = calculate_workbook_hash(str(path))
        file_size = path.stat().st_size if path.exists() else 0
        wb_id = workbook_id or str(uuid.uuid4())

        raw_analysis: PipelineWorkbookAnalysis = pipeline_analyze_workbook(path)

        sheets_models: list[SheetAnalysis] = []
        for s in raw_analysis.get("sheets", []):
            s_name = s.get("sheet_name", "Sheet1")
            s_idx = s.get("sheet_index", 0)
            max_r = s.get("max_row", 1)
            max_c = s.get("max_column", 1)
            h_row = s.get("header_row", 1)

            cols_models: list[DetectedColumn] = []
            for c in s.get("columns", []):
                c_type_raw = str(c.get("column_type", "unknown")).lower()
                c_type = ColumnType.UNKNOWN
                for ct in ColumnType:
                    if ct.value == c_type_raw:
                        c_type = ct
                        break
                cols_models.append(
                    DetectedColumn(
                        column_letter=str(c.get("column_letter", "A")),
                        column_index=int(c.get("column_index", 1)),
                        header_name=str(c.get("header_name", "")),
                        column_type=c_type,
                    )
                )

            reqs_models: list[ExcelRequirement] = []
            for r in s.get("requirements", []):
                slots = r.get("target_slots", {})
                vendor_cells: dict[str, str] = {}
                compliance_cells: dict[str, str] = {}
                remarks_cells: dict[str, str] = {}
                answer_cells: dict[str, str] = {}
                marks_cells: dict[str, str] = {}
                total_marks_cells: dict[str, str] = {}

                for s_key, s_val in slots.items():
                    s_type = str(s_val.get("slot_type", ""))
                    coord = str(s_val.get("cell_coordinate", ""))
                    if s_type == "compliance":
                        compliance_cells[s_key] = coord
                    elif s_type == "remarks":
                        remarks_cells[s_key] = coord
                    elif s_type == "answer":
                        answer_cells[s_key] = coord
                    elif s_type == "marks":
                        marks_cells[s_key] = coord
                    elif s_type == "total_marks":
                        total_marks_cells[s_key] = coord
                    elif s_type == "vendor":
                        vendor_cells[s_key] = coord

                reqs_models.append(
                    ExcelRequirement(
                        requirement_id=str(r.get("requirement_id", "")),
                        sheet_name=s_name,
                        row_number=int(r.get("row_number", 0)),
                        section=r.get("section"),
                        requirement_text=str(r.get("requirement_text", "")),
                        source_cell=str(r.get("source_cell", "A1")),
                        vendor_cells=vendor_cells,
                        compliance_cells=compliance_cells,
                        remarks_cells=remarks_cells,
                        answer_cells=answer_cells,
                        marks_cells=marks_cells,
                        total_marks_cells=total_marks_cells,
                        empty_slots=list(slots.keys()),
                    )
                )

            section_map: dict[str, list[ExcelRequirement]] = {}
            for rm in reqs_models:
                sec_name = rm.section or "General"
                section_map.setdefault(sec_name, []).append(rm)

            sec_models: list[ExcelSection] = []
            for sec_name, sec_reqs in section_map.items():
                min_r = min(req.row_number for req in sec_reqs)
                max_row_sec = max(req.row_number for req in sec_reqs)
                sec_models.append(
                    ExcelSection(
                        name=sec_name,
                        start_row=min_r,
                        end_row=max_row_sec,
                        requirements=sec_reqs,
                    )
                )

            sheets_models.append(
                SheetAnalysis(
                    sheet_name=s_name,
                    sheet_index=s_idx,
                    dimensions={"min_row": 1, "max_row": max_r, "min_col": 1, "max_col": max_c},
                    header_row=h_row,
                    columns=cols_models,
                    sections=sec_models,
                    requirements=reqs_models,
                )
            )

        return WorkbookAnalysis(
            workbook_id=wb_id,
            filename=path.name,
            file_hash=file_hash,
            file_size=file_size,
            total_sheets=len(sheets_models),
            sheet_names=[s.sheet_name for s in sheets_models],
            sheets=sheets_models,
            total_requirements=raw_analysis.get("total_requirements", 0),
            version=version,
        )
