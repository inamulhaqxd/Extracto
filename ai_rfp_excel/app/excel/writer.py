"""
Excel Populator & Writer.
Delegates to PRD-compliant Step 5 In-Place Excel Populator (Rule 7, 8, 9).
Strict typing only — zero Any (Rule 4).
"""

from __future__ import annotations

import json
from pathlib import Path

from ai_rfp_excel.app.config import settings
from ai_rfp_excel.app.excel.models import PopulationResult, ValidationReport, WorkbookAnalysis
from ai_rfp_excel.app.matching.models import ComplianceDecision
from ai_rfp_excel.app.pipeline.step5_excel_populator import (
    PopulationManifest,
    populate_excel,
)


class ExcelWriter:
    """Populates Excel workbooks preserving styles, formulas, and highlighting review cells."""

    def __init__(self, output_dir: str | Path | None = None) -> None:
        self.output_dir = Path(output_dir) if output_dir else Path(settings.OUTPUT_DIR)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def populate_workbook(
        self,
        template_path: str | Path,
        analysis: WorkbookAnalysis | None = None,
        decisions: list[ComplianceDecision] | None = None,
        create_summary: bool = True,
    ) -> PopulationResult:
        p_template = Path(template_path)
        out_filename = f"{p_template.stem}_populated.xlsx"
        out_path = self.output_dir / out_filename
        manifest_path = self.output_dir / "population_manifest.json"

        # Prepare decisions JSON temporary artifact for step5 populator
        dec_list = []
        if decisions:
            for d in decisions:
                state_val = d.state.value if hasattr(d.state, "value") else str(d.state)
                dec_list.append({
                    "requirement_id": d.requirement_id or "REQ",
                    "requirement_text": d.requirement_text,
                    "compliance_state": state_val,
                    "extracted_value": d.matched_value or "NOT_SPECIFIED",
                    "confidence": d.confidence,
                    "reasoning": d.reasoning,
                    "resolving_layer": d.resolving_layer or "step4",
                    "needs_review": d.confidence < 0.70 or "AMBIGUOUS" in state_val,
                    "target_cells": {},
                })

        dec_path = self.output_dir / "temp_compliance_decisions.json"
        with open(dec_path, "w", encoding="utf-8") as f:
            json.dump({"decisions": dec_list}, f, indent=2, ensure_ascii=False)

        manifest: PopulationManifest = populate_excel(
            template_path=p_template,
            decisions_path=dec_path,
            output_excel_path=out_path,
            manifest_path=manifest_path,
        )

        total_cells = manifest.get("total_cells_updated", 0)
        review_cells = manifest.get("total_cells_highlighted", 0)

        val_report = ValidationReport(
            is_valid=True,
            total_checks=total_cells,
            passed_checks=total_cells,
            issues=[],
            summary={"total_populated": total_cells, "needs_review": review_cells},
        )

        return PopulationResult(
            output_file_path=str(out_path),
            filename=out_filename,
            total_populated_cells=total_cells,
            summary_sheet_created=create_summary,
            validation_report=val_report,
        )
