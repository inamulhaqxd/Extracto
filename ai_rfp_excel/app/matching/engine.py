"""
Compliance Engine Adapter.
Directly delegates to the PRD-compliant Step 4 Compliance Resolver.
Zero Any (Rule 4). 100% offline (Rule 10).
"""

from __future__ import annotations

from ai_rfp_excel.app.matching.models import (
    ComplianceDecision,
    ComplianceState,
    FactItem,
)
from ai_rfp_excel.app.pipeline.step4_compliance_resolver import (
    resolve_requirement,
)


class ComplianceEngine:
    """Evaluates requirements using the production Step 4 Compliance Resolver."""

    def __init__(self, llm_provider: object | None = None) -> None:
        self.llm_provider = llm_provider

    async def evaluate_requirement(
        self,
        requirement_text: str,
        facts: list[FactItem] | None = None,
        vendor_name: str | None = None,
        model_name: str | None = None,
        requirement_id: str | None = None,
    ) -> ComplianceDecision:
        candidate_snippets: list[dict[str, object]] = []
        if facts:
            for f in facts:
                candidate_snippets.append({
                    "snippet": f"{f.field_name}: {f.value}" if f.field_name else str(f.value),
                    "page_number": f.source_page or 1,
                    "source_type": f.source_type or "text",
                })

        req_payload: dict[str, object] = {
            "requirement_id": requirement_id or "REQ-001",
            "requirement_text": requirement_text,
            "candidate_snippets": candidate_snippets,
            "target_slots": {},
        }

        selected_model = model_name or "qwen2.5:1.5b"
        res = resolve_requirement(req_payload, model_name=selected_model)

        raw_state = res.get("compliance_state", "NOT_FOUND")
        state_enum = ComplianceState.NOT_FOUND
        for s in ComplianceState:
            if s.value == raw_state or s.name == raw_state:
                state_enum = s
                break

        return ComplianceDecision(
            requirement_id=requirement_id,
            requirement_text=requirement_text,
            vendor_name=vendor_name,
            state=state_enum,
            confidence=float(res.get("confidence", 0.85)),
            reasoning=str(res.get("reasoning", "")),
            matched_value=str(res.get("extracted_value") or "") or None,
            resolving_layer=str(res.get("resolving_layer", "step4_compliance_resolver")),
            evidence=[],
        )
