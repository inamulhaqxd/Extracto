import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ai_rfp_excel.app.api.deps import get_current_user
from ai_rfp_excel.app.config import settings
from ai_rfp_excel.app.database.connection import get_db
from ai_rfp_excel.app.database.models import Requirement, User, Workbook, WorkbookSheet
from ai_rfp_excel.app.excel.analyzer import ExcelAnalyzer
from ai_rfp_excel.app.excel.models import PopulationResult, WorkbookAnalysis
from ai_rfp_excel.app.excel.utils import (
    MAX_EXCEL_SIZE_MB,
    VALID_EXCEL_EXTENSIONS,
    calculate_workbook_hash,
)
from ai_rfp_excel.app.excel.writer import ExcelWriter
from ai_rfp_excel.app.matching.engine import ComplianceEngine
from ai_rfp_excel.app.matching.models import ComplianceDecision

router = APIRouter(prefix="/excel", tags=["excel"])
analyzer = ExcelAnalyzer()
writer = ExcelWriter()
compliance_engine = ComplianceEngine()


class ExcelUploadResponse(BaseModel):
    workbook_id: str
    filename: str
    file_hash: str
    file_size: int
    version: int
    status: str
    is_duplicate: bool = False
    duplicate_workbook_id: str | None = None
    warning: str | None = None


class ExcelAnalyzeResponse(BaseModel):
    workbook_id: str
    filename: str
    total_sheets: int
    total_requirements: int
    analysis: WorkbookAnalysis


class ExcelPopulateRequest(BaseModel):
    workbook_id: str
    decisions: list[ComplianceDecision] | None = None


@router.post("/upload", response_model=ExcelUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_excel(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExcelUploadResponse:
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename cannot be empty",
        )

    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in VALID_EXCEL_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid file extension '{file_ext}'. "
                f"Allowed Excel formats: {', '.join(sorted(VALID_EXCEL_EXTENSIONS))}"
            ),
        )

    content = await file.read()
    file_size_bytes = len(content)
    max_size_bytes = MAX_EXCEL_SIZE_MB * 1024 * 1024

    if file_size_bytes > max_size_bytes:
        file_size_mb = round(file_size_bytes / (1024 * 1024), 2)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"File size of {file_size_mb}MB exceeds maximum allowed limit of {MAX_EXCEL_SIZE_MB}MB. "
                "Please upload a smaller workbook."
            ),
        )

    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)

    workbook_id = str(uuid.uuid4())
    file_path = upload_dir / f"{workbook_id}{file_ext}"

    with open(file_path, "wb") as f:
        f.write(content)

    file_hash = calculate_workbook_hash(str(file_path))

    # Check for duplicate workbook hash
    result = await db.execute(Workbook.__table__.select().where(Workbook.file_hash == file_hash))
    existing_wb = result.first()
    is_dup = existing_wb is not None
    dup_id = str(existing_wb.id) if existing_wb else None
    warning = (
        f"Warning: An Excel template with identical content was previously uploaded (Workbook ID: {dup_id})"
        if is_dup
        else None
    )

    # Determine version: check if previous versions with same original filename exist
    prev_versions_res = await db.execute(
        Workbook.__table__.select().where(Workbook.original_filename == file.filename)
    )
    prev_rows = prev_versions_res.fetchall()
    version = len(prev_rows) + 1

    workbook_record = Workbook(
        id=uuid.UUID(workbook_id),
        filename=f"{workbook_id}{file_ext}",
        original_filename=file.filename,
        file_hash=file_hash,
        file_size=file_size_bytes,
        version=version,
        metadata_json={
            "uploaded_by": str(current_user.id),
            "original_filename": file.filename,
        },
    )
    db.add(workbook_record)
    await db.flush()

    return ExcelUploadResponse(
        workbook_id=workbook_id,
        filename=file.filename,
        file_hash=file_hash,
        file_size=file_size_bytes,
        version=version,
        status="uploaded",
        is_duplicate=is_dup,
        duplicate_workbook_id=dup_id,
        warning=warning,
    )


