from ai_rfp_excel.app.matching.layers.units import (
    compare_quantities,
    normalize_unit_string,
    parse_numeric_with_unit,
)
from ai_rfp_excel.app.matching.models import (
    ComplianceState,
    EvidenceItem,
    FactItem,
    LayerResult,
)


class UnitConversionLayer:
    """Layer 3: Unit conversion & normalization (e.g., 64GB = 64 GB = 64 gigabytes)."""

    name = "unit_conversion"

    def evaluate(
        self,
        requirement_text: str,
        facts: list[FactItem],
        vendor_name: str | None = None,
    ) -> LayerResult | None:
        req_norm = normalize_unit_string(requirement_text).lower()
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

        req_parsed = parse_numeric_with_unit(requirement_text)

        for fact in candidate_facts:
            fact_norm = normalize_unit_string(fact.value).lower()
            if not fact_norm:
                continue

            # Check if normalized fact matches normalized requirement exactly or as substring
            if fact_norm in req_norm or req_norm in fact_norm:
                citation_ref = f"Page {fact.source_page}" if fact.source_page else "Document reference"
                if fact.source_table_id:
                    citation_ref += f", Table {fact.source_table_id}"

                evidence = EvidenceItem(
                    source_document_id=fact.source_document_id,
                    source_page=fact.source_page,
                    source_table_id=fact.source_table_id,
                    source_image_id=fact.source_image_id,
                    source_type=fact.source_type,
                    value=fact.value,
                    confidence=0.94,
                    extraction_method=self.name,
                    citation=citation_ref,
                    reasoning=f"Unit normalization matched '{fact.value}' with '{requirement_text}'.",
                )

                return LayerResult(
                    layer_name=self.name,
                    state=ComplianceState.COMPLIANT,
                    confidence=0.94,
                    reasoning=f"Specification '{fact.value}' matches requirement through unit normalization.",
                    matched_value=fact.value,
                    evidence=[evidence],
                )

            # Check quantity comparison equality if both have units
            if req_parsed:
                num_req, unit_req, _ = req_parsed
                req_token = f"{num_req}{unit_req}"
                if compare_quantities(fact.value, req_token, operator="=") is True:
                    citation_ref = f"Page {fact.source_page}" if fact.source_page else "Document reference"
                    if fact.source_table_id:
                        citation_ref += f", Table {fact.source_table_id}"

                    evidence = EvidenceItem(
                        source_document_id=fact.source_document_id,
                        source_page=fact.source_page,
                        source_table_id=fact.source_table_id,
                        source_image_id=fact.source_image_id,
                        source_type=fact.source_type,
                        value=fact.value,
                        confidence=0.94,
                        extraction_method=self.name,
                        citation=citation_ref,
                        reasoning=f"Unit normalization matched quantity in '{fact.value}' with '{requirement_text}'.",
                    )

                    return LayerResult(
                        layer_name=self.name,
                        state=ComplianceState.COMPLIANT,
                        confidence=0.94,
                        reasoning=f"Specification '{fact.value}' matches requirement through unit normalization.",
                        matched_value=fact.value,
                        evidence=[evidence],
                    )

        return None

