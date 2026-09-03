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
    """Layer 3: Strict Unit conversion & normalization (e.g., 64GB = 64 GB = 64 gigabytes).

    Only executes when both requirement and fact contain explicit numeric units that normalize to equality.
    """

    name = "unit_conversion"

    def evaluate(
        self,
        requirement_text: str,
        facts: list[FactItem],
        vendor_name: str | None = None,
    ) -> LayerResult | None:
        if not facts:
            return None

        # Only evaluate if the requirement actually contains a numeric unit
        req_parsed = parse_numeric_with_unit(requirement_text)
        if not req_parsed:
            return None

        req_norm = normalize_unit_string(requirement_text).lower()

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

        num_req, unit_req, _ = req_parsed
        req_token = f"{num_req}{unit_req}"

        for fact in candidate_facts:
            # Skip multi-line paragraphs or page overviews
            if "\n" in fact.value or len(fact.value) > 120:
                continue

            fact_parsed = parse_numeric_with_unit(fact.value)
            if not fact_parsed:
                continue

            fact_norm = normalize_unit_string(fact.value).lower()

            # Strict equality of unit strings or arithmetic quantity equality
            is_unit_match = (
                (bool(fact_norm) and bool(req_norm) and fact_norm == req_norm)
                or (compare_quantities(fact.value, req_token, operator="=") is True)
            )

            if is_unit_match:
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

        return None
