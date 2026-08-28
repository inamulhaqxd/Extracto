from ai_rfp_excel.app.ai.base import LLMInterface
from ai_rfp_excel.app.ai.models import (
    ChatMessage,
    ComplianceAnalysisResult,
    ComplianceStatus,
    Role,
)
from ai_rfp_excel.app.ai.prompts.compliance_matching import (
    build_compliance_matching_prompt,
)
from ai_rfp_excel.app.matching.models import (
    ComplianceState,
    EvidenceItem,
    FactItem,
    LayerResult,
)


class LLMReasoningLayer:
    """Layer 5: LLM reasoning for complex, multi-clause, or ambiguous compliance evaluation."""

    name = "llm_reasoning"

    def __init__(self, llm_provider: LLMInterface) -> None:
        self.llm_provider = llm_provider

    async def evaluate(
        self,
        requirement_text: str,
        facts: list[FactItem],
        vendor_name: str | None = None,
        model_name: str | None = None,
    ) -> LayerResult | None:
        if not facts:
            return None

        # Filter facts for vendor if specified
        candidate_facts = facts
        if vendor_name:
            v_lower = vendor_name.lower()
            filtered = [
                f
                for f in facts
                if (f.field_name and v_lower in f.field_name.lower())
                or (f.metadata_json and f.metadata_json.get("vendor", "").lower() == v_lower)
            ]
            if filtered:
                candidate_facts = filtered

        fact_strings = [
            f"[{f.field_name or 'Spec'} (Page {f.source_page or 'N/A'})] {f.value}"
            for f in candidate_facts[:15]  # limit context to top 15 facts
        ]

        prompt = build_compliance_matching_prompt(
            requirement_text=requirement_text,
            extracted_facts=fact_strings,
            vendor_name=vendor_name,
        )

        try:
            res: ComplianceAnalysisResult = await self.llm_provider.chat(
                messages=[ChatMessage(role=Role.USER, content=prompt)],
                response_model=ComplianceAnalysisResult,
                model=model_name,
            )

            # Map ComplianceStatus to ComplianceState
            state_map = {
                ComplianceStatus.COMPLIANT: ComplianceState.COMPLIANT,
                ComplianceStatus.NON_COMPLIANT: ComplianceState.NON_COMPLIANT,
                ComplianceStatus.PARTIAL: ComplianceState.PARTIALLY_COMPLIANT,
                ComplianceStatus.AMBIGUOUS: ComplianceState.AMBIGUOUS,
            }
            state = state_map.get(res.status, ComplianceState.COMPLIANT)

            # Create evidence citation
            evidence_items: list[EvidenceItem] = []
            if candidate_facts:
                primary_fact = candidate_facts[0]
                citation_ref = f"Page {primary_fact.source_page}" if primary_fact.source_page else "Document reference"
                if primary_fact.source_table_id:
                    citation_ref += f", Table {primary_fact.source_table_id}"

                evidence_items.append(
                    EvidenceItem(
                        source_document_id=primary_fact.source_document_id,
                        source_page=primary_fact.source_page,
                        source_table_id=primary_fact.source_table_id,
                        source_image_id=primary_fact.source_image_id,
                        source_type=primary_fact.source_type,
                        value=res.evidence_text or res.matched_value or primary_fact.value,
                        confidence=res.confidence,
                        extraction_method=self.name,
                        citation=citation_ref,
                        reasoning=res.reasoning,
                    )
                )

            return LayerResult(
                layer_name=self.name,
                state=state,
                confidence=res.confidence,
                reasoning=res.reasoning,
                matched_value=res.matched_value,
                evidence=evidence_items,
            )
        except Exception:
            return None
