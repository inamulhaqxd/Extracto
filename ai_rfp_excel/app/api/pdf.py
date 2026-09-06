import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ai_rfp_excel.app.api.deps import get_current_user
from ai_rfp_excel.app.config import settings
from ai_rfp_excel.app.database.connection import get_db
from ai_rfp_excel.app.database.models import Document, User
from ai_rfp_excel.app.ingestion.pdf.processor import process_pdf, retry_failed_pages
from ai_rfp_excel.app.ingestion.pdf.utils import get_file_info

router = APIRouter(prefix="/pdf", tags=["pdf"])


class PDFUploadResponse(BaseModel):
    document_id: str
    filename: str
    file_hash: str
    total_pages: int
    status: str
    is_duplicate: bool = False
    duplicate_document_id: str | None = None
    warning: str | None = None


class PDFProcessResponse(BaseModel):
    document_id: str
    status: str
    total_pages: int
    processed_pages: int
    failed_pages: list[int]
    errors: list[str]


@router.post("/upload", response_model=PDFUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_pdf(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PDFUploadResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are allowed",
        )

    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_id = str(uuid.uuid4())
    file_path = upload_dir / f"{file_id}.pdf"

    content = await file.read()
    if len(content) > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum size of {settings.MAX_FILE_SIZE_MB}MB",
        )

    with open(file_path, "wb") as f:
        f.write(content)

    file_info = get_file_info(str(file_path))
    file_hash = str(file_info["file_hash"])

    # Check for duplicates in DB
    result = await db.execute(Document.__table__.select().where(Document.file_hash == file_hash))
    existing_doc = result.first()
    is_dup = existing_doc is not None
    dup_id = str(existing_doc.id) if existing_doc else None
    warning = (
        f"Warning: A document with identical content was previously uploaded (Document ID: {dup_id})"
        if is_dup
        else None
    )

    total_pages = 1
    try:
        import pdfplumber

        with pdfplumber.open(str(file_path)) as pdf:
            total_pages = len(pdf.pages)
    except Exception:
        try:
            import fitz

            doc = fitz.open(str(file_path))
            total_pages = len(doc)
            doc.close()
        except Exception:
            total_pages = 1

    document = Document(
        id=uuid.UUID(file_id),
        filename=f"{file_id}.pdf",
        original_filename=file.filename,
        file_hash=file_hash,
        file_size=int(file_info["file_size"]),
        content_type="application/pdf",
        total_pages=total_pages,
    )
    db.add(document)
    await db.flush()

    return PDFUploadResponse(
        document_id=file_id,
        filename=file.filename,
        file_hash=file_hash,
        total_pages=total_pages,
        status="uploaded",
        is_duplicate=is_dup,
        duplicate_document_id=dup_id,
        warning=warning,
    )


@router.post("/{document_id}/process", response_model=PDFProcessResponse)
async def process_uploaded_pdf(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PDFProcessResponse:
    result = await db.execute(Document.__table__.select().where(Document.id == document_id))
    document_row = result.first()

    if document_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    file_path = Path(settings.UPLOAD_DIR) / f"{document_id}.pdf"
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PDF file not found on disk",
        )

    checkpoint_path = Path(settings.PROCESSED_DIR) / "checkpoints" / f"checkpoint_{document_id}.json"

    context = process_pdf(
        pdf_path=str(file_path),
        user_id=str(current_user.id),
        batch_size=10,
        checkpoint_path=checkpoint_path,
    )

    return PDFProcessResponse(
        document_id=document_id,
        status=context.status.value,
        total_pages=context.total_pages,
        processed_pages=context.processed_pages,
        failed_pages=context.failed_pages,
        errors=context.errors,
    )


@router.post("/{document_id}/retry", response_model=PDFProcessResponse)
async def retry_failed_pdf_pages(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PDFProcessResponse:
    result = await db.execute(Document.__table__.select().where(Document.id == document_id))
    document_row = result.first()

    if document_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    file_path = Path(settings.UPLOAD_DIR) / f"{document_id}.pdf"
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PDF file not found on disk",
        )

    checkpoint_path = Path(settings.PROCESSED_DIR) / "checkpoints" / f"checkpoint_{document_id}.json"

    context = process_pdf(
        pdf_path=str(file_path),
        user_id=str(current_user.id),
        batch_size=10,
        checkpoint_path=checkpoint_path,
    )

    if context.failed_pages:
        context = retry_failed_pages(
            pdf_path=str(file_path),
            context=context,
            checkpoint_path=checkpoint_path,
        )

    return PDFProcessResponse(
        document_id=document_id,
        status=context.status.value,
        total_pages=context.total_pages,
        processed_pages=context.processed_pages,
        failed_pages=context.failed_pages,
        errors=context.errors,
    )

