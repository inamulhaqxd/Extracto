import os
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db
from app.database.models import Document, Workbook, ProcessingRun, User
from app.api.auth_routes import get_current_user

router = APIRouter(tags=["processing"])


@router.post("/process")
async def start_processing(
    pdf: UploadFile = File(...),
    excel: UploadFile = File(...),
    model: str = Form("llama3.2:3b"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not pdf.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "File must be a PDF")
    if not excel.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(400, "File must be an Excel file")

    os.makedirs("./data/uploads", exist_ok=True)
    os.makedirs("./data/generated", exist_ok=True)

    pdf_path = f"./data/uploads/{uuid.uuid4()}_{pdf.filename}"
    excel_path = f"./data/uploads/{uuid.uuid4()}_{excel.filename}"

    with open(pdf_path, "wb") as f:
        f.write(await pdf.read())
    with open(excel_path, "wb") as f:
        f.write(await excel.read())

    doc = Document(
        id=uuid.uuid4(),
        user_id=current_user.id,
        filename=pdf.filename,
        file_hash="",
        file_size=os.path.getsize(pdf_path),
        file_path=pdf_path,
        status="uploaded",
    )
    db.add(doc)

    wb = Workbook(
        id=uuid.uuid4(),
        user_id=current_user.id,
        filename=excel.filename,
        file_hash="",
        file_size=os.path.getsize(excel_path),
        file_path=excel_path,
        status="uploaded",
    )
    db.add(wb)

    run = ProcessingRun(
        id=uuid.uuid4(),
        user_id=current_user.id,
        document_id=doc.id,
        workbook_id=wb.id,
        model_used=model,
        status="PROCESSING",
        started_at=datetime.utcnow(),
    )
    db.add(run)
    await db.flush()

    output_path = f"./data/generated/{run.id}.xlsx"

    import asyncio
    asyncio.create_task(_run_pipeline(str(run.id), pdf_path, excel_path, output_path, model))

    return {"run_id": str(run.id), "status": "processing", "message": "Processing started"}


async def _run_pipeline(run_id: str, pdf_path: str, excel_path: str, output_path: str, model: str):
    from app.database.connection import async_session_factory
    from app.ingestion.pdf.router import PDFRouter
    from app.excel.analyzer import ExcelAnalyzer
    from app.excel.writer import ExcelWriter
    from app.ai.ollama_client import OllamaClient
    from app.matching.compliance import ComplianceEngine

    async with async_session_factory() as db:
        try:
            result = await db.execute(select(ProcessingRun).where(ProcessingRun.id == run_id))
            run = result.scalar_one_or_none()
            if not run:
                return

            run.current_step = "Extracting PDF"
            run.progress = 0.1
            await db.commit()

            pdf_router = PDFRouter()
            pdf_pages = pdf_router.parse_all_pages(pdf_path)

            run.current_step = "Analyzing Excel"
            run.progress = 0.3
            await db.commit()

            analyzer = ExcelAnalyzer()
            excel_analysis = analyzer.analyze(excel_path)
            analyzer.close()

            run.current_step = "AI Compliance Analysis"
            run.progress = 0.5
            await db.commit()

            llm = OllamaClient()
            compliance_engine = ComplianceEngine(llm, model)

            requirements = excel_analysis.get("requirements", [])
            pdf_text = ""
            for page in pdf_pages:
                pdf_text += (page.text or "") + "\n"

            compliance_results = []
            for req in requirements:
                text = req.get("requirement_text", "")
                if not text:
                    continue
                try:
                    decision = await compliance_engine.resolve(text, [pdf_text])
                    compliance_results.append({
                        "requirement": text,
                        "sheet_name": req.get("sheet_name"),
                        "cell_reference": req.get("source_cell"),
                        "status": decision.status.value if hasattr(decision.status, "value") else str(decision.status),
                        "confidence": decision.confidence,
                        "ai_decision": decision.status.value if hasattr(decision.status, "value") else str(decision.status),
                        "evidence": getattr(decision, "reasoning", ""),
                    })
                except Exception as e:
                    compliance_results.append({
                        "requirement": text,
                        "sheet_name": req.get("sheet_name"),
                        "cell_reference": req.get("source_cell"),
                        "status": "NOT_FOUND",
                        "confidence": 0.0,
                        "ai_decision": "NOT_FOUND",
                        "evidence": str(e),
                    })

            run.current_step = "Generating Excel"
            run.progress = 0.8
            await db.commit()

            writer = ExcelWriter()
            output_dir = os.path.dirname(output_path)
            actual_output = writer.populate(excel_path, compliance_results, output_dir)

            run.status = "COMPLETED"
            run.progress = 1.0
            run.current_step = "Done"
            run.completed_at = datetime.utcnow()
            run.processing_context = {"output_path": actual_output, "result_count": len(compliance_results)}
            await db.commit()

        except Exception as e:
            run.status = "FAILED"
            run.error_message = str(e)
            await db.commit()


@router.get("/process/{run_id}/status")
async def get_processing_status(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ProcessingRun).where(ProcessingRun.id == run_id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(404, "Run not found")

    return {
        "run_id": str(run.id),
        "status": run.status,
        "progress": run.progress,
        "current_step": run.current_step,
        "error_message": run.error_message,
    }


@router.get("/process/{run_id}/download")
async def download_result(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ProcessingRun).where(ProcessingRun.id == run_id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(404, "Run not found")

    ctx = run.processing_context or {}
    output_path = ctx.get("output_path", f"./data/generated/{run_id}.xlsx")

    if not os.path.exists(output_path):
        raise HTTPException(404, "Output file not ready")

    return FileResponse(
        output_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"compliance_result_{run_id[:8]}.xlsx",
    )
