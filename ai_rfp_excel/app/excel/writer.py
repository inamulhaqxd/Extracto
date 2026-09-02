from datetime import datetime
from pathlib import Path
from typing import Any

import openpyxl
from openpyxl.cell.cell import Cell, MergedCell
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from ai_rfp_excel.app.config import settings
from ai_rfp_excel.app.excel.models import (
    PopulationResult,
    WorkbookAnalysis,
)
from ai_rfp_excel.app.excel.validator import ExcelValidator
from ai_rfp_excel.app.logging import get_logger
from ai_rfp_excel.app.matching.models import ComplianceDecision, ComplianceState

logger = get_logger("excel.writer")

# Soft highlight colors for compliance states (hex fill colors)
STATUS_FILLS = {
    ComplianceState.COMPLIANT: PatternFill(start_color="E2F0D9", end_color="E2F0D9", fill_type="solid"),
    ComplianceState.NON_COMPLIANT: PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid"),
    ComplianceState.PARTIALLY_COMPLIANT: PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid"),
    ComplianceState.AMBIGUOUS: PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid"),
    ComplianceState.NOT_FOUND: PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid"),
}

STATUS_LABELS = {
    ComplianceState.COMPLIANT: "Compliant",
    ComplianceState.NON_COMPLIANT: "Non-Compliant",
    ComplianceState.PARTIALLY_COMPLIANT: "Partially Compliant",
    ComplianceState.AMBIGUOUS: "Ambiguous",
    ComplianceState.NOT_FOUND: "Not Found",
}


