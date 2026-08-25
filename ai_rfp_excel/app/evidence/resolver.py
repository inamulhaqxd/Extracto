from typing import Optional
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Evidence, ComplianceResult
from app.matching.rules import ComplianceDecision, Evidence as EvidenceData
from app.logging_config import get_logger

logger = get_logger()


class EvidenceResolver:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def save_evidence(
        self,
        compliance_result_id: str,
        decision: ComplianceDecision,
    ) -> list[Evidence]:
        evidence_records = []

        for evidence_data in decision.evidence:
            evidence = Evidence(
                id=uuid4(),
                compliance_result_id=compliance_result_id,
                value=evidence_data.value,
                page=evidence_data.page,
                table_id=evidence_data.table_id,
                image_id=evidence_data.image_id,
                source_type=evidence_data.source_type,
                confidence=evidence_data.confidence,
            )
            self.db.add(evidence)
            evidence_records.append(evidence)

        await self.db.flush()

        logger.info(
            "evidence_saved",
            compliance_result_id=compliance_result_id,
            count=len(evidence_records),
        )

        return evidence_records

    async def get_evidence(self, compliance_result_id: str) -> list[Evidence]:
        from sqlalchemy import select

        result = await self.db.execute(
            select(Evidence).where(
                Evidence.compliance_result_id == compliance_result_id
            )
        )
        return list(result.scalars().all())

    def format_evidence_for_review(self, evidence: list[Evidence]) -> list[dict]:
        formatted = []
        for e in evidence:
            source = f"Page {e.page}" if e.page else "Unknown"
            if e.table_id:
                source += f", Table {e.table_id}"
            if e.image_id:
                source += f", Image {e.image_id}"

            formatted.append({
                "value": e.value,
                "source": source,
                "source_type": e.source_type,
                "confidence": e.confidence,
            })

        return formatted
