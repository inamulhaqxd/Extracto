from ai_rfp_excel.app.ai.base import LLMInterface
from ai_rfp_excel.app.ai.provider import LocalLLMProvider
from ai_rfp_excel.app.config import settings
from ai_rfp_excel.app.logging import get_logger
from ai_rfp_excel.app.matching.layers.exact import ExactMatchLayer
from ai_rfp_excel.app.matching.layers.llm_layer import LLMReasoningLayer
from ai_rfp_excel.app.matching.layers.rules import RuleBasedLayer
from ai_rfp_excel.app.matching.layers.semantic import SemanticMatchLayer
from ai_rfp_excel.app.matching.layers.unit_matching import UnitConversionLayer
from ai_rfp_excel.app.matching.layers.units import parse_numeric_with_unit
from ai_rfp_excel.app.matching.models import (
    ComplianceDecision,
    ComplianceState,
    EvidenceItem,
    FactItem,
    LayerResult,
)

logger = get_logger("matching.engine")


class ComplianceEngine:
    """Layered Compliance Engine resolving requirements against reference data."""

    def __init__(
        self,
        llm_provider: LLMInterface | None = None,
        high_confidence_threshold: float | None = None,
    ) -> None:
        self.llm_provider = llm_provider or LocalLLMProvider()
        self.high_confidence_threshold = (
            high_confidence_threshold
            if high_confidence_threshold is not None
            else settings.CONFIDENCE_HIGH_THRESHOLD
        )

        self.layer1_exact = ExactMatchLayer()
        self.layer2_rules = RuleBasedLayer()
        self.layer3_units = UnitConversionLayer()
        self.layer4_semantic = SemanticMatchLayer()
        self.layer5_llm = LLMReasoningLayer(self.llm_provider)

    def _detect_conflicts(
        self,
        requirement_text: str,
        facts: list[FactItem],
    ) -> tuple[bool, list[EvidenceItem]]:
        req_lower = requirement_text.lower().strip()

        # If requirement asks for a specific scoped metric, evaluate directly rather than flagging ambiguity
        scope_qualifiers = ("typical", "max", "maximum", "peak", "idle", "standby", "nominal", "minimum", "min")
        if any(sq in req_lower for sq in scope_qualifiers):
            return False, []

        relevant_facts = [
            f for f in facts
            if f.field_name and (
                f.field_name.lower() in req_lower
                or req_lower in f.field_name.lower()
                or any(w in req_lower for w in f.field_name.lower().split() if len(w) >= 3)
            )
            and not any(sq in f.field_name.lower() or (f.value and sq in f.value.lower()) for sq in scope_qualifiers)
        ]
        if len(relevant_facts) < 2:
            return False, []

        numeric_facts = []
        for f in relevant_facts:
            parsed = parse_numeric_with_unit(f.value)
            if parsed:
                _, unit, base_val = parsed
                numeric_facts.append((base_val, unit, f))

        if len(numeric_facts) >= 2:
            base_values = {nf[0] for nf in numeric_facts}
            if len(base_values) > 1:
                # Conflicting values found for the same field
                evidence_list = []
                for _, _, fact in numeric_facts:
                    citation = f"Page {fact.source_page}" if fact.source_page else "Document citation"
                    if fact.source_table_id:
                        citation += f", Table {fact.source_table_id}"
                    evidence_list.append(
                        EvidenceItem(
                            source_document_id=fact.source_document_id,
                            source_page=fact.source_page,
                            source_table_id=fact.source_table_id,
                            source_image_id=fact.source_image_id,
                            source_type=fact.source_type,
                            value=fact.value,
                            confidence=0.5,
                            extraction_method="conflict_detection",
                            citation=citation,
                            reasoning=f"Conflicting value '{fact.value}' found in {citation}.",
                        )
                    )
                return True, evidence_list

        return False, []


    async def evaluate_requirement(
        self,
        requirement_text: str,
        facts: list[FactItem],
        vendor_name: str | None = None,
        model_name: str | None = None,
        requirement_id: str | None = None,
    ) -> ComplianceDecision:
        """Evaluate an RFP requirement through the 5-layer resolution pipeline."""
        req_clean = requirement_text.strip()
        if not req_clean or not facts:
            # Hallucination prevention: No facts available -> NOT_FOUND
            return ComplianceDecision(
                requirement_id=requirement_id,
                requirement_text=requirement_text,
                vendor_name=vendor_name,
                state=ComplianceState.NOT_FOUND,
                confidence=1.0,
                reasoning="No technical specifications or facts found in reference document to evaluate this requirement.",
                resolving_layer="none",
                evidence=[],
                conflicting_evidence=[],
            )

        # 1. Check for conflicting evidence across facts
        has_conflict, conflict_evidence = self._detect_conflicts(req_clean, facts)

        if has_conflict:
            return ComplianceDecision(
                requirement_id=requirement_id,
                requirement_text=requirement_text,
                vendor_name=vendor_name,
                state=ComplianceState.AMBIGUOUS,
                confidence=0.50,
                reasoning="Multiple conflicting specification values found in source document. Preserving all sources for human review.",
                resolving_layer="conflict_resolver",
                evidence=conflict_evidence,
                conflicting_evidence=conflict_evidence,
            )

        # Layer 1: Exact Matching
        res1: LayerResult | None = self.layer1_exact.evaluate(req_clean, facts, vendor_name)
        if res1 and res1.confidence >= self.high_confidence_threshold:
            logger.info("Requirement resolved at Layer 1 (Exact Match)", req=req_clean)
            return self._build_decision(requirement_id, req_clean, vendor_name, res1)

        # Layer 2: Rule-Based / Arithmetic Matching
        res2: LayerResult | None = self.layer2_rules.evaluate(req_clean, facts, vendor_name)
        if res2 and res2.confidence >= self.high_confidence_threshold:
            logger.info("Requirement resolved at Layer 2 (Rule-based)", req=req_clean)
            return self._build_decision(requirement_id, req_clean, vendor_name, res2)

        # Layer 3: Unit Conversion & Normalization
        res3: LayerResult | None = self.layer3_units.evaluate(req_clean, facts, vendor_name)
        if res3 and res3.confidence >= self.high_confidence_threshold:
            logger.info("Requirement resolved at Layer 3 (Unit Conversion)", req=req_clean)
            return self._build_decision(requirement_id, req_clean, vendor_name, res3)

        # Layer 4: Semantic Keyword Matching
        res4: LayerResult | None = self.layer4_semantic.evaluate(req_clean, facts, vendor_name)
        if res4 and res4.confidence >= self.high_confidence_threshold:
            logger.info("Requirement resolved at Layer 4 (Semantic Match)", req=req_clean)
            return self._build_decision(requirement_id, req_clean, vendor_name, res4)

        # Layer 5: LLM Reasoning (Complex / Ambiguous)
        logger.info("Invoking Layer 5 (LLM Reasoning)", req=req_clean)
        res5: LayerResult | None = await self.layer5_llm.evaluate(
            requirement_text=req_clean,
            facts=facts,
            vendor_name=vendor_name,
            model_name=model_name,
        )
        if res5:
            return self._build_decision(requirement_id, req_clean, vendor_name, res5)

        # Fallback to Layer 4 if available
        if res4:
            return self._build_decision(requirement_id, req_clean, vendor_name, res4)

        # If all layers fail to find relevant data: NOT_FOUND
        return ComplianceDecision(
            requirement_id=requirement_id,
            requirement_text=requirement_text,
            vendor_name=vendor_name,
            state=ComplianceState.NOT_FOUND,
            confidence=0.90,
            reasoning="Specification not found in reference data.",
            resolving_layer="none",
            evidence=[],
            conflicting_evidence=[],
        )

    def _build_decision(
        self,
        requirement_id: str | None,
        requirement_text: str,
        vendor_name: str | None,
        res: LayerResult,
    ) -> ComplianceDecision:
        return ComplianceDecision(
            requirement_id=requirement_id,
            requirement_text=requirement_text,
            vendor_name=vendor_name,
            state=res.state,
            confidence=res.confidence,
            reasoning=res.reasoning,
            matched_value=res.matched_value,
            resolving_layer=res.layer_name,
            evidence=res.evidence,
            conflicting_evidence=[],
        )
