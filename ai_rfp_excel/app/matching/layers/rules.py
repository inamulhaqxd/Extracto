import re
from typing import ClassVar

from ai_rfp_excel.app.matching.layers.units import compare_quantities, parse_numeric_with_unit
from ai_rfp_excel.app.matching.models import (
    ComplianceState,
    EvidenceItem,
    FactItem,
    LayerResult,
)


class RuleBasedLayer:
    """Layer 2: Rule-based & arithmetic comparisons (>=, <=, at least, minimum, redundant)."""

    name = "rule_based"

    # Regex patterns for comparison operators
    OP_PATTERNS: ClassVar[list[tuple[str, str]]] = [
        (r"(?i)\b(?:at least|minimum of|minimum|min|>=|>=)\s*(\d+(?:\.\d+)?\s*[a-zA-Z]*)", ">="),
        (r"(?i)\b(?:up to|maximum of|maximum|max|<=|<=)\s*(\d+(?:\.\d+)?\s*[a-zA-Z]*)", "<="),
        (r"(?i)\b(?:greater than|>)\s*(\d+(?:\.\d+)?\s*[a-zA-Z]*)", ">"),
        (r"(?i)\b(?:less than|<)\s*(\d+(?:\.\d+)?\s*[a-zA-Z]*)", "<"),
        (r"(?i)\b(?:exactly|=|==)\s*(\d+(?:\.\d+)?\s*[a-zA-Z]*)", "="),
    ]


    def evaluate(
        self,
        requirement_text: str,
        facts: list[FactItem],
        vendor_name: str | None = None,
    ) -> LayerResult | None:
        req_lower = requirement_text.lower().strip()
        if not facts:
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

        # 1. Check numeric / quantity operator rules
        for pat, op in self.OP_PATTERNS:
            match = re.search(pat, requirement_text)
            if match:
                req_threshold_str = match.group(1).strip()
                req_parsed = parse_numeric_with_unit(req_threshold_str)

                best_res: LayerResult | None = None

                for fact in candidate_facts:
                    fact_parsed = parse_numeric_with_unit(fact.value)
                    if not fact_parsed or not req_parsed:
                        # Try pure numeric comparison if unit is missing
                        num_match_req = re.search(r"(\d+(?:\.\d+)?)", req_threshold_str)
                        num_match_fact = re.search(r"(\d+(?:\.\d+)?)", fact.value)
                        if num_match_req and num_match_fact:
                            val_req = float(num_match_req.group(1))
                            val_fact = float(num_match_fact.group(1))
                            if op == ">=":
                                is_valid = val_fact >= val_req
                            elif op == "<=":
                                is_valid = val_fact <= val_req
                            elif op == ">":
                                is_valid = val_fact > val_req
                            elif op == "<":
                                is_valid = val_fact < val_req
                            else:
                                is_valid = abs(val_fact - val_req) < 1e-6

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
                                confidence=0.95,
                                extraction_method=self.name,
                                citation=citation_ref,
                                reasoning=f"Numeric rule evaluation: {val_fact} {op} {val_req} (Requirement: {req_threshold_str}).",
                            )

                            current_res = LayerResult(
                                layer_name=self.name,
                                state=ComplianceState.COMPLIANT if is_valid else ComplianceState.NON_COMPLIANT,
                                confidence=0.95,
                                reasoning=(
                                    f"Provided value '{fact.value}' satisfies requirement '{req_threshold_str}' ({op})."
                                    if is_valid
                                    else f"Provided value '{fact.value}' fails requirement threshold '{req_threshold_str}' ({op})."
                                ),
                                matched_value=fact.value,
                                evidence=[evidence],
                            )
                            if is_valid:
                                return current_res
                            if best_res is None:
                                best_res = current_res
                        continue

                    # Quantity comparison with unit conversion
                    res = compare_quantities(fact.value, req_threshold_str, operator=op)
                    if res is not None:
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
                            confidence=0.95,
                            extraction_method=self.name,
                            citation=citation_ref,
                            reasoning=f"Quantity check: {fact.value} compared against requirement threshold {req_threshold_str} ({op}).",
                        )

                        current_res = LayerResult(
                            layer_name=self.name,
                            state=ComplianceState.COMPLIANT if res else ComplianceState.NON_COMPLIANT,
                            confidence=0.95,
                            reasoning=(
                                f"Specification value '{fact.value}' complies with threshold '{req_threshold_str}'."
                                if res
                                else f"Specification value '{fact.value}' does not meet required threshold '{req_threshold_str}'."
                            ),
                            matched_value=fact.value,
                            evidence=[evidence],
                        )
                        if res:  # Compliant match found!
                            return current_res
                        if best_res is None:
                            best_res = current_res

                if best_res is not None:
                    return best_res


        # 2. Check redundancy & dual architecture rules
        redundancy_keywords = ("redundant", "dual", "hot-swap", "hot-pluggable", "2x", "n+1")
        if any(kw in req_lower for kw in redundancy_keywords):
            for fact in candidate_facts:
                fact_lower = fact.value.lower()
                if any(kw in fact_lower for kw in redundancy_keywords):
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
                        confidence=0.92,
                        extraction_method=self.name,
                        citation=citation_ref,
                        reasoning=f"Redundancy criteria matched in {citation_ref}.",
                    )

                    return LayerResult(
                        layer_name=self.name,
                        state=ComplianceState.COMPLIANT,
                        confidence=0.92,
                        reasoning=f"High-availability / redundancy requirement met by '{fact.value}'.",
                        matched_value=fact.value,
                        evidence=[evidence],
                    )

        return None
