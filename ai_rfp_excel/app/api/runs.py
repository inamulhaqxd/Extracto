import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_rfp_excel.app.api.deps import get_current_user
from ai_rfp_excel.app.config import settings
from ai_rfp_excel.app.database.connection import get_db
from ai_rfp_excel.app.database.models import (
    Document,
    DocumentPage,
    ExtractedFact,
    ProcessingRun,
    User,
    Workbook,
)
from ai_rfp_excel.app.excel.analyzer import ExcelAnalyzer
from ai_rfp_excel.app.excel.models import WorkbookAnalysis
from ai_rfp_excel.app.excel.writer import ExcelWriter
from ai_rfp_excel.app.logging import get_logger
from ai_rfp_excel.app.matching.engine import ComplianceEngine
from ai_rfp_excel.app.matching.models import (
    ComplianceDecision,
    ComplianceState,
    FactItem,
)

logger = get_logger("api.runs")
router = APIRouter(prefix="/runs", tags=["runs"])

excel_analyzer = ExcelAnalyzer()
excel_writer = ExcelWriter()
compliance_engine = ComplianceEngine()


class CreateRunRequest(BaseModel):
    model_config = {"protected_namespaces": ()}
    pdf_document_id: str
    workbook_id: str
    model_name: str | None = None
    vendor_name: str | None = None


class ReviewItem(BaseModel):
    model_config = {"protected_namespaces": ()}
    requirement_id: str
    status: str
    matched_value: str | None = None
    confidence: float | None = None
    review_notes: str | None = None
    override_reason: str | None = None


class SubmitReviewRequest(BaseModel):
    model_config = {"protected_namespaces": ()}
    reviews: list[ReviewItem]


class RunDecisionResponse(BaseModel):
    model_config = {"protected_namespaces": ()}
    requirement_id: str
    requirement_text: str
    section: str | None = None
    status: str
    confidence: float
    reasoning: str | None = None
    matched_value: str | None = None
    resolving_layer: str | None = None
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    needs_review: bool = False
    review_notes: str | None = None


class RunResponse(BaseModel):
    model_config = {"protected_namespaces": ()}
    run_id: str
    status: str
    progress: float
    current_step: str | None = None
    model_used: str | None = None
    pdf_filename: str | None = None
    workbook_filename: str | None = None
    generated_file: str | None = None
    total_requirements: int = 0
    compliant_count: int = 0
    non_compliant_count: int = 0
    ambiguous_count: int = 0
    not_found_count: int = 0
    low_confidence_count: int = 0
    decisions: list[RunDecisionResponse] = Field(default_factory=list)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None


