from ai_rfp_excel.app.matching.models import (
    ComplianceState,
    EvidenceItem,
    FactItem,
    LayerResult,
)


class ExactMatchLayer:
    """Layer 1: Exact string, model number, or part number matching."""

    name = "exact_match"

    def evaluate(
        self,
        requirement_text: str,
        facts: list[FactItem],
        vendor_name: str | None = None,
    ) -> LayerResult | None:
        req_clean = requirement_text.strip().lower()
        if not req_clean or not facts:
            return None

        # Filter by vendor if specified
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

        for fact in candidate_facts:
            fact_val_clean = fact.value.strip().lower()
            if not fact_val_clean:
                continue

            # Exact full match or specific model name match
            is_exact = (req_clean == fact_val_clean) or (len(req_clean) >= 6 and req_clean in fact_val_clean)

            if is_exact:
                citation_ref = f"Page {fact.source_page}" if fact.source_page else "Document reference"
                if fact.source_table_id:
                    citation_ref += f", Table {fact.source_table_id}"
                elif fact.source_image_id:
                    citation_ref += f", Image {fact.source_image_id}"

                evidence = EvidenceItem(
                    source_document_id=fact.source_document_id,
                    source_page=fact.source_page,
                    source_table_id=fact.source_table_id,
                    source_image_id=fact.source_image_id,
                    source_type=fact.source_type,
                    value=fact.value,
                    confidence=1.0,
                    extraction_method=self.name,
                    citation=citation_ref,
                    reasoning=f"Exact match found for requirement in {citation_ref}.",
                )

                return LayerResult(
                    layer_name=self.name,
                    state=ComplianceState.COMPLIANT,
                    confidence=1.0,
                    reasoning=f"Exact match verified with source data ({fact.value}).",
                    matched_value=fact.value,
                    evidence=[evidence],
                )


        return None
