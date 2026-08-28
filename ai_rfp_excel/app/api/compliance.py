import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ai_rfp_excel.app.api.deps import get_current_user
from ai_rfp_excel.app.database.connection import get_db
from ai_rfp_excel.app.database.models import DocumentPage, ExtractedFact, User
from ai_rfp_excel.app.matching.engine import ComplianceEngine
from ai_rfp_excel.app.matching.models import (
    ComplianceDecision,
    FactItem,
)

router = APIRouter(prefix="/compliance", tags=["compliance"])
compliance_engine = ComplianceEngine()


class ComplianceEvaluationRequest(BaseModel):
    model_config = {"protected_namespaces": ()}
    requirement_text: str
    requirement_id: str | None = None
    vendor_name: str | None = None
    document_id: str | None = None
    facts: list[FactItem] | None = None
    model_name: str | None = None



@router.post("/evaluate", response_model=ComplianceDecision)
async def evaluate_requirement(
    request: ComplianceEvaluationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ComplianceDecision:
    """Evaluate compliance of an RFP requirement using layered resolution."""
    if not request.requirement_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="requirement_text cannot be empty",
        )

    facts_to_use: list[FactItem] = list(request.facts or [])

    # If document_id is provided, retrieve facts and text pages from database
    if request.document_id:
        try:
            doc_uuid = uuid.UUID(request.document_id)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid document_id UUID: {request.document_id}",
            ) from e

        # Query extracted_facts
        facts_res = await db.execute(
            ExtractedFact.__table__.select().where(ExtractedFact.document_id == doc_uuid)
        )
        db_facts = facts_res.fetchall()
        for f in db_facts:
            facts_to_use.append(
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

        # Also query pages text if no structured facts found
        if not facts_to_use:
            pages_res = await db.execute(
                DocumentPage.__table__.select().where(DocumentPage.document_id == doc_uuid)
            )
            db_pages = pages_res.fetchall()
            for p in db_pages:
                text_content = p.native_text or p.ocr_text
                if text_content:
                    facts_to_use.append(
                        FactItem(
                            field_name="Document Page Text",
                            value=text_content,
                            source_document_id=str(p.document_id),
                            source_page=p.page_number,
                            source_type=p.content_type,
                            confidence=0.9,
                        )
                    )

    decision = await compliance_engine.evaluate_requirement(
        requirement_text=request.requirement_text,
        facts=facts_to_use,
        vendor_name=request.vendor_name,
        model_name=request.model_name,
        requirement_id=request.requirement_id,
    )

    return decision
