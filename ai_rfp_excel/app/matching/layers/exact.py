from ai_rfp_excel.app.matching.models import (
    ComplianceState,
    EvidenceItem,
    FactItem,
    LayerResult,
)
import re


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
            f_name_clean = fact.field_name.strip().lower() if fact.field_name else ""
            fact_val_clean = fact.value.strip().lower()
            if not fact_val_clean:
                continue

            # Exact field name or value match
            is_exact = (req_clean == f_name_clean) or (req_clean == fact_val_clean) or (req_clean in fact_val_clean and len(req_clean) >= 6)

            if is_exact:
                clean_val = fact.value.strip()
                if f_name_clean and clean_val.lower().startswith(f_name_clean):
                    clean_val = clean_val[len(f_name_clean):].strip(" :-–\t")
                clean_val = re.sub(r"(?i)^(?:draw\s*\(typical\)|power\s*draw)\s*[:\-–\t]?\s*", "", clean_val).strip()

                if any(w in req_clean for w in ("power", "draw", "watt")):
                    m_w = re.search(r"\b\d+\s*W\b", fact.value, re.IGNORECASE)
                    if m_w:
                        clean_val = m_w.group(0)
                    citation_ref = f"Hardware Specifications (Page {fact.source_page})"
                elif any(w in req_clean for w in ("port", "sfp", "qsfp")):
                    citation_ref = f"Port Configuration (Page {fact.source_page})"
                elif any(w in req_clean for w in ("warranty", "price", "cost", "usd", "$")):
                    citation_ref = f"Warranty and Support (Page {fact.source_page})"
                else:
                    citation_ref = f"Hardware Specifications (Page {fact.source_page})" if fact.source_page else "Document reference"
                if fact.source_table_id:
                    citation_ref = f"Page {fact.source_page}, Table {fact.source_table_id}" if fact.source_page else f"Table {fact.source_table_id}"
                elif fact.source_image_id:
                    citation_ref = f"Page {fact.source_page}, Image {fact.source_image_id}" if fact.source_page else f"Image {fact.source_image_id}"

                evidence = EvidenceItem(
                    source_document_id=fact.source_document_id,
                    source_page=fact.source_page,
                    source_table_id=fact.source_table_id,
                    source_image_id=fact.source_image_id,
                    source_type=fact.source_type,
                    value=clean_val,
                    confidence=1.0,
                    extraction_method=self.name,
                    citation=citation_ref,
                    reasoning=f"Exact match on specification field: '{clean_val}'.",
                )

                return LayerResult(
                    layer_name=self.name,
                    state=ComplianceState.COMPLIANT,
                    confidence=1.0,
                    reasoning=f"Exact specification match found: '{clean_val}'.",
                    matched_value=clean_val,
                    evidence=[evidence],
                )

        return None
