"""
PRD-Compliant Modular RFP PDF-to-Excel Pipeline.
Zero AI vision models (Rule 1). Zero Any (Rule 4). 100% offline (Rule 10).
"""

from ai_rfp_excel.app.pipeline.orchestrator import PipelineOrchestrator, PipelineResult
from ai_rfp_excel.app.pipeline.step1_pdf_extractor import NormalizedDocument, extract_pdf
from ai_rfp_excel.app.pipeline.step2_excel_analyzer import WorkbookAnalysis, analyze_workbook
from ai_rfp_excel.app.pipeline.step3_evidence_retriever import Step3Output, run_evidence_retrieval
from ai_rfp_excel.app.pipeline.step4_compliance_resolver import (
    ComplianceDecision,
    ComplianceState,
    Step4Output,
    resolve_compliance_batch,
)
from ai_rfp_excel.app.pipeline.step5_excel_populator import (
    PopulationManifest,
    populate_excel,
)

__all__ = [
    "ComplianceDecision",
    "ComplianceState",
    "NormalizedDocument",
    "PipelineOrchestrator",
    "PipelineResult",
    "PopulationManifest",
    "Step3Output",
    "Step4Output",
    "WorkbookAnalysis",
    "analyze_workbook",
    "extract_pdf",
    "populate_excel",
    "resolve_compliance_batch",
    "run_evidence_retrieval",
]