async def execute_pipeline_background(
    run_id: uuid.UUID,
    pdf_doc_id: uuid.UUID,
    wb_id: uuid.UUID,
    model_name: str | None,
    vendor_name: str | None,
    db: AsyncSession,
) -> None:
    """Execute end-to-end extraction, matching, and excel population pipeline."""
    try:
        # Step 1: Initialize run record
        run_res = await db.execute(select(ProcessingRun).where(ProcessingRun.id == run_id))
        run = run_res.scalar_one_or_none()
        if not run or run.status == "cancelled":
            return

        run.status = "processing"
        run.started_at = datetime.now()
        run.progress = 10.0
        run.current_step = "Analyzing Excel template and mapping empty slots"
        await db.commit()

        # Step 2: Load and analyze Excel workbook
        wb_res = await db.execute(select(Workbook).where(Workbook.id == wb_id))
        wb_record = wb_res.scalar_one_or_none()
        if not wb_record:
            raise ValueError(f"Workbook {wb_id} not found")

        wb_path = Path(settings.UPLOAD_DIR) / wb_record.filename
        if not wb_path.exists():
            raise FileNotFoundError(f"Workbook file {wb_path} not found")

        analysis: WorkbookAnalysis = excel_analyzer.analyze_workbook(
            file_path=str(wb_path),
            workbook_id=str(wb_id),
            version=wb_record.version,
        )

        run.progress = 30.0
        run.current_step = "Extracting technical specifications from reference PDF"
        await db.commit()

        # Step 3: Fetch facts / pages from PDF document, or extract if not yet ingested
        facts: list[FactItem] = []
        facts_res = await db.execute(select(ExtractedFact).where(ExtractedFact.document_id == pdf_doc_id))
        db_facts = facts_res.scalars().all()
        for f in db_facts:
            facts.append(
                FactItem(
                    id=str(f.id),
                    field_name=f.field_name,
                    value=f.normalized_value or f.original_value,
                    source_document_id=str(f.document_id),
                    source_page=f.source_page,
                    source_table_id=f.source_table_id,
                    source_image_id=f.source_image_id,
                    source_type=f.source_type,
                    confidence=f.confidence,
                    extraction_method=f.extraction_method,
                    metadata_json=f.metadata_json,
                )
            )

        if not facts:
            # Fallback to document pages text or extract directly from PDF file
            pages_res = await db.execute(select(DocumentPage).where(DocumentPage.document_id == pdf_doc_id))
            db_pages = pages_res.scalars().all()
            for p in db_pages:
                text = p.native_text or p.ocr_text
                if text:
                    facts.append(
                        FactItem(
                            field_name="Technical Spec",
                            value=text,
                            source_document_id=str(p.document_id),
                            source_page=p.page_number,
                            source_type=p.content_type,
                            confidence=0.90,
                        )
                    )

        if not facts:
            # Automatically extract text and specs directly from the uploaded PDF file
            doc_res = await db.execute(select(Document).where(Document.id == pdf_doc_id))
            doc_rec = doc_res.scalar_one_or_none()
            if doc_rec:
                pdf_path = Path(settings.UPLOAD_DIR) / doc_rec.filename
                if not pdf_path.exists():
                    pdf_path = Path(settings.UPLOAD_DIR) / f"{pdf_doc_id}.pdf"

                if pdf_path.exists():
                    import fitz
                    fitz_doc = fitz.open(str(pdf_path))
                    for p_num in range(len(fitz_doc)):
                        page = fitz_doc[p_num]
                        page_text = page.get_text()
                        page_index = p_num + 1
                        if page_text and page_text.strip():
                            doc_page = DocumentPage(
                                document_id=pdf_doc_id,
                                page_number=page_index,
                                content_type="text",
                                native_text=page_text,
                                is_scanned=False,
                            )
                            db.add(doc_page)

                            # Extract bullet points / line specs
                            lines = [ln.strip() for ln in page_text.split("\n") if len(ln.strip()) >= 3]
                            for line in lines:
                                if ":" in line:
                                    parts = line.split(":", 1)
                                    f_name = parts[0].strip()
                                    f_val = parts[1].strip()
                                else:
                                    f_name = "Technical Specification"
                                    f_val = line

                                fact_item = FactItem(
                                    field_name=f_name,
                                    value=f_val,
                                    source_document_id=str(pdf_doc_id),
                                    source_page=page_index,
                                    source_type="text",
                                    confidence=0.95,
                                    extraction_method="pdf_ingestion",
                                )
                                facts.append(fact_item)

                                ef = ExtractedFact(
                                    document_id=pdf_doc_id,
                                    source_page=page_index,
                                    field_name=f_name,
                                    original_value=f_val,
                                    normalized_value=f_val,
                                    confidence=0.95,
                                    extraction_method="pdf_ingestion",
                                    source_type="text",
                                )
                                db.add(ef)
                    fitz_doc.close()
                    await db.commit()

        run.progress = 50.0
        run.current_step = f"Evaluating {analysis.total_requirements} requirements with Compliance Engine"
        await db.commit()

        # Step 4: Evaluate requirements against facts
        all_decisions: list[ComplianceDecision] = []
        all_requirements = [req for s in analysis.sheets for req in s.requirements]
        total_reqs = len(all_requirements)

        for idx, req in enumerate(all_requirements, start=1):
            # Check if run was cancelled in the meantime
            chk_res = await db.execute(select(ProcessingRun.status).where(ProcessingRun.id == run_id))
            curr_status = chk_res.scalar_one_or_none()
            if curr_status == "cancelled":
                logger.info("Run was cancelled during processing", run_id=str(run_id))
                return

            dec = await compliance_engine.evaluate_requirement(
                requirement_text=req.requirement_text,
                facts=facts,
                vendor_name=vendor_name,
                model_name=model_name,
                requirement_id=req.requirement_id,
            )
            all_decisions.append(dec)

            # Update progress incrementally
            progress_pct = 50.0 + (35.0 * (idx / max(total_reqs, 1)))
            run.progress = round(progress_pct, 1)
            run.current_step = f"Evaluating requirement {idx}/{total_reqs}: {req.requirement_text[:40]}..."
            await db.commit()

        # Step 5: Populate initial Excel output and validate
        run.progress = 90.0
        run.current_step = "Populating Excel workbook and generating Compliance Summary"
        await db.commit()

        pop_result = excel_writer.populate_workbook(
            template_path=wb_path,
            analysis=analysis,
            decisions=all_decisions,
        )

        # Step 6: Complete run record
        run.status = "completed"
        run.progress = 100.0
        run.current_step = "Completed successfully. Ready for review and download."
        run.completed_at = datetime.now()
        run.metadata_json = {
            "vendor_name": vendor_name,
            "generated_file": pop_result.filename,
            "generated_file_path": pop_result.output_file_path,
            "total_requirements": total_reqs,
            "decisions": [d.model_dump() for d in all_decisions],
            "validation": pop_result.validation_report.model_dump(),
        }
        await db.commit()
        logger.info("Pipeline run completed successfully", run_id=str(run_id), generated_file=pop_result.filename)

    except Exception as e:
        logger.error("Pipeline execution failed", run_id=str(run_id), error=str(e), exc_info=True)
        run_res = await db.execute(select(ProcessingRun).where(ProcessingRun.id == run_id))
        run = run_res.scalar_one_or_none()
        if run:
            run.status = "failed"
            run.error_message = str(e)
            run.current_step = f"Failed: {e!s}"
            run.completed_at = datetime.now()
            await db.commit()


