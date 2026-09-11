import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import TypedDict

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
    slot_overrides: dict[str, str] | None = None


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
    slot_assignments: dict[str, dict[str, object]] = Field(default_factory=dict)


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


class FingerprintGroupData(TypedDict):
    label: str
    total: int
    matches: int


class FingerprintGroup(BaseModel):
    model_config = {"protected_namespaces": ()}
    fingerprint: str
    label: str
    sample_count: int
    accuracy: float


class QualityMetricsResponse(BaseModel):
    model_config = {"protected_namespaces": ()}
    total_runs: int
    reviewed_runs: int
    total_reviewed_examples: int
    exact_correction_accuracy: float
    low_confidence_failures: int
    active_dataset_version: str
    layer_breakdown: dict[str, int]
    fingerprint_groups: list[FingerprintGroup]


class CreateSnapshotResponse(BaseModel):
    model_config = {"protected_namespaces": ()}
    snapshot_id: str
    file_path: str
    item_count: int
    created_at: str


class RunInspectionItem(BaseModel):
    model_config = {"protected_namespaces": ()}
    requirement_id: str
    requirement_text: str
    predicted_status: str
    predicted_value: str
    confidence: float
    reasoning: str
    citation: str
    corrected_status: str
    corrected_value: str
    review_notes: str | None = None
    is_exact_match: bool


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


@router.get("/quality/metrics", response_model=QualityMetricsResponse)
async def get_quality_metrics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QualityMetricsResponse:
    """Calculate user-scoped extraction quality KPIs and dynamic document fingerprint groups."""
    stmt = select(ProcessingRun).order_by(desc(ProcessingRun.created_at))
    res = await db.execute(stmt)
    runs = res.scalars().all()

    total_runs = len(runs)
    reviewed_runs_count = 0
    total_reviewed_examples = 0
    exact_match_count = 0
    low_confidence_failures = 0
    layer_breakdown: dict[str, int] = {"deterministic_rules": 0, "verified_llm": 0, "fallback": 0}
    fingerprint_map: dict[str, FingerprintGroupData] = {}

    for r in runs:
        meta = r.metadata_json or {}
        decisions = meta.get("decisions")
        if not isinstance(decisions, list):
            continue

        pdf_name = str(meta.get("pdf_filename") or "document")
        wb_name = str(meta.get("workbook_filename") or "workbook")
        doc_fingerprint = f"{Path(pdf_name).stem}:{Path(wb_name).stem}"

        has_reviews = False
        for d in decisions:
            if not isinstance(d, dict):
                continue

            conf = float(str(d.get("confidence") or 1.0))
            if conf < 0.70 or d.get("needs_review"):
                low_confidence_failures += 1

            layer = str(d.get("resolving_layer") or "verified_llm").lower()
            if "rule" in layer or "math" in layer:
                layer_breakdown["deterministic_rules"] += 1
            elif "fallback" in layer:
                layer_breakdown["fallback"] += 1
            else:
                layer_breakdown["verified_llm"] += 1

            pred_status = str(d.get("compliance_state") or d.get("status") or "").upper()
            pred_val = str(d.get("extracted_value") or d.get("matched_value") or "").strip().lower()

            if r.status == "completed":
                total_reviewed_examples += 1
                has_reviews = True

                if "COMPLIANT" in pred_status and pred_val and pred_val != "not_specified":
                    exact_match_count += 1
                elif pred_status == "NOT_FOUND" and pred_val in ("", "not_specified"):
                    exact_match_count += 1

                if doc_fingerprint not in fingerprint_map:
                    fingerprint_map[doc_fingerprint] = {
                        "label": f"{Path(pdf_name).stem[:24]} ({Path(wb_name).stem[:16]})",
                        "total": 0,
                        "matches": 0,
                    }
                fg = fingerprint_map[doc_fingerprint]
                fg["total"] += 1
                if "COMPLIANT" in pred_status and pred_val != "not_specified":
                    fg["matches"] += 1

        if has_reviews:
            reviewed_runs_count += 1

    accuracy = round((exact_match_count / max(total_reviewed_examples, 1)), 4) if total_reviewed_examples > 0 else 0.0

    fingerprint_groups: list[FingerprintGroup] = []
    for fp, data in fingerprint_map.items():
        cnt = data["total"]
        if cnt >= 2:
            m = data["matches"]
            fingerprint_groups.append(
                FingerprintGroup(
                    fingerprint=fp,
                    label=data["label"],
                    sample_count=cnt,
                    accuracy=round(m / max(cnt, 1), 2),
                )
            )

    datasets_dir = Path(settings.GENERATED_DIR) / "datasets"
    active_version = "v1.0-default"
    if datasets_dir.exists():
        snapshots = sorted(datasets_dir.glob("snapshot_*.jsonl"), reverse=True)
        if snapshots:
            active_version = snapshots[0].stem

    return QualityMetricsResponse(
        total_runs=total_runs,
        reviewed_runs=reviewed_runs_count,
        total_reviewed_examples=total_reviewed_examples,
        exact_correction_accuracy=accuracy,
        low_confidence_failures=low_confidence_failures,
        active_dataset_version=active_version,
        layer_breakdown=layer_breakdown,
        fingerprint_groups=fingerprint_groups,
    )


