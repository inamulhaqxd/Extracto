import re

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

        # Sort candidate facts so exact matches with longer field names match first
        sorted_facts = sorted(
            candidate_facts,
            key=lambda f: len(f.field_name or "") if (f.field_name and f.field_name.lower() in req_clean) else 0,
            reverse=True,
        )

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
        }

        for fact in sorted_facts:
            f_name_clean = fact.field_name.strip().lower() if fact.field_name else ""
            fact_val_clean = fact.value.strip().lower()
            if not fact_val_clean or fact_val_clean in invalid_values:
                continue

            # Exact field name or exact value match (avoid single-word loose matches like 'port')
            is_exact = (
                (req_clean == f_name_clean)
                or (req_clean == fact_val_clean)
                or (req_clean in fact_val_clean and len(req_clean) >= 6)
                or (bool(f_name_clean) and len(f_name_clean) >= 4 and f_name_clean == req_clean.split()[0])
                or (bool(f_name_clean) and f_name_clean in req_clean and len(f_name_clean.split()) >= 2)
            )

            if is_exact:
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
