from typing import Optional

from app.ai.llm_interface import LLMInterface
from app.ai.output_parser import StructuredOutputParser, ComplianceResult
from app.matching.rules import ComplianceDecision, ComplianceStatus, Evidence
from app.logging_config import get_logger

logger = get_logger()


class SemanticMatcher:
    def __init__(self, llm: LLMInterface, model: str = "qwen3:4b"):
        self.llm = llm
        self.model = model
        self.parser = StructuredOutputParser(llm)

    async def match(
        self,
        requirement: str,
        reference_data: list[dict],
        context: dict = None,
    ) -> Optional[ComplianceDecision]:
        reference_text = self._format_reference(reference_data)

        messages = [
            {
                "role": "system",
                "content": """You are a technical specification compliance analyzer.
Determine if the reference data meets the requirement.
Return ONLY valid JSON with this structure:
{
    "status": "COMPLIANT|PARTIALLY_COMPLIANT|NON_COMPLIANT|NOT_FOUND|AMBIGUOUS",
    "confidence": 0.95,
    "evidence": [{"text": "evidence", "page": 1, "source_type": "text"}],
    "reasoning": "brief explanation"
}"""
            },
            {
                "role": "user",
                "content": f"""Requirement: {requirement}

Reference Data:
{reference_text}

Analyze compliance and return JSON."""
            }
        ]

        result = await self.parser.parse_with_retry(
            model=self.model,
            messages=messages,
            output_model=ComplianceResult,
        )

        if result is None:
            return None

        status_map = {
            "COMPLIANT": ComplianceStatus.COMPLIANT,
            "PARTIALLY_COMPLIANT": ComplianceStatus.PARTIALLY_COMPLIANT,
            "NON_COMPLIANT": ComplianceStatus.NON_COMPLIANT,
            "NOT_FOUND": ComplianceStatus.NOT_FOUND,
            "AMBIGUOUS": ComplianceStatus.AMBIGUOUS,
        }

        status = status_map.get(result.status, ComplianceStatus.NOT_FOUND)

        evidence_list = [
            Evidence(
                value=e.get("text", ""),
                page=e.get("page"),
                source_type=e.get("source_type", "text"),
                confidence=result.confidence,
            )
            for e in result.evidence
        ]

        return ComplianceDecision(
            status=status,
            confidence=result.confidence,
            evidence=evidence_list,
            reasoning=result.reasoning,
            layer="semantic",
        )

    def _format_reference(self, reference_data: list[dict]) -> str:
        parts = []
        for item in reference_data:
            if "text" in item:
                parts.append(f"Text: {item['text']}")
            if "table" in item:
                parts.append(f"Table: {item['table']}")
            if "value" in item:
                parts.append(f"Value: {item['value']}")
        return "\n".join(parts) if parts else "No reference data available"
