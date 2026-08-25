from typing import Optional

from app.ai.llm_interface import LLMInterface
from app.matching.rules import (
    ComplianceDecision,
    ComplianceStatus,
    ExactMatcher,
    RuleMatcher,
    UnitConversionMatcher,
)
from app.matching.semantic import SemanticMatcher
from app.document.processing_context import ProcessingContext
from app.logging_config import get_logger

logger = get_logger()


class ComplianceEngine:
    def __init__(self, llm: LLMInterface, model: str = "qwen3:4b"):
        self.llm = llm
        self.model = model
        self.exact_matcher = ExactMatcher()
        self.rule_matcher = RuleMatcher()
        self.unit_matcher = UnitConversionMatcher()
        self.semantic_matcher = SemanticMatcher(llm, model)

    async def resolve(
        self,
        requirement: str,
        reference_data: list[dict],
        context: Optional[ProcessingContext] = None,
    ) -> ComplianceDecision:
        logger.info("resolving_compliance", requirement=requirement[:100])

        decision = self.exact_matcher.match(requirement, str(reference_data))
        if decision and decision.confidence >= 0.9:
            return decision

        decision = self.rule_matcher.match(requirement, str(reference_data))
        if decision and decision.confidence >= 0.9:
            return decision

        decision = self.unit_matcher.match(requirement, str(reference_data))
        if decision and decision.confidence >= 0.9:
            return decision

        decision = await self.semantic_matcher.match(requirement, reference_data)
        if decision and decision.confidence >= 0.9:
            return decision

        if decision:
            return decision

        return ComplianceDecision(
            status=ComplianceStatus.NOT_FOUND,
            confidence=0.0,
            reasoning="No matching layer could resolve this requirement",
            layer="none",
        )

    async def batch_resolve(
        self,
        requirements: list[dict],
        reference_data: list[dict],
        context: Optional[ProcessingContext] = None,
    ) -> list[ComplianceDecision]:
        results = []

        for req in requirements:
            req_text = req.get("requirement_text", "")
            decision = await self.resolve(req_text, reference_data, context)
            results.append(decision)

        return results
