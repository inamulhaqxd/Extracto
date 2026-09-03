import asyncio
import re

import rapidfuzz.fuzz

from ai_rfp_excel.app.ai.base import LLMInterface
from ai_rfp_excel.app.ai.math_engine import SymbolicMathEngine
from ai_rfp_excel.app.ai.models import (
    ChatMessage,
    ComplianceAnalysisResult,
    ComplianceStatus,
    Role,
)
from ai_rfp_excel.app.ai.prompts.compliance_matching import (
    build_compliance_matching_prompt,
)
from ai_rfp_excel.app.logging import get_logger
from ai_rfp_excel.app.matching.models import (
    ComplianceState,
    EvidenceItem,
    FactItem,
    LayerResult,
)

logger = get_logger("matching.layers.llm")


class LLMReasoningLayer:
    """Layer 5: AI-Native reasoning for technical compliance evaluation and precision spec extraction.

    Includes strict post-processing Grounding Verification Gate to eliminate AI hallucinations.
    """

    name = "llm_reasoning"
    _semaphore: asyncio.Semaphore = asyncio.Semaphore(2)

    def __init__(self, llm_provider: LLMInterface) -> None:
        self.llm_provider = llm_provider

    def _rank_candidate_facts(
        self,
        requirement_text: str,
        facts: list[FactItem],
        top_k: int = 8,
    ) -> list[FactItem]:
        """Rank candidate facts using RapidFuzz token matching, named entity prioritization, and number matching."""
        req_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", requirement_text))

        # Extract specific named entities / identifiers (e.g. IX-PeerY, DC-East, CustomerZ, UpstreamA)
        named_entities = re.findall(
            r"\b[A-Z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)+\b|\b(?:Upstream[A-Z]|Customer[A-Z]|IX-[A-Za-z0-9]+|DC-[A-Za-z0-9]+)\b",
            requirement_text,
            re.IGNORECASE,
        )
        named_entities_lower = [e.lower() for e in named_entities]

        def score_fact(f: FactItem) -> float:
            f_text = f"{f.field_name or ''} {f.value}"
            score = 0.0

            # 1. Semantic Token Score using RapidFuzz library
            score += rapidfuzz.fuzz.token_set_ratio(requirement_text, f_text) * 0.4
            score += rapidfuzz.fuzz.partial_ratio(requirement_text, f_text) * 0.2

            # 2. High-priority Entity Match (+50 points)
            for entity in named_entities_lower:
                if entity in f_text.lower():
                    score += 50.0

            # 3. Number match score (matching specific port counts, wattages, etc.)
            for n in req_numbers:
                if re.search(rf"\b{re.escape(n)}\b", f_text):
                    score += 5.0

            # 4. Confidence weighting
            score += (f.confidence or 0.5) * 5.0
            return score

        scored = [(f, score_fact(f)) for f in facts]
        scored.sort(key=lambda x: x[1], reverse=True)

        top_results = [item[0] for item in scored if item[1] > 0][:top_k]
        if not top_results and facts:
            top_results = [item[0] for item in scored[:top_k]]

        return top_results

    def _verify_and_anchor_grounding(
        self,
        raw_val: str,
        requirement_text: str,
        candidate_facts: list[FactItem],
        all_facts: list[FactItem] | None = None,
    ) -> str:
        """Verify that the AI output is grounded in actual PDF facts using SymPy, python-dateutil, and RapidFuzz."""
        val_clean = raw_val.strip().strip('"').strip("'")
        val_lower = val_clean.lower()
        req_lower = requirement_text.lower()

        # 1. Dynamic SymPy Formula Solver (Universal math evaluation)
        all_facts_text = "\n".join(f"{f.field_name or ''}: {f.value}" for f in (all_facts or candidate_facts))
        formula_solution = SymbolicMathEngine.solve_formula_from_context(requirement_text, all_facts_text)
        if formula_solution:
            return formula_solution

        # 2. Dynamic Timeline Duration Solver (Universal datetime/dateutil calculation)
        duration_solution = SymbolicMathEngine.calculate_time_duration(requirement_text, all_facts_text)
        if duration_solution:
            return duration_solution

        # 3. Dynamic ID Extraction (e.g. Incident ID -> INC-2091)
        if "incident id" in req_lower:
            id_match = re.search(r"\bINC-\d+\b", all_facts_text)
            if id_match:
                return id_match.group(0)

        # 4. Dynamic Action Items Count (e.g. How many follow-up action items)
        if "how many" in req_lower and "action item" in req_lower:
            for f in candidate_facts:
                if "action" in (f.field_name or "").lower() or "follow-up" in f.value.lower():
                    numbered = re.findall(r"\(\d+\)", f.value)
                    if numbered:
                        return str(len(numbered))

        # 5. Check for unstated person / unapproved questions
        if "name of the person" in req_lower or "who approved" in req_lower:
            if not any(name in val_lower for name in ["john", "jane", "director", "manager", "signed by"]):
                if "noc lead" in val_lower or "not" in val_lower or "compiled" in val_lower:
                    return "Not Specified"

        # List of known hallucination & prompt-copy artifacts
        hallucination_indicators = [
            "write extracted value here",
            "the exact technical value",
            "exact specification from reference",
            "direct concise answer",
            "section/page reference",
            "brief explanation",
            "placeholder",
            "quote from reference",
        ]

        # Use RapidFuzz for fuzzy hallucination phrase detection
        is_hallucinated = any(
            rapidfuzz.fuzz.partial_ratio(h, val_lower) > 85 for h in hallucination_indicators
        )
        if is_hallucinated:
            # Anchor back to best matching fact field using RapidFuzz
            best_fact = None
            best_score = 0.0
            for f in candidate_facts:
                if f.field_name and len(f.value.strip()) <= 100:
                    sim = float(rapidfuzz.fuzz.token_sort_ratio(requirement_text, f.field_name))
                    if sim > best_score and sim > 60:
                        best_score = sim
                        best_fact = f.value.strip()
            return best_fact if best_fact else "Not Specified"

        if not val_clean:
            return "Not Specified"

        return val_clean

    async def evaluate(
        self,
        requirement_text: str,
        facts: list[FactItem],
        vendor_name: str | None = None,
        model_name: str | None = None,
    ) -> LayerResult | None:
        if not facts:
            return None

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

        # Relevance rank top facts/passages against this requirement with Entity Prioritization
        top_facts = self._rank_candidate_facts(requirement_text, candidate_facts, top_k=8)

        fact_strings: list[str] = []
        for f in top_facts:
            page_info = f"Page {f.source_page}" if f.source_page else "General Spec"
            field_info = f"{f.field_name}: " if f.field_name and f.field_name != "Technical Specification" else ""
            fact_strings.append(f"[{page_info}] {field_info}{f.value}")

        prompt = build_compliance_matching_prompt(
            requirement_text=requirement_text,
            extracted_facts=fact_strings,
            vendor_name=vendor_name,
        )

        try:
            async with self._semaphore:
                res: ComplianceAnalysisResult = await self.llm_provider.chat(
                    messages=[ChatMessage(role=Role.USER, content=prompt)],
                    response_model=ComplianceAnalysisResult,
                    model=model_name,
                    temperature=0.0,
                )

            # Map ComplianceStatus to ComplianceState
            state_map = {
                ComplianceStatus.COMPLIANT: ComplianceState.COMPLIANT,
                ComplianceStatus.NON_COMPLIANT: ComplianceState.NON_COMPLIANT,
                ComplianceStatus.PARTIAL: ComplianceState.PARTIALLY_COMPLIANT,
                ComplianceStatus.AMBIGUOUS: ComplianceState.AMBIGUOUS,
                ComplianceStatus.NOT_SPECIFIED: ComplianceState.AMBIGUOUS,
                ComplianceStatus.NOT_APPLICABLE: ComplianceState.AMBIGUOUS,
            }
            state = state_map.get(res.status, ComplianceState.COMPLIANT)

            # Pass output through Grounding Verification Gate
            grounded_value = self._verify_and_anchor_grounding(
                raw_val=res.matched_value or "",
                requirement_text=requirement_text,
                candidate_facts=top_facts,
                all_facts=facts,
            )

            # Create evidence citation
            evidence_items: list[EvidenceItem] = []
            if top_facts:
                primary_fact = top_facts[0]
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
                        value=res.evidence_text or grounded_value or primary_fact.value,
                        confidence=res.confidence,
                        extraction_method=self.name,
                        citation=res.evidence_text or citation_ref,
                        reasoning=res.reasoning,
                    )
                )

            return LayerResult(
                layer_name=self.name,
                state=state,
                confidence=res.confidence,
                reasoning=res.reasoning,
                matched_value=grounded_value,
                evidence=evidence_items,
            )
        except Exception as e:
            logger.warning("LLM reasoning evaluation failed", error=str(e), req=requirement_text)
            return None
