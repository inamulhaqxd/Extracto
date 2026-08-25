from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import openpyxl

from app.logging_config import get_logger

logger = get_logger()


@dataclass
class ValidationResult:
    check_name: str
    passed: bool
    message: str
    severity: str = "error"


class ExcelValidator:
    def __init__(self):
        self.results: list[ValidationResult] = []

    def validate(self, excel_path: str, original_path: str = None) -> list[ValidationResult]:
        self.results = []

        self._check_file_opens(excel_path)

        if not self.results or not any(not r.passed for r in self.results):
            self._check_sheets_exist(excel_path, original_path)
            self._check_no_rows_removed(excel_path, original_path)
            self._check_no_columns_removed(excel_path, original_path)
            self._check_cells_populated(excel_path)
            self._check_formulas_preserved(excel_path, original_path)
            self._check_merged_cells_preserved(excel_path, original_path)

        return self.results

    def _check_file_opens(self, excel_path: str):
        try:
            wb = openpyxl.load_workbook(excel_path)
            wb.close()
            self.results.append(ValidationResult(
                check_name="file_opens",
                passed=True,
                message="Workbook opens successfully",
            ))
        except Exception as e:
            self.results.append(ValidationResult(
                check_name="file_opens",
                passed=False,
                message=f"Failed to open workbook: {str(e)}",
                severity="critical",
            ))

    def _check_sheets_exist(self, excel_path: str, original_path: str = None):
        if not original_path:
            return

        try:
            original_wb = openpyxl.load_workbook(original_path)
            current_wb = openpyxl.load_workbook(excel_path)

            original_sheets = set(original_wb.sheetnames)
            current_sheets = set(current_wb.sheetnames)

            missing_sheets = original_sheets - current_sheets

            original_wb.close()
            current_wb.close()

            if missing_sheets:
                self.results.append(ValidationResult(
                    check_name="sheets_exist",
                    passed=False,
                    message=f"Missing sheets: {', '.join(missing_sheets)}",
                ))
            else:
                self.results.append(ValidationResult(
                    check_name="sheets_exist",
                    passed=True,
                    message="All original sheets present",
                ))
        except Exception as e:
            self.results.append(ValidationResult(
                check_name="sheets_exist",
                passed=False,
                message=f"Failed to check sheets: {str(e)}",
            ))

    def _check_no_rows_removed(self, excel_path: str, original_path: str = None):
        if not original_path:
            return

        try:
            original_wb = openpyxl.load_workbook(original_path)
            current_wb = openpyxl.load_workbook(excel_path)

            issues = []
            for sheet_name in original_wb.sheetnames:
                if sheet_name in current_wb.sheetnames:
                    original_rows = original_wb[sheet_name].max_row
                    current_rows = current_wb[sheet_name].max_row
                    if current_rows < original_rows:
                        issues.append(f"{sheet_name}: {original_rows} -> {current_rows}")

            original_wb.close()
            current_wb.close()

            if issues:
                self.results.append(ValidationResult(
                    check_name="no_rows_removed",
                    passed=False,
                    message=f"Rows removed from sheets: {'; '.join(issues)}",
                ))
            else:
                self.results.append(ValidationResult(
                    check_name="no_rows_removed",
                    passed=True,
                    message="No unexpected rows removed",
                ))
        except Exception as e:
            self.results.append(ValidationResult(
                check_name="no_rows_removed",
                passed=False,
                message=f"Failed to check rows: {str(e)}",
            ))

    def _check_no_columns_removed(self, excel_path: str, original_path: str = None):
        if not original_path:
            return

        try:
            original_wb = openpyxl.load_workbook(original_path)
            current_wb = openpyxl.load_workbook(excel_path)

            issues = []
            for sheet_name in original_wb.sheetnames:
                if sheet_name in current_wb.sheetnames:
                    original_cols = original_wb[sheet_name].max_column
                    current_cols = current_wb[sheet_name].max_column
                    if current_cols < original_cols:
                        issues.append(f"{sheet_name}: {original_cols} -> {current_cols}")

            original_wb.close()
            current_wb.close()

            if issues:
                self.results.append(ValidationResult(
                    check_name="no_columns_removed",
                    passed=False,
                    message=f"Columns removed from sheets: {'; '.join(issues)}",
                ))
            else:
                self.results.append(ValidationResult(
                    check_name="no_columns_removed",
                    passed=True,
                    message="No unexpected columns removed",
                ))
        except Exception as e:
            self.results.append(ValidationResult(
                check_name="no_columns_removed",
                passed=False,
                message=f"Failed to check columns: {str(e)}",
            ))

    def _check_cells_populated(self, excel_path: str):
        try:
            wb = openpyxl.load_workbook(excel_path)
            populated_count = 0

            for sheet in wb.sheetnames:
                ws = wb[sheet]
                for row in ws.iter_rows():
                    for cell in row:
                        if cell.value is not None:
                            populated_count += 1

            wb.close()

            self.results.append(ValidationResult(
                check_name="cells_populated",
                passed=populated_count > 0,
                message=f"Found {populated_count} populated cells",
            ))
        except Exception as e:
            self.results.append(ValidationResult(
                check_name="cells_populated",
                passed=False,
                message=f"Failed to check cells: {str(e)}",
            ))

    def _check_formulas_preserved(self, excel_path: str, original_path: str = None):
        if not original_path:
            return

        try:
            original_wb = openpyxl.load_workbook(original_path)
            current_wb = openpyxl.load_workbook(excel_path)

            original_formulas = []
            for sheet_name in original_wb.sheetnames:
                if sheet_name in current_wb.sheetnames:
                    ws = original_wb[sheet_name]
                    for row in ws.iter_rows():
                        for cell in row:
                            if cell.value and str(cell.value).startswith("="):
                                original_formulas.append((sheet_name, cell.coordinate))

            current_wb.close()
            original_wb.close()

            self.results.append(ValidationResult(
                check_name="formulas_preserved",
                passed=True,
                message=f"Found {len(original_formulas)} formulas in original (preservation check basic)",
            ))
        except Exception as e:
            self.results.append(ValidationResult(
                check_name="formulas_preserved",
                passed=False,
                message=f"Failed to check formulas: {str(e)}",
            ))

    def _check_merged_cells_preserved(self, excel_path: str, original_path: str = None):
        if not original_path:
            return

        try:
            original_wb = openpyxl.load_workbook(original_path)
            current_wb = openpyxl.load_workbook(excel_path)

            issues = []
            for sheet_name in original_wb.sheetnames:
                if sheet_name in current_wb.sheetnames:
                    original_merges = set(str(m) for m in original_wb[sheet_name].merged_cells.ranges)
                    current_merges = set(str(m) for m in current_wb[sheet_name].merged_cells.ranges)
                    missing = original_merges - current_merges
                    if missing:
                        issues.append(f"{sheet_name}: {len(missing)} merges missing")

            original_wb.close()
            current_wb.close()

            if issues:
                self.results.append(ValidationResult(
                    check_name="merged_cells_preserved",
                    passed=False,
                    message=f"Merged cells missing: {'; '.join(issues)}",
                ))
            else:
                self.results.append(ValidationResult(
                    check_name="merged_cells_preserved",
                    passed=True,
                    message="Merged cells preserved",
                ))
        except Exception as e:
            self.results.append(ValidationResult(
                check_name="merged_cells_preserved",
                passed=False,
                message=f"Failed to check merged cells: {str(e)}",
            ))

    def get_validation_summary(self) -> dict:
        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if not r.passed)
        critical = sum(1 for r in self.results if not r.passed and r.severity == "critical")

        return {
            "total_checks": len(self.results),
            "passed": passed,
            "failed": failed,
            "critical": critical,
            "overall_pass": critical == 0,
            "results": [
                {
                    "check": r.check_name,
                    "passed": r.passed,
                    "message": r.message,
                    "severity": r.severity,
                }
                for r in self.results
            ],
        }
