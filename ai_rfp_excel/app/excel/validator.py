from pathlib import Path
from typing import Any

import openpyxl

from ai_rfp_excel.app.excel.models import (
    ValidationIssue,
    ValidationReport,
    ValidationSeverity,
    WorkbookAnalysis,
)
from ai_rfp_excel.app.logging import get_logger
from ai_rfp_excel.app.matching.models import ComplianceDecision

logger = get_logger("excel.validator")


class ExcelValidator:
    """Automated validator verifying integrity, evidence compliance, and structure of populated Excel files."""

    def validate(
        self,
        populated_path: str | Path,
        original_analysis: WorkbookAnalysis,
        decisions: list[ComplianceDecision],
    ) -> ValidationReport:
        path = Path(populated_path)
        issues: list[ValidationIssue] = []
        total_checks = 0
        passed_checks = 0

        # Check 1: Workbook file exists and opens successfully
        total_checks += 1
        if not path.exists():
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    message=f"Populated file does not exist: {populated_path}",
                    rule="file_existence",
                )
            )
            return ValidationReport(
                is_valid=False,
                total_checks=total_checks,
                passed_checks=0,
                issues=issues,
                summary={"error": "File not found"},
            )

        try:
            wb = openpyxl.load_workbook(path, data_only=False)
            passed_checks += 1
        except Exception as e:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    message=f"Failed to open workbook with openpyxl: {e}",
                    rule="workbook_loadable",
                )
            )
            return ValidationReport(
                is_valid=False,
                total_checks=total_checks,
                passed_checks=0,
                issues=issues,
                summary={"error": str(e)},
            )

        # Check 2: All original sheets still exist
        total_checks += 1
        missing_sheets = [s.sheet_name for s in original_analysis.sheets if s.sheet_name not in wb.sheetnames]
        if missing_sheets:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    message=f"Missing original sheets in populated workbook: {', '.join(missing_sheets)}",
                    rule="sheet_preservation",
                )
            )
        else:
            passed_checks += 1

        # Check 3: Compliance summary sheet was created
        total_checks += 1
        if "Compliance Summary" not in wb.sheetnames:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    message="Compliance Summary worksheet is missing.",
                    rule="summary_sheet_present",
                )
            )
        else:
            passed_checks += 1

        # Check 4: Verify requirement cells populated
        total_checks += 1
        unpopulated_cells: list[str] = []
        for sheet_analysis in original_analysis.sheets:
            if sheet_analysis.sheet_name not in wb.sheetnames:
                continue
            ws = wb[sheet_analysis.sheet_name]
            for req in sheet_analysis.requirements:
                for _, cell_coord in req.compliance_cells.items():
                    val = ws[cell_coord].value
                    if val is None or str(val).strip() == "":
                        unpopulated_cells.append(f"{sheet_analysis.sheet_name}!{cell_coord}")

        if unpopulated_cells:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    message=f"{len(unpopulated_cells)} target compliance cells remain empty (e.g. {unpopulated_cells[:3]}).",
                    rule="target_cells_populated",
                )
            )
        else:
            passed_checks += 1

        # Check 5: Evidence citations present for all decisions
        total_checks += 1
        missing_evidence_count = 0
        for d in decisions:
            if not d.evidence and not d.reasoning:
                missing_evidence_count += 1

        if missing_evidence_count > 0:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    message=f"{missing_evidence_count} decisions are missing evidence citations.",
                    rule="evidence_citation_presence",
                )
            )
        else:
            passed_checks += 1

        # Check 6: Flag low-confidence (< 70%) decisions for manual review
        total_checks += 1
        low_confidence_items = [d for d in decisions if d.confidence < 0.70]
        if low_confidence_items:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.INFO,
                    message=f"{len(low_confidence_items)} requirement(s) have confidence < 70% and should be reviewed manually.",
                    rule="low_confidence_flagged",
                )
            )
        passed_checks += 1

        is_valid = not any(issue.severity == ValidationSeverity.ERROR for issue in issues)

        summary: dict[str, Any] = {
            "is_valid": is_valid,
            "total_requirements": len(decisions),
            "total_issues": len(issues),
            "error_count": sum(1 for i in issues if i.severity == ValidationSeverity.ERROR),
            "warning_count": sum(1 for i in issues if i.severity == ValidationSeverity.WARNING),
            "info_count": sum(1 for i in issues if i.severity == ValidationSeverity.INFO),
            "low_confidence_count": len(low_confidence_items),
        }

        return ValidationReport(
            is_valid=is_valid,
            total_checks=total_checks,
            passed_checks=passed_checks,
            issues=issues,
            summary=summary,
        )