class ExcelWriter:
    """Populates RFP response workbooks with compliance decisions and evidence."""

    def __init__(self, output_dir: str | Path | None = None) -> None:
        self.output_dir = Path(output_dir) if output_dir else Path(settings.OUTPUT_DIR)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.validator = ExcelValidator()

    def _safe_set_cell_value(
        self,
        ws: Worksheet,
        cell_coord: str,
        value: Any,
        fill: PatternFill | None = None,
    ) -> None:
        """Safely write to normal cells and merged cells without raising read-only attribute errors."""
        if isinstance(value, str):
            value = "".join(
                c
                for c in value
                if (
                    ord(c) in (0x9, 0xA, 0xD)
                    or (0x20 <= ord(c) <= 0xD7FF)
                    or (0xE000 <= ord(c) <= 0xFFFD)
                    or (0x10000 <= ord(c) <= 0x10FFFF)
                )
            )

        cell = ws[cell_coord]
        from openpyxl.cell.cell import MergedCell

        if isinstance(cell, MergedCell):
            for rng in ws.merged_cells.ranges:
                if cell.coordinate in rng:
                    top_cell = ws.cell(row=rng.min_row, column=rng.min_col)
                    setattr(top_cell, "value", value)
                    if fill:
                        setattr(top_cell, "fill", fill)
                    break
        else:
            setattr(cell, "value", value)
            if fill:
                setattr(cell, "fill", fill)

    def populate_workbook(
        self,
        template_path: str | Path,
        analysis: WorkbookAnalysis,
        decisions: list[ComplianceDecision],
        create_summary: bool = True,
    ) -> PopulationResult:
        """Populate template workbook with compliance results, preserving formatting and formulas."""
        template_file = Path(template_path)
        if not template_file.exists():
            raise FileNotFoundError(f"Template workbook not found: {template_path}")

        # Load original workbook preserving formulas (data_only=False)
        wb = openpyxl.load_workbook(template_file, data_only=False)

        # Index decisions for lookup
        decision_by_id = {d.requirement_id: d for d in decisions if d.requirement_id}
        decision_by_text = {d.requirement_text.strip().lower(): d for d in decisions}

        total_populated = 0
        all_evaluated_decisions: list[ComplianceDecision] = []

        # Iterate through sheets and requirements
        for sheet_analysis in analysis.sheets:
            if sheet_analysis.sheet_name not in wb.sheetnames:
                continue

            ws = wb[sheet_analysis.sheet_name]

            for req in sheet_analysis.requirements:
                # Find matching decision
                dec = decision_by_id.get(req.requirement_id)
                if not dec:
                    dec = decision_by_text.get(req.requirement_text.strip().lower())

                if not dec:
                    continue

                all_evaluated_decisions.append(dec)
                status_str = STATUS_LABELS.get(dec.state, dec.state.value)
                fill = STATUS_FILLS.get(dec.state)

                # Format evidence text for remarks
                remarks_parts: list[str] = []
                if dec.evidence:
                    for ev in dec.evidence:
                        if ev.citation:
                            remarks_parts.append(ev.citation)
                        elif ev.reasoning:
                            remarks_parts.append(ev.reasoning)
                        elif ev.value:
                            remarks_parts.append(ev.value)
                elif dec.reasoning:
                    remarks_parts.append(dec.reasoning)

                remarks_text = " | ".join(dict.fromkeys(remarks_parts)) if remarks_parts else "Specification not found in reference data."

                # 1. Populate compliance cells
                for _, cell_coord in req.compliance_cells.items():
                    self._safe_set_cell_value(ws, cell_coord, status_str, fill)
                    total_populated += 1

                # 2. Populate answer / offered specification / proposed value cells
                matched_val = dec.matched_value or (dec.evidence[0].value if dec.evidence else "")
                if matched_val:
                    for _, cell_coord in req.answer_cells.items():
                        self._safe_set_cell_value(ws, cell_coord, matched_val)
                        total_populated += 1

                    for _, cell_coord in req.proposed_cells.items():
                        self._safe_set_cell_value(ws, cell_coord, matched_val)
                        total_populated += 1

                    for _, cell_coord in req.offered_spec_cells.items():
                        self._safe_set_cell_value(ws, cell_coord, matched_val)
                        total_populated += 1

                    for _, cell_coord in req.vendor_cells.items():
                        # Only fill vendor cell if not already populated
                        if (
                            cell_coord not in req.compliance_cells.values()
                            and cell_coord not in req.offered_spec_cells.values()
                            and cell_coord not in req.answer_cells.values()
                            and cell_coord not in req.proposed_cells.values()
                        ):
                            self._safe_set_cell_value(ws, cell_coord, matched_val)
                            total_populated += 1

                # 3. Populate remarks cells
                for _, cell_coord in req.remarks_cells.items():
                    self._safe_set_cell_value(ws, cell_coord, remarks_text)
                    total_populated += 1

                # 4. Populate total marks cells
                is_preference = "preference" in req.requirement_text.lower() or "preferred" in req.requirement_text.lower()
                total_marks_val = "10" if is_preference else "Mandatory"
                for _, cell_coord in req.total_marks_cells.items():
                    self._safe_set_cell_value(ws, cell_coord, total_marks_val)
                    total_populated += 1

                # 5. Populate marks obtained cells
                if dec.state == ComplianceState.COMPLIANT:
                    marks_val = "10"
                elif dec.state == ComplianceState.PARTIALLY_COMPLIANT:
                    marks_val = "5"
                else:
                    marks_val = "0"

                for _, cell_coord in req.marks_cells.items():
                    self._safe_set_cell_value(ws, cell_coord, marks_val)
                    total_populated += 1

        # Add Compliance Summary Sheet if requested
        if create_summary:
            self._create_summary_sheet(wb, analysis, all_evaluated_decisions or decisions)

        # File naming: {original_name}_populated_{timestamp}.xlsx
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stem = template_file.stem
        populated_filename = f"{stem}_populated_{timestamp}.xlsx"
        output_file_path = self.output_dir / populated_filename

        wb.save(output_file_path)
        logger.info("Populated workbook saved", path=str(output_file_path), populated_cells=total_populated)

        # Run automated validation
        validation_report = self.validator.validate(
            populated_path=output_file_path,
            original_analysis=analysis,
            decisions=all_evaluated_decisions or decisions,
        )

        return PopulationResult(
            output_file_path=str(output_file_path),
            filename=populated_filename,
            total_populated_cells=total_populated,
            summary_sheet_created=True,
            validation_report=validation_report,
        )

    def _create_summary_sheet(
        self,
        wb: openpyxl.Workbook,
        analysis: WorkbookAnalysis,
        decisions: list[ComplianceDecision],
    ) -> None:
        """Create executive summary sheet as sheet index 0."""
        summary_title = "Compliance Summary"
        if summary_title in wb.sheetnames:
            del wb[summary_title]

        ws = wb.create_sheet(title=summary_title, index=0)
        ws.views.sheetView[0].showGridLines = True

        # Styles
        title_font = Font(name="Calibri", size=16, bold=True, color="1F4E79")
        subtitle_font = Font(name="Calibri", size=10, italic=True, color="595959")
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        section_font = Font(name="Calibri", size=12, bold=True, color="1F4E79")
        bold_font = Font(name="Calibri", size=11, bold=True)
        regular_font = Font(name="Calibri", size=11)

        header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
        thin_border = Border(

            left=Side(style="thin", color="D9D9D9"),
            right=Side(style="thin", color="D9D9D9"),
            top=Side(style="thin", color="D9D9D9"),
            bottom=Side(style="thin", color="D9D9D9"),
        )

        # Title block
        cell_b2 = ws.cell(row=2, column=2, value="RFP COMPLIANCE EVALUATION REPORT")
        cell_b2.font = title_font
        cell_b3 = ws.cell(row=3, column=2, value=f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Source File: {analysis.filename}")
        cell_b3.font = subtitle_font

        # Calculate Statistics
        total_reqs = len(decisions) if decisions else analysis.total_requirements
        counts: dict[ComplianceState, int] = {state: 0 for state in ComplianceState}
        high_conf = 0
        med_conf = 0
        low_conf = 0

        for d in decisions:
            counts[d.state] = counts.get(d.state, 0) + 1
            if d.confidence >= 0.90:
                high_conf += 1
            elif d.confidence >= 0.70:
                med_conf += 1
            else:
                low_conf += 1

        # 1. Executive Status Breakdown Table
        row = 5
        ws.cell(row=row, column=2, value="1. Executive Compliance Summary").font = section_font
        row += 1

        headers = ["Compliance Status", "Count", "Percentage (%)"]
        for col_idx, h in enumerate(headers, start=2):
            cell = ws.cell(row=row, column=col_idx, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center" if col_idx > 2 else "left")

        status_order = [
            (ComplianceState.COMPLIANT, "Compliant", "E2F0D9"),
            (ComplianceState.PARTIALLY_COMPLIANT, "Partially Compliant", "FFF2CC"),
            (ComplianceState.NON_COMPLIANT, "Non-Compliant", "FCE4D6"),
            (ComplianceState.AMBIGUOUS, "Ambiguous (Conflicting)", "FFF2CC"),
            (ComplianceState.NOT_FOUND, "Not Found in Reference Specs", "F2F2F2"),
        ]

        for state, label, fill_hex in status_order:
            row += 1
            cnt = counts.get(state, 0)
            pct = round((cnt / total_reqs * 100), 1) if total_reqs > 0 else 0.0

            c1 = ws.cell(row=row, column=2, value=label)
            c1.font = regular_font
            c1.border = thin_border
            if fill_hex:
                c1.fill = PatternFill(start_color=fill_hex, end_color=fill_hex, fill_type="solid")

            c2 = ws.cell(row=row, column=3, value=cnt)
            c2.font = regular_font
            c2.alignment = Alignment(horizontal="right")
            c2.border = thin_border

            c3 = ws.cell(row=row, column=4, value=f"{pct}%")
            c3.font = regular_font
            c3.alignment = Alignment(horizontal="right")
            c3.border = thin_border

        # Total row
        row += 1
        c_tot1 = ws.cell(row=row, column=2, value="Total Requirements Evaluated")
        c_tot1.font = bold_font
        c_tot1.border = thin_border

        c_tot2 = ws.cell(row=row, column=3, value=total_reqs)
        c_tot2.font = bold_font
        c_tot2.alignment = Alignment(horizontal="right")
        c_tot2.border = thin_border

        c_tot3 = ws.cell(row=row, column=4, value="100.0%")
        c_tot3.font = bold_font
        c_tot3.alignment = Alignment(horizontal="right")
        c_tot3.border = thin_border

        # 2. Confidence Distribution Table
        row += 3
        ws.cell(row=row, column=2, value="2. AI Confidence Distribution").font = section_font
        row += 1

        conf_headers = ["Confidence Tier", "Criteria", "Count", "Share (%)"]
        for col_idx, h in enumerate(conf_headers, start=2):
            cell = ws.cell(row=row, column=col_idx, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center" if col_idx > 3 else "left")

        conf_data = [
            ("High Confidence", "Score >= 90% (Exact & Rule match)", high_conf),
            ("Medium Confidence", "Score 70% - 89% (Semantic match)", med_conf),
            ("Low Confidence (Flagged)", "Score < 70% (Manual review recommended)", low_conf),
        ]

        for label, crit, cnt in conf_data:
            row += 1
            pct = round((cnt / total_reqs * 100), 1) if total_reqs > 0 else 0.0
            r_c1 = ws.cell(row=row, column=2, value=label)
            r_c1.font = regular_font
            r_c1.border = thin_border

            r_c2 = ws.cell(row=row, column=3, value=crit)
            r_c2.font = regular_font
            r_c2.border = thin_border

            r_c3 = ws.cell(row=row, column=4, value=cnt)
            r_c3.font = regular_font
            r_c3.alignment = Alignment(horizontal="right")
            r_c3.border = thin_border

            r_c4 = ws.cell(row=row, column=5, value=f"{pct}%")
            r_c4.font = regular_font
            r_c4.alignment = Alignment(horizontal="right")
            r_c4.border = thin_border

        # 3. Sheet Breakdown
        row += 3
        ws.cell(row=row, column=2, value="3. Workbook Sheets Breakdown").font = section_font
        row += 1

        sheet_headers = ["Sheet Name", "Total Requirements", "Sections Detected", "Columns"]
        for col_idx, h in enumerate(sheet_headers, start=2):
            cell = ws.cell(row=row, column=col_idx, value=h)
            cell.font = header_font
            cell.fill = header_fill

        for sheet in analysis.sheets:
            row += 1
            s_c1 = ws.cell(row=row, column=2, value=sheet.sheet_name)
            s_c1.font = regular_font
            s_c1.border = thin_border

            s_c2 = ws.cell(row=row, column=3, value=len(sheet.requirements))
            s_c2.font = regular_font
            s_c2.alignment = Alignment(horizontal="right")
            s_c2.border = thin_border

            s_c3 = ws.cell(row=row, column=4, value=len(sheet.sections))
            s_c3.font = regular_font
            s_c3.alignment = Alignment(horizontal="right")
            s_c3.border = thin_border

            s_c4 = ws.cell(row=row, column=5, value=len(sheet.columns))
            s_c4.font = regular_font
            s_c4.alignment = Alignment(horizontal="right")
            s_c4.border = thin_border

        # Auto-fit column widths
        for col in range(2, 7):
            col_letter = get_column_letter(col)
            max_len = 0
            for r in range(1, row + 2):
                val = ws.cell(row=r, column=col).value
                if val:
                    max_len = max(max_len, len(str(val)))
            ws.column_dimensions[col_letter].width = max(max_len + 3, 14)