@router.post("/quality/snapshots", response_model=CreateSnapshotResponse)
async def create_dataset_snapshot(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CreateSnapshotResponse:
    """Create a versioned local JSONL dataset snapshot from reviewed runs for offline training/eval."""
    stmt = select(ProcessingRun).order_by(desc(ProcessingRun.created_at))
    res = await db.execute(stmt)
    runs = res.scalars().all()

    datasets_dir = Path(settings.GENERATED_DIR) / "datasets"
    datasets_dir.mkdir(parents=True, exist_ok=True)

    snapshot_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot_id = f"snapshot_{snapshot_ts}"
    snapshot_path = datasets_dir / f"{snapshot_id}.jsonl"

    records: list[dict[str, object]] = []
    for r in runs:
        meta = r.metadata_json or {}
        decisions = meta.get("decisions")
        if not isinstance(decisions, list):
            continue
        pdf_name = str(meta.get("pdf_filename") or "")
        wb_name = str(meta.get("workbook_filename") or "")

        for d in decisions:
            if not isinstance(d, dict):
                continue
            records.append({
                "run_id": str(r.id),
                "model_used": r.model_used,
                "document": pdf_name,
                "workbook": wb_name,
                "requirement_id": d.get("requirement_id"),
                "requirement_text": d.get("requirement_text"),
                "predicted_status": d.get("compliance_state") or d.get("status"),
                "predicted_value": d.get("extracted_value") or d.get("matched_value"),
                "confidence": d.get("confidence"),
                "citation": d.get("citation"),
                "remarks": d.get("remarks") or d.get("reasoning"),
                "review_notes": d.get("review_notes"),
                "slot_assignments": d.get("slot_assignments"),
                "timestamp": datetime.now().isoformat(),
            })

    with open(snapshot_path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    return CreateSnapshotResponse(
        snapshot_id=snapshot_id,
        file_path=str(snapshot_path),
        item_count=len(records),
        created_at=datetime.now().isoformat(),
    )


@router.get("/{run_id}/inspections", response_model=list[RunInspectionItem])
async def get_run_inspections(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[RunInspectionItem]:
    """Retrieve detailed item-by-item comparison between model prediction and human review."""
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
    decisions: list[object] = decisions_raw if isinstance(decisions_raw, list) else []
    items: list[RunInspectionItem] = []

    for d in decisions:
        if not isinstance(d, dict):
            continue

        req_id = str(d.get("requirement_id") or "")
        req_text = str(d.get("requirement_text") or "")
        pred_status = str(d.get("compliance_state") or d.get("status") or "NOT_FOUND")
        pred_val = str(d.get("extracted_value") or d.get("matched_value") or "")
        conf = float(str(d.get("confidence") or 1.0))
        reasoning = str(d.get("reasoning") or d.get("remarks") or "")
        citation = str(d.get("citation") or "None")

        slots = d.get("slot_assignments") or {}
        corr_val = pred_val
        corr_status = pred_status
        review_notes = str(d.get("review_notes") or "")

        if isinstance(slots, dict):
            for s_dict in slots.values():
                if isinstance(s_dict, dict):
                    st = str(s_dict.get("slot_type", "")).lower()
                    if "compliance" in st and s_dict.get("value"):
                        corr_status = str(s_dict.get("value"))
                    elif ("answer" in st or "value" in st) and s_dict.get("value"):
                        corr_val = str(s_dict.get("value"))

        is_match = (
            pred_status.strip().upper() == corr_status.strip().upper()
            and pred_val.strip().lower() == corr_val.strip().lower()
        )

        items.append(
            RunInspectionItem(
                requirement_id=req_id,
                requirement_text=req_text,
                predicted_status=pred_status,
                predicted_value=pred_val,
                confidence=conf,
                reasoning=reasoning,
                citation=citation,
                corrected_status=corr_status,
                corrected_value=corr_val,
                review_notes=review_notes if review_notes else None,
                is_exact_match=is_match,
            )
        )

    return items


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

        raw_slots = d.get("slot_assignments")
        clean_slots: dict[str, dict[str, object]] = {}
        if isinstance(raw_slots, dict):
            for sk, sv in raw_slots.items():
                if isinstance(sv, dict):
                    clean_slots[str(sk)] = {str(k): v for k, v in sv.items()}

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
                slot_assignments=clean_slots,
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
    if not isinstance(decisions_raw, list) or len(decisions_raw) == 0:
        decisions_json_path = Path(settings.GENERATED_DIR) / str(run_id) / "compliance_decisions.json"
        if decisions_json_path.exists():
            try:
                with open(decisions_json_path, "r", encoding="utf-8") as f:
                    disk_data = json.load(f)
                    decisions_raw = disk_data.get("items") or disk_data.get("decisions") or []
            except Exception:
                pass

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
                status_upper = rev.status.upper()
                item["status"] = status_upper
                item["compliance_state"] = "COMPLIANT" if status_upper in ("COMPLIANT", "OVERRIDDEN") else status_upper

                if rev.matched_value is not None:
                    item["extracted_value"] = rev.matched_value
                    item["matched_value"] = rev.matched_value
                if rev.confidence is not None:
                    item["confidence"] = rev.confidence
                else:
                    item["confidence"] = 1.0

                if rev.review_notes:
                    item["review_notes"] = rev.review_notes
                    reason_base = str(item.get("reasoning") or item.get("remarks") or "")
                    item["reasoning"] = f"{reason_base} [Reviewer Note: {rev.review_notes}]"
                item["needs_review"] = False

                # Propagate override to slot_assignments for Step 5 Excel population
                slots_raw = item.get("slot_assignments")
                if isinstance(slots_raw, dict):
                    updated_slots: dict[str, dict[str, object]] = {}
                    for k, v in slots_raw.items():
                        if isinstance(v, dict):
                            updated_slots[k] = {str(sk): sv for sk, sv in v.items()}

                    # 1. Apply slot-level overrides if specified by user
                    if rev.slot_overrides:
                        for s_key, s_val in rev.slot_overrides.items():
                            if s_key in updated_slots:
                                updated_slots[s_key]["value"] = s_val
                                updated_slots[s_key]["needs_review"] = False
                            else:
                                for uk, uv in updated_slots.items():
                                    if uk.lower() == s_key.lower() or str(uv.get("slot_type", "")).lower() == s_key.lower():
                                        uv["value"] = s_val
                                        uv["needs_review"] = False
                                        break

                    # 2. Update primary answer/value slot if matched_value is provided
                    if rev.matched_value is not None:
                        # Find primary answer/value slot
                        target_key: str | None = None
                        if "answer" in updated_slots:
                            target_key = "answer"
                        else:
                            for sk, s_dict in updated_slots.items():
                                st = str(s_dict.get("slot_type", "")).lower()
                                if st in ("answer", "value", "specification", "offered", "response"):
                                    target_key = sk
                                    break
                        if target_key is None:
                            for sk, s_dict in updated_slots.items():
                                st = str(s_dict.get("slot_type", sk)).lower()
                                if not any(ign in st for ign in ("remark", "note", "comment", "citation", "reference", "status", "compliance")):
                                    target_key = sk
                                    break
                        if target_key is None and len(updated_slots) > 0:
                            target_key = next(iter(updated_slots.keys()))

                        if target_key and target_key in updated_slots:
                            if not rev.slot_overrides or target_key not in rev.slot_overrides:
                                updated_slots[target_key]["value"] = rev.matched_value
                                updated_slots[target_key]["needs_review"] = False

                    if rev.review_notes:
                        for s_dict in updated_slots.values():
                            st = str(s_dict.get("slot_type", "")).lower()
                            if any(rk in st for rk in ("remark", "note", "comment")):
                                prev_rem = str(s_dict.get("value") or "")
                                s_dict["value"] = f"{prev_rem} [Review: {rev.review_notes}]" if prev_rem and prev_rem != "None" else rev.review_notes
                                s_dict["needs_review"] = False

                    # Mark all slots for this reviewed item as not needing review
                    for s_dict in updated_slots.values():
                        s_dict["needs_review"] = False

                    item["slot_assignments"] = updated_slots

            updated_decisions.append(item)

    # Re-populate workbook with updated decisions
    if run.workbook_id:
        wb_res = await db.execute(select(Workbook).where(Workbook.id == run.workbook_id))
        wb_rec = wb_res.scalar_one_or_none()
        if not wb_rec and meta.get("workbook_filename"):
            wb_res = await db.execute(select(Workbook).where(Workbook.filename == str(meta.get("workbook_filename"))))
            wb_rec = wb_res.scalar_one_or_none()

        if wb_rec:
            wb_path = Path(settings.UPLOAD_DIR) / wb_rec.filename
            if not wb_path.exists():
                wb_path = Path(settings.UPLOAD_DIR) / f"{run.workbook_id}.xlsx"

            if wb_path.exists():
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
    run.metadata_json = dict(meta)
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(run, "metadata_json")
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
