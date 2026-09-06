import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_rfp_excel.app.api.deps import get_current_user, get_current_user_flexible
from ai_rfp_excel.app.config import settings
from ai_rfp_excel.app.database.connection import async_session, get_db
from ai_rfp_excel.app.database.models import (
    Document,
    ProcessingRun,
    User,
    Workbook,
)
from ai_rfp_excel.app.logging import get_logger
from ai_rfp_excel.app.pipeline.orchestrator import PipelineOrchestrator
from ai_rfp_excel.app.pipeline.step5_excel_populator import populate_excel

logger = get_logger("api.runs")
router = APIRouter(prefix="/runs", tags=["runs"])


class CreateRunRequest(BaseModel):
    model_config = {"protected_namespaces": ()}
    pdf_document_id: str
    workbook_id: str
    model_name: str | None = None
    vendor_name: str | None = None
    include_summary_sheet: bool = True


class ReviewItem(BaseModel):
    model_config = {"protected_namespaces": ()}
    requirement_id: str
    status: str
    matched_value: str | None = None
    confidence: float | None = None
    review_notes: str | None = None


class SubmitReviewRequest(BaseModel):
    model_config = {"protected_namespaces": ()}
    reviews: list[ReviewItem]


class EvidenceItemResponse(BaseModel):
    citation: str
    value: str
    location: str | None = None


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
    evidence: list[dict[str, object]] = Field(default_factory=list)
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
    include_summary_sheet: bool,
) -> None:
    """Execute end-to-end extraction, matching, and excel population pipeline."""
    async with async_session() as db:
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

            # Step 3: Locate PDF document file
            doc_res = await db.execute(select(Document).where(Document.id == pdf_doc_id))
            doc_rec = doc_res.scalar_one_or_none()
            if not doc_rec:
                raise ValueError(f"PDF Document {pdf_doc_id} not found")

            pdf_path = Path(settings.UPLOAD_DIR) / doc_rec.filename
            if not pdf_path.exists():
                pdf_path = Path(settings.UPLOAD_DIR) / f"{pdf_doc_id}.pdf"
            if not pdf_path.exists():
                raise FileNotFoundError(f"PDF file {pdf_path} not found")

            output_dir = Path(settings.GENERATED_DIR) / str(run_id)
            output_dir.mkdir(parents=True, exist_ok=True)
            out_excel_path = output_dir / f"{wb_path.stem}_populated.xlsx"

            async def on_progress(progress: float, message: str) -> None:
                chk = await db.execute(select(ProcessingRun).where(ProcessingRun.id == run_id))
                curr_run = chk.scalar_one_or_none()
                if not curr_run or curr_run.status == "cancelled":
                    raise asyncio.CancelledError("Run cancelled by user")
                curr_run.progress = progress
                curr_run.current_step = message
                await db.commit()

            orchestrator = PipelineOrchestrator(progress_callback=on_progress)
            pipeline_res = await orchestrator.run(
                pdf_path=pdf_path,
                excel_path=wb_path,
                output_dir=output_dir,
                output_excel_path=out_excel_path,
                model_name=model_name,
            )

            decisions_json_path = output_dir / "compliance_decisions.json"
            raw_decisions: list[dict[str, object]] = []
            if decisions_json_path.exists():
                with open(decisions_json_path, "r", encoding="utf-8") as f:
                    dec_data = json.load(f)
                    raw_decisions = dec_data.get("items") or dec_data.get("decisions") or []

            run_res_final = await db.execute(select(ProcessingRun).where(ProcessingRun.id == run_id))
            final_run = run_res_final.scalar_one_or_none()
            if not final_run:
                return

            final_run.status = "completed"
            final_run.progress = 100.0
            final_run.current_step = "Completed successfully. Ready for review and download."
            final_run.completed_at = datetime.now()
            final_run.metadata_json = {
                "vendor_name": vendor_name,
                "pdf_filename": doc_rec.original_filename,
                "workbook_filename": wb_record.original_filename,
                "generated_file": out_excel_path.name,
                "generated_file_path": str(out_excel_path),
                "total_requirements": pipeline_res.total_requirements,
                "decisions": raw_decisions,
                "manifest": pipeline_res.manifest,
            }
            await db.commit()
            logger.info("Pipeline run completed successfully", run_id=str(run_id), generated_file=out_excel_path.name)

        except asyncio.CancelledError:
            logger.info("Pipeline run cancelled by user", run_id=str(run_id))
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

    selected_model = request.model_name
    if not selected_model:
        meta = current_user.metadata_json if hasattr(current_user, "metadata_json") and current_user.metadata_json else {}
        if isinstance(meta, dict) and meta.get("preferred_llm_model"):
            selected_model = str(meta["preferred_llm_model"])
        else:
            selected_model = settings.DEFAULT_LLM_MODEL

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

    # Launch background task with its own independent session
    background_tasks.add_task(
        execute_pipeline_background,
        run_id=run_id,
        pdf_doc_id=pdf_uuid,
        wb_id=wb_uuid,
        model_name=selected_model,
        vendor_name=request.vendor_name,
        include_summary_sheet=request.include_summary_sheet,
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
    raw_decisions = meta.get("decisions")
    decisions_items: list[dict[str, object]] = []
    if isinstance(raw_decisions, list) and len(raw_decisions) > 0:
        for item in raw_decisions:
            if isinstance(item, dict):
                decisions_items.append({str(k): v for k, v in item.items()})
    else:
        decisions_json_path = Path(settings.GENERATED_DIR) / str(run.id) / "compliance_decisions.json"
        if decisions_json_path.exists():
            try:
                with open(decisions_json_path, "r", encoding="utf-8") as f:
                    disk_data = json.load(f)
                    disk_items = disk_data.get("items") or disk_data.get("decisions") or []
                    if isinstance(disk_items, list):
                        for item in disk_items:
                            if isinstance(item, dict):
                                decisions_items.append({str(k): v for k, v in item.items()})
            except Exception:
                pass

    decisions_list: list[RunDecisionResponse] = []
    comp_cnt = 0
    non_comp_cnt = 0
    amb_cnt = 0
    nf_cnt = 0
    low_conf_cnt = 0

    for d in decisions_items:
        state_val = str(d.get("compliance_state") or d.get("state") or d.get("status") or "NOT_FOUND")
        conf_raw = d.get("confidence")
        conf = float(str(conf_raw)) if conf_raw is not None else 1.0
        m_val = str(d.get("extracted_value") or d.get("matched_value")) if (d.get("extracted_value") or d.get("matched_value")) else None
        reasoning_val = str(d.get("reasoning") or d.get("remarks") or "") if (d.get("reasoning") or d.get("remarks")) else None

        if "COMPLIANT" in state_val and "NON" not in state_val and "PARTIAL" not in state_val:
            comp_cnt += 1
        elif "NON_COMPLIANT" in state_val:
            non_comp_cnt += 1
        elif "AMBIGUOUS" in state_val or "PARTIAL" in state_val:
            amb_cnt += 1
        else:
            nf_cnt += 1

        if conf < 0.70 or d.get("needs_review"):
            low_conf_cnt += 1

        ev_raw = d.get("evidence")
        ev_list: list[dict[str, object]] = []
        if isinstance(ev_raw, list):
            for ev_item in ev_raw:
                if isinstance(ev_item, dict):
                    ev_list.append({str(k): v for k, v in ev_item.items()})
        elif d.get("citation"):
            ev_list.append({
                "citation": str(d.get("citation")),
                "value": m_val or "",
                "location": str(d.get("sheet_name") or ""),
            })

        decisions_list.append(
            RunDecisionResponse(
                requirement_id=str(d.get("requirement_id") or "REQ"),
                requirement_text=str(d.get("requirement_text") or ""),
                section=str(d.get("section")) if d.get("section") else None,
                status=state_val,
                confidence=conf,
                reasoning=reasoning_val,
                matched_value=m_val,
                resolving_layer=str(d.get("resolving_layer")) if d.get("resolving_layer") else None,
                evidence=ev_list,
                needs_review=bool(d.get("needs_review") or conf < 0.70 or "AMBIGUOUS" in state_val),
                review_notes=str(d.get("review_notes")) if d.get("review_notes") else None,
            )
        )

    return RunResponse(
        run_id=str(run.id),
        status=run.status,
        progress=run.progress,
        current_step=run.current_step,
        model_used=run.model_used,
        pdf_filename=str(meta["pdf_filename"]) if meta.get("pdf_filename") else None,
        workbook_filename=str(meta["workbook_filename"]) if meta.get("workbook_filename") else None,
        generated_file=str(meta["generated_file"]) if meta.get("generated_file") else None,
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
    decisions_raw = meta.get("decisions")
    reviews_by_req = {r.requirement_id: r for r in review_req.reviews}

    # Apply overrides
    updated_decisions: list[dict[str, object]] = []
    if isinstance(decisions_raw, list):
        for d_dict in decisions_raw:
            if not isinstance(d_dict, dict):
                continue
            item: dict[str, object] = {str(k): v for k, v in d_dict.items()}
            req_id = str(item.get("requirement_id") or "")

            if req_id in reviews_by_req:
                rev = reviews_by_req[req_id]
                item["compliance_state"] = rev.status.upper()
                item["status"] = rev.status.upper()
                if rev.matched_value is not None:
                    item["extracted_value"] = rev.matched_value
                    item["matched_value"] = rev.matched_value
                if rev.confidence is not None:
                    item["confidence"] = rev.confidence
                if rev.review_notes:
                    item["review_notes"] = rev.review_notes
                    reason_base = str(item.get("reasoning") or "")
                    item["reasoning"] = f"{reason_base} [Reviewer Note: {rev.review_notes}]"
                item["needs_review"] = False

            updated_decisions.append(item)

    # Re-populate workbook with updated decisions
    if run.workbook_id:
        wb_res = await db.execute(select(Workbook).where(Workbook.id == run.workbook_id))
        wb_rec = wb_res.scalar_one_or_none()
        if wb_rec:
            wb_path = Path(settings.UPLOAD_DIR) / wb_rec.filename
            output_dir = Path(settings.GENERATED_DIR) / str(run_id)
            output_dir.mkdir(parents=True, exist_ok=True)
            decisions_json_path = output_dir / "compliance_decisions.json"
            with open(decisions_json_path, "w", encoding="utf-8") as f:
                json.dump({"items": updated_decisions, "decisions": updated_decisions}, f, indent=2, ensure_ascii=False)
            out_excel_path = output_dir / f"{wb_path.stem}_populated.xlsx"
            manifest_json_path = output_dir / "population_manifest.json"
            populate_excel(wb_path, decisions_json_path, out_excel_path, manifest_json_path)
            meta["generated_file"] = out_excel_path.name
            meta["generated_file_path"] = str(out_excel_path)

    meta["decisions"] = updated_decisions
    run.metadata_json = meta
    await db.commit()

    return await get_run_status(run_id, current_user, db)


@router.get("/{run_id}/download")
async def download_run_excel(
    run_id: str,
    current_user: User = Depends(get_current_user_flexible),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Download populated Excel file for a specific run."""
    try:
        run_uuid = uuid.UUID(run_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid run_id format") from e

    res = await db.execute(select(ProcessingRun).where(ProcessingRun.id == run_uuid))
    run = res.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    meta = run.metadata_json or {}
    gen_file_path_str = meta.get("generated_file_path")
    file_path: Path | None = None
    if gen_file_path_str:
        p = Path(str(gen_file_path_str))
        if p.exists():
            file_path = p

    if not file_path:
        run_dir = Path(settings.GENERATED_DIR) / str(run_uuid)
        if run_dir.exists():
            candidates = list(run_dir.glob("*_populated.xlsx"))
            if candidates:
                file_path = candidates[0]

    if not file_path or not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Populated Excel file not found on server")

    download_name = str(meta.get("workbook_filename") or file_path.name)
    if not download_name.endswith(".xlsx"):
        download_name += ".xlsx"
    if "_populated" not in download_name:
        stem = Path(download_name).stem
        download_name = f"{stem}_populated.xlsx"

    return FileResponse(
        path=str(file_path),
        filename=download_name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


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
        decisions_raw = meta.get("decisions")
        decisions_len = len(decisions_raw) if isinstance(decisions_raw, list) else 0
        output.append(
            RunResponse(
                run_id=str(r.id),
                status=r.status,
                progress=r.progress,
                current_step=r.current_step,
                model_used=r.model_used,
                pdf_filename=str(meta["pdf_filename"]) if meta.get("pdf_filename") else None,
                workbook_filename=str(meta["workbook_filename"]) if meta.get("workbook_filename") else None,
                generated_file=str(meta["generated_file"]) if meta.get("generated_file") else None,
                total_requirements=decisions_len,
                started_at=r.started_at,
                completed_at=r.completed_at,
                error_message=r.error_message,
            )
        )
    return output