@router.post("", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
async def create_processing_run(
    request: CreateRunRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RunResponse:
    """Create and start a new processing run."""
    try:
        pdf_uuid = uuid.UUID(request.pdf_document_id)
        wb_uuid = uuid.UUID(request.workbook_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid UUID format: {e}",
        ) from e

    # Verify PDF and Workbook exist
    pdf_res = await db.execute(select(Document).where(Document.id == pdf_uuid))
    pdf_doc = pdf_res.scalar_one_or_none()
    if not pdf_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PDF Document not found")

    wb_res = await db.execute(select(Workbook).where(Workbook.id == wb_uuid))
    wb_record = wb_res.scalar_one_or_none()
    if not wb_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workbook not found")

    selected_model = request.model_name or settings.DEFAULT_LLM_MODEL
    run_id = uuid.uuid4()

    run = ProcessingRun(
        id=run_id,
        user_id=current_user.id,
        pdf_document_id=pdf_uuid,
        workbook_id=wb_uuid,
        status="pending",
        progress=0.0,
        current_step="Queued for processing",
        model_used=selected_model,
        started_at=datetime.now(),
        metadata_json={
            "vendor_name": request.vendor_name,
            "pdf_filename": pdf_doc.original_filename,
            "workbook_filename": wb_record.original_filename,
        },
    )
    db.add(run)
    await db.commit()

    # Launch background task
    background_tasks.add_task(
        execute_pipeline_background,
        run_id=run_id,
        pdf_doc_id=pdf_uuid,
        wb_id=wb_uuid,
        model_name=selected_model,
        vendor_name=request.vendor_name,
        db=db,
    )

    return RunResponse(
        run_id=str(run_id),
        status="pending",
        progress=0.0,
        current_step="Queued for processing",
        model_used=selected_model,
        pdf_filename=pdf_doc.original_filename,
        workbook_filename=wb_record.original_filename,
        started_at=run.started_at,
    )


@router.get("/{run_id}", response_model=RunResponse)
async def get_run_status(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RunResponse:
    """Get status, progress, decisions, and results of a processing run."""
    try:
        run_uuid = uuid.UUID(run_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid run_id format") from e

    res = await db.execute(select(ProcessingRun).where(ProcessingRun.id == run_uuid))
    run = res.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    meta = run.metadata_json or {}
    raw_decisions = meta.get("decisions", [])

    decisions_list: list[RunDecisionResponse] = []
    comp_cnt = 0
    non_comp_cnt = 0
    amb_cnt = 0
    nf_cnt = 0
    low_conf_cnt = 0

    for d in raw_decisions:
        state_val = str(d.get("state", "NOT_FOUND"))
        conf = float(d.get("confidence", 1.0))

        if "COMPLIANT" in state_val and "NON" not in state_val and "PARTIAL" not in state_val:
            comp_cnt += 1
        elif "NON_COMPLIANT" in state_val:
            non_comp_cnt += 1
        elif "AMBIGUOUS" in state_val or "PARTIAL" in state_val:
            amb_cnt += 1
        else:
            nf_cnt += 1

        if conf < 0.70:
            low_conf_cnt += 1

        decisions_list.append(
            RunDecisionResponse(
                requirement_id=d.get("requirement_id") or "REQ",
                requirement_text=d.get("requirement_text") or "",
                section=d.get("section"),
                status=state_val,
                confidence=conf,
                reasoning=d.get("reasoning"),
                matched_value=d.get("matched_value"),
                resolving_layer=d.get("resolving_layer"),
                evidence=d.get("evidence", []),
                needs_review=conf < 0.70 or "AMBIGUOUS" in state_val,
                review_notes=d.get("review_notes"),
            )
        )

    return RunResponse(
        run_id=str(run.id),
        status=run.status,
        progress=run.progress,
        current_step=run.current_step,
        model_used=run.model_used,
        pdf_filename=meta.get("pdf_filename"),
        workbook_filename=meta.get("workbook_filename"),
        generated_file=meta.get("generated_file"),
        total_requirements=len(decisions_list),
        compliant_count=comp_cnt,
        non_compliant_count=non_comp_cnt,
        ambiguous_count=amb_cnt,
        not_found_count=nf_cnt,
        low_confidence_count=low_conf_cnt,
        decisions=decisions_list,
        started_at=run.started_at,
        completed_at=run.completed_at,
        error_message=run.error_message,
    )


@router.post("/{run_id}/cancel")
async def cancel_run(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Cancel an ongoing processing run."""
    try:
        run_uuid = uuid.UUID(run_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid run_id format") from e

    res = await db.execute(select(ProcessingRun).where(ProcessingRun.id == run_uuid))
    run = res.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    run.status = "cancelled"
    run.current_step = "Cancelled by user"
    run.completed_at = datetime.now()
    await db.commit()

    return {"message": "Run marked as cancelled", "run_id": run_id, "status": "cancelled"}


@router.post("/{run_id}/review", response_model=RunResponse)
async def submit_run_review(
    run_id: str,
    review_req: SubmitReviewRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RunResponse:
    """Apply human reviewer overrides and update the populated workbook."""
    try:
        run_uuid = uuid.UUID(run_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid run_id format") from e

    res = await db.execute(select(ProcessingRun).where(ProcessingRun.id == run_uuid))
    run = res.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    meta = run.metadata_json or {}
    decisions_raw = meta.get("decisions", [])
    reviews_by_req = {r.requirement_id: r for r in review_req.reviews}

    # Apply overrides
    updated_decisions: list[ComplianceDecision] = []
    for d_dict in decisions_raw:
        req_id = d_dict.get("requirement_id")
        dec = ComplianceDecision(**d_dict)

        if req_id in reviews_by_req:
            rev = reviews_by_req[req_id]
            # Map status string to ComplianceState
            for state in ComplianceState:
                if state.value.lower() == rev.status.lower() or state.name.lower() == rev.status.lower():
                    dec.state = state
                    break
            if rev.matched_value is not None:
                dec.matched_value = rev.matched_value
            if rev.confidence is not None:
                dec.confidence = rev.confidence
            if rev.review_notes:
                dec.reasoning = f"{dec.reasoning} [Reviewer Note: {rev.review_notes}]"

        updated_decisions.append(dec)

    # Re-populate workbook with updated decisions
    if run.workbook_id:
        wb_res = await db.execute(select(Workbook).where(Workbook.id == run.workbook_id))
        wb_rec = wb_res.scalar_one_or_none()
        if wb_rec:
            wb_path = Path(settings.UPLOAD_DIR) / wb_rec.filename
            analysis = excel_analyzer.analyze_workbook(str(wb_path), str(wb_rec.id), wb_rec.version)
            pop_res = excel_writer.populate_workbook(wb_path, analysis, updated_decisions)
            meta["generated_file"] = pop_res.filename
            meta["generated_file_path"] = pop_res.output_file_path

    meta["decisions"] = [d.model_dump() for d in updated_decisions]
    run.metadata_json = meta
    await db.commit()

    return await get_run_status(run_id, current_user, db)


@router.get("", response_model=list[RunResponse])
async def list_runs(
    status_filter: str | None = Query(None, alias="status"),
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[RunResponse]:
    """List processing runs for the current user."""
    stmt = select(ProcessingRun).order_by(desc(ProcessingRun.created_at)).limit(limit).offset(offset)
    if status_filter:
        stmt = stmt.where(ProcessingRun.status == status_filter)

    res = await db.execute(stmt)
    runs = res.scalars().all()

    output = []
    for r in runs:
        meta = r.metadata_json or {}
        decisions_raw = meta.get("decisions", [])
        output.append(
            RunResponse(
                run_id=str(r.id),
                status=r.status,
                progress=r.progress,
                current_step=r.current_step,
                model_used=r.model_used,
                pdf_filename=meta.get("pdf_filename"),
                workbook_filename=meta.get("workbook_filename"),
                generated_file=meta.get("generated_file"),
                total_requirements=len(decisions_raw),
                started_at=r.started_at,
                completed_at=r.completed_at,
                error_message=r.error_message,
            )
        )
    return output
