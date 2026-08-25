import copy
from datetime import datetime
from pathlib import Path
from typing import Optional

import openpyxl
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment

from app.matching.rules import ComplianceStatus
from app.logging_config import get_logger

logger = get_logger()


class ExcelWriter:
    def __init__(self):
        self.compliance_colors = {
            ComplianceStatus.COMPLIANT: "92D050",
            ComplianceStatus.PARTIALLY_COMPLIANT: "FFC000",
            ComplianceStatus.NON_COMPLIANT: "FF0000",
            ComplianceStatus.NOT_FOUND: "BFBFBF",
            ComplianceStatus.AMBIGUOUS: "FF99FF",
        }

    def populate(
        self,
        template_path: str,
        compliance_results: list[dict],
        output_dir: str,
    ) -> str:
        wb = openpyxl.load_workbook(template_path)

        for result in compliance_results:
            self._write_compliance_result(wb, result)

        self._add_summary_sheet(wb, compliance_results)

        output_path = self._generate_output_path(template_path, output_dir)

        wb.save(output_path)
        wb.close()

        logger.info("excel_populated", output_path=output_path)
        return output_path

    def _write_compliance_result(self, wb: openpyxl.Workbook, result: dict):
        sheet_name = result.get("sheet_name")
        cell_ref = result.get("cell_reference")
        status = result.get("status")
        confidence = result.get("confidence", 0)

        if not sheet_name or not cell_ref:
            return

        if sheet_name not in wb.sheetnames:
            return

        sheet = wb[sheet_name]

        try:
            cell = sheet[cell_ref]

            if cell.value is not None:
                original_value = cell.value
                result["original_value"] = original_value

            cell.value = result.get("ai_decision", result.get("value", ""))

            if status:
                color = self.compliance_colors.get(ComplianceStatus(status), "FFFFFF")
                cell.fill = PatternFill(start_color=color, end_color=color, fill_type="solid")

            if confidence < 0.7:
                cell.font = Font(color="FF0000")
            elif confidence < 0.9:
                cell.font = Font(color="FFC000")

        except Exception as e:
            logger.error("failed_to_write_cell", cell=cell_ref, error=str(e))

    def _add_summary_sheet(self, wb: openpyxl.Workbook, compliance_results: list[dict]):
        if "Summary" in wb.sheetnames:
            del wb["Summary"]

        summary = wb.create_sheet("Summary", 0)

        summary["A1"] = "Compliance Summary"
        summary["A1"].font = Font(bold=True, size=14)

        summary["A3"] = "Status"
        summary["B3"] = "Count"
        summary["A3"].font = Font(bold=True)
        summary["B3"].font = Font(bold=True)

        status_counts = {}
        for result in compliance_results:
            status = result.get("status", "UNKNOWN")
            status_counts[status] = status_counts.get(status, 0) + 1

        row = 4
        for status, count in status_counts.items():
            summary[f"A{row}"] = status
            summary[f"B{row}"] = count

            color = self.compliance_colors.get(ComplianceStatus(status), "FFFFFF")
            summary[f"A{row}"].fill = PatternFill(start_color=color, end_color=color, fill_type="solid")

            row += 1

        row += 1
        summary[f"A{row}"] = "Total Requirements"
        summary[f"B{row}"] = len(compliance_results)
        summary[f"A{row}"].font = Font(bold=True)

        row += 2
        summary[f"A{row}"] = "Confidence Distribution"
        summary[f"A{row}"].font = Font(bold=True, size=12)

        row += 1
        high = sum(1 for r in compliance_results if r.get("confidence", 0) >= 0.9)
        medium = sum(1 for r in compliance_results if 0.7 <= r.get("confidence", 0) < 0.9)
        low = sum(1 for r in compliance_results if r.get("confidence", 0) < 0.7)

        summary[f"A{row}"] = "High Confidence (>=0.90)"
        summary[f"B{row}"] = high
        row += 1
        summary[f"A{row}"] = "Medium Confidence (0.70-0.89)"
        summary[f"B{row}"] = medium
        row += 1
        summary[f"A{row}"] = "Low Confidence (<0.70)"
        summary[f"B{row}"] = low

        row += 2
        summary[f"A{row}"] = f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"

        summary.column_dimensions["A"].width = 35
        summary.column_dimensions["B"].width = 15

    def _generate_output_path(self, template_path: str, output_dir: str) -> str:
        template_name = Path(template_path).stem
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        output_filename = f"{template_name}_populated_{timestamp}.xlsx"
        return str(Path(output_dir) / output_filename)