@router.post("/{workbook_id}/analyze", response_model=ExcelAnalyzeResponse)
async def analyze_uploaded_excel(
    workbook_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExcelAnalyzeResponse:
    result = await db.execute(Workbook.__table__.select().where(Workbook.id == workbook_id))
    workbook_row = result.first()

    if workbook_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workbook not found",
        )

    file_ext = Path(workbook_row.filename).suffix
    file_path = Path(settings.UPLOAD_DIR) / f"{workbook_id}{file_ext}"

    if not file_path.exists():
        # Fallback to direct filename search
        file_path = Path(settings.UPLOAD_DIR) / workbook_row.filename
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Excel file not found on disk",
            )

    try:
        analysis = analyzer.analyze_workbook(
            file_path=str(file_path),
            workbook_id=workbook_id,
            version=workbook_row.version,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to analyze Excel workbook: {e!s}",
        ) from e

    # Persist WorkbookSheet and Requirement models into database
    for sheet_data in analysis.sheets:
        sheet_id = uuid.uuid4()
        wb_sheet = WorkbookSheet(
            id=sheet_id,
            workbook_id=uuid.UUID(workbook_id),
            sheet_name=sheet_data.sheet_name,
            sheet_index=sheet_data.sheet_index,
            dimensions=sheet_data.dimensions,
            merged_cells=sheet_data.merged_cells,
            hidden_rows=sheet_data.hidden_rows,
            hidden_columns=sheet_data.hidden_columns,
            metadata_json={
                "header_row": sheet_data.header_row,
                "columns": [c.model_dump() for c in sheet_data.columns],
                "sections": [s.model_dump() for s in sheet_data.sections],
            },
        )
        db.add(wb_sheet)
        await db.flush()

        for req_data in sheet_data.requirements:
            req_record = Requirement(
                id=uuid.uuid4(),
                sheet_id=sheet_id,
                requirement_index=int(req_data.requirement_id.split("-")[-1]) if "-" in req_data.requirement_id else 1,
                requirement_text=req_data.requirement_text,
                section=req_data.section,
                subsection=req_data.subsection,
                row_number=req_data.row_number,
                source_cell=req_data.source_cell,
                source_range=req_data.source_range,
                metadata_json={
                    "vendor_cells": req_data.vendor_cells,
                    "compliance_cells": req_data.compliance_cells,
                    "remarks_cells": req_data.remarks_cells,
                    "raw_values": req_data.raw_values,
                },
            )
            db.add(req_record)

    await db.flush()

    return ExcelAnalyzeResponse(
        workbook_id=workbook_id,
        filename=workbook_row.original_filename,
        total_sheets=analysis.total_sheets,
        total_requirements=analysis.total_requirements,
        analysis=analysis,
    )


@router.get("/{workbook_id}/structure")
async def get_excel_structure(
    workbook_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    result = await db.execute(Workbook.__table__.select().where(Workbook.id == workbook_id))
    wb_row = result.first()

    if wb_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workbook not found",
        )

    sheets_res = await db.execute(
        WorkbookSheet.__table__.select().where(WorkbookSheet.workbook_id == workbook_id)
    )
    sheet_rows = sheets_res.fetchall()

    sheets_info = []
    for s in sheet_rows:
        reqs_res = await db.execute(
            Requirement.__table__.select().where(Requirement.sheet_id == s.id)
        )
        req_rows = reqs_res.fetchall()
        sheets_info.append(
            {
                "sheet_id": str(s.id),
                "sheet_name": s.sheet_name,
                "sheet_index": s.sheet_index,
                "dimensions": s.dimensions,
                "merged_cells": s.merged_cells,
                "hidden_rows": s.hidden_rows,
                "hidden_columns": s.hidden_columns,
                "requirements_count": len(req_rows),
            }
        )

    return {
        "workbook_id": workbook_id,
        "filename": wb_row.original_filename,
        "version": wb_row.version,
        "file_hash": wb_row.file_hash,
        "sheets": sheets_info,
    }


@router.post("/populate", response_model=PopulationResult)
async def populate_excel_workbook(
    request: ExcelPopulateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PopulationResult:
    """Populate workbook with compliance results, preserving format and adding summary tab."""
    result = await db.execute(Workbook.__table__.select().where(Workbook.id == request.workbook_id))
    workbook_row = result.first()

    if workbook_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workbook not found",
        )

    file_ext = Path(workbook_row.filename).suffix
    file_path = Path(settings.UPLOAD_DIR) / f"{request.workbook_id}{file_ext}"
    if not file_path.exists():
        file_path = Path(settings.UPLOAD_DIR) / workbook_row.filename
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Excel file not found on disk",
            )

    analysis = analyzer.analyze_workbook(
        file_path=str(file_path),
        workbook_id=request.workbook_id,
        version=workbook_row.version,
    )

    decisions = request.decisions or []

    try:
        pop_res = writer.populate_workbook(
            template_path=file_path,
            analysis=analysis,
            decisions=decisions,
        )
        return pop_res
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to populate Excel workbook: {e!s}",
        ) from e


@router.get("/download/{filename}")
async def download_populated_excel(
    filename: str,
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    """Download populated Excel file from output directory."""
    file_path = Path(settings.OUTPUT_DIR) / filename
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File '{filename}' not found in output directory",
        )

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

