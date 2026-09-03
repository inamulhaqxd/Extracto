import re

from ai_rfp_excel.app.matching.models import (
    ComplianceState,
    EvidenceItem,
    FactItem,
    LayerResult,
)


class ExactMatchLayer:
    """Layer 1: Exact string, model number, or part number matching.

    Strictly matches 1:1 clean atomic specifications. Never matches multi-line text dumps.
    """

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

        # Disallow matching generic header / section words
        invalid_values = {
            "configuration",
            "specifications",
            "specification",
            "overview",
            "attribute",
            "attributes",
            "value",
            "and support",
            "support",
            "section",
            "general requirements",
            "hardware specifications",
            "port configuration",
            "power and environmental",
            "warranty and support",
            "compliance",
            "compliance/marks",
        }

        # Normalize trailing descriptor nouns
        norm_req = re.sub(r"\b(?:processors?|cpus?|modules?|units?|cards?|appliances?)\b", "", req_clean).strip()

        for fact in candidate_facts:
            # Skip multi-line paragraphs or whole-page contexts for Layer 1 exact match
            if "\n" in fact.value or len(fact.value) > 120:
                continue

            f_name_clean = fact.field_name.strip().lower() if fact.field_name else ""
            fact_val_clean = fact.value.strip().lower()
            if not fact_val_clean or fact_val_clean in invalid_values:
                continue

            # Strip multiplier prefixes (e.g. "2x Intel Xeon Gold 6430" -> "intel xeon gold 6430")
            unprefixed_val = re.sub(r"^\d+\s*x\s*", "", fact_val_clean).strip()
            norm_fact_val = re.sub(r"\b(?:processors?|cpus?|modules?|units?|cards?|appliances?)\b", "", fact_val_clean).strip()

            # Exact match conditions
            is_strict_exact = (
                (bool(f_name_clean) and req_clean == f_name_clean)
                or (req_clean == fact_val_clean)
                or (req_clean == unprefixed_val)
                or (bool(norm_req) and norm_req == norm_fact_val)
            )

            if is_strict_exact:
                clean_val = fact.value.strip()
                if f_name_clean and clean_val.lower().startswith(f_name_clean):
                    clean_val = clean_val[len(f_name_clean):].strip(" :-\t")

                # Strip common remnant prefixes
                clean_val = re.sub(r"(?i)^(?:factor|capacity|draw\s*\(typical\)|draw\s*\(max\)|power\s*draw)\s*[:\-\t]?\s*", "", clean_val).strip()

                if not clean_val or clean_val.lower() in invalid_values:
                    continue

                citation_parts: list[str] = []
                if fact.source_page:
                    citation_parts.append(f"Page {fact.source_page}")
                if fact.source_table_id:
                    citation_parts.append(f"Table {fact.source_table_id}")
                elif fact.source_image_id:
                    citation_parts.append(f"Image {fact.source_image_id}")
                citation_ref = ", ".join(citation_parts) if citation_parts else "Document reference"

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
