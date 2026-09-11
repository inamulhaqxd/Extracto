#!/usr/bin/env python3
"""
Pipeline Orchestrator: Unified coordinator executing Steps 1 through 5.
Saves human-readable, validated JSON artifacts between all phases (Rule 8).
Zero external cloud API calls (Rule 10). Zero Any (Rule 4).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from ai_rfp_excel.app.pipeline.step1_pdf_extractor import NormalizedDocument, extract_pdf
from ai_rfp_excel.app.pipeline.step2_excel_analyzer import WorkbookAnalysis, analyze_workbook
from ai_rfp_excel.app.pipeline.step3_evidence_retriever import run_evidence_retrieval
from ai_rfp_excel.app.pipeline.step4_compliance_resolver import (
    Step4Output,
    resolve_compliance_batch,
)
from ai_rfp_excel.app.pipeline.step5_excel_populator import (
    PopulationManifest,
    populate_excel,
)

logger = logging.getLogger("PipelineOrchestrator")


@dataclass(frozen=True)
class PipelineResult:
    pdf_path: str
    excel_path: str
    output_excel_path: str
    output_dir: str
    total_requirements: int
    compliant_count: int
    partially_compliant_count: int
    non_compliant_count: int
    not_found_count: int
    ambiguous_count: int
    needs_review_count: int
    elapsed_seconds: float
    manifest: PopulationManifest


class PipelineOrchestrator:
    """Orchestrates Steps 1 through 5 of the RFP PDF-to-Excel pipeline."""

    def __init__(
        self,
        progress_callback: Callable[[float, str], Awaitable[None]] | None = None,
    ) -> None:
        self.progress_callback = progress_callback

    async def _report_progress(self, progress: float, message: str) -> None:
        logger.info("Pipeline progress %.1f%%: %s", progress, message)
        if self.progress_callback:
            try:
                await self.progress_callback(progress, message)
            except Exception as e:
                logger.warning("Progress callback failed: %s", e)

    async def run(
        self,
        pdf_path: Path | str,
        excel_path: Path | str,
        output_dir: Path | str = "output",
        output_excel_path: Path | str | None = None,
        model_name: str | None = None,
        enable_ocr: bool = True,
        top_k: int = 5,
        concurrency: int = 2,
    ) -> PipelineResult:
        start_time = time.time()
        p_pdf = Path(pdf_path).resolve()
        p_excel = Path(excel_path).resolve()
        p_out_dir = Path(output_dir).resolve()
        p_out_dir.mkdir(parents=True, exist_ok=True)

        if not p_pdf.exists():
            raise FileNotFoundError(f"PDF file not found: {p_pdf}")
        if not p_excel.exists():
            raise FileNotFoundError(f"Excel file not found: {p_excel}")

        if output_excel_path is None:
            stem = p_excel.stem
            out_excel = p_out_dir / f"{stem}_populated.xlsx"
        else:
            out_excel = Path(output_excel_path).resolve()

        # Step 1: PDF Fact & Table Extraction
        await self._report_progress(10.0, "Step 1: Extracting text, tables, and metadata from PDF")
        pdf_json_path = p_out_dir / "pdf_output.json"
        loop = asyncio.get_running_loop()
        norm_doc: NormalizedDocument = await loop.run_in_executor(
            None, extract_pdf, p_pdf, enable_ocr
        )
        with open(pdf_json_path, "w", encoding="utf-8") as f:
            json.dump(norm_doc, f, indent=2, ensure_ascii=False)

        # Step 2: Dynamic Excel Parsing
        await self._report_progress(30.0, "Step 2: Analyzing Excel template headers and requirements")
        excel_json_path = p_out_dir / "excel_analysis.json"
        wb_analysis: WorkbookAnalysis = await loop.run_in_executor(
            None, analyze_workbook, p_excel
        )
        with open(excel_json_path, "w", encoding="utf-8") as f:
            json.dump(wb_analysis, f, indent=2, ensure_ascii=False)

        total_reqs = wb_analysis.get("total_requirements", 0)

        # Step 3: Evidence Retrieval (Vector Search)
        await self._report_progress(50.0, f"Step 3: Matching evidence for {total_reqs} requirement(s)")
        evidence_json_path = p_out_dir / "candidate_evidence.json"
        await loop.run_in_executor(
            None,
            run_evidence_retrieval,
            pdf_json_path,
            excel_json_path,
            evidence_json_path,
            top_k,
            True,
        )

        # Step 4: Compliance Resolution (Stage 1/2 Rules + Stage 3 Ollama LLM)
        await self._report_progress(70.0, "Step 4: Evaluating compliance decisions and extracting values")
        decisions_json_path = p_out_dir / "compliance_decisions.json"
        decisions_output: Step4Output = await loop.run_in_executor(
            None,
            resolve_compliance_batch,
            evidence_json_path,
            decisions_json_path,
            model_name or "qwen2.5:1.5b",
            True,
        )

        # Step 5: In-Place Excel Population & Styling
        await self._report_progress(90.0, "Step 5: Populating Excel workbook with style preservation")
        manifest_json_path = p_out_dir / "population_manifest.json"
        manifest: PopulationManifest = await loop.run_in_executor(
            None,
            populate_excel,
            p_excel,
            decisions_json_path,
            out_excel,
            manifest_json_path,
        )

        elapsed = time.time() - start_time
        await self._report_progress(100.0, "Pipeline completed successfully")

        return PipelineResult(
            pdf_path=str(p_pdf),
            excel_path=str(p_excel),
            output_excel_path=str(out_excel),
            output_dir=str(p_out_dir),
            total_requirements=total_reqs,
            compliant_count=int(decisions_output.get("compliant_count", 0)),
            partially_compliant_count=int(decisions_output.get("partially_compliant_count", 0)),
            non_compliant_count=int(decisions_output.get("non_compliant_count", 0)),
            not_found_count=int(decisions_output.get("not_specified_count", 0)),
            ambiguous_count=int(decisions_output.get("ambiguous_count", 0)),
            needs_review_count=int(manifest.get("total_cells_highlighted", 0)),
            elapsed_seconds=elapsed,
            manifest=manifest,
        )
