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
    """Layer 2: Strict arithmetic, quantity threshold & redundancy rule verification.

    Resolves explicitly defined numeric criteria (>=, <=, at least, redundant) against
    semantically relevant facts. Leaves broader and contextual technical matching to the AI layer.
    """

    name = "rule_based"

    # Regex patterns for comparison operators
    OP_PATTERNS: ClassVar[list[tuple[str, str]]] = [
        (r"(?i)\b(?:at least|minimum of|minimum|min|>=)\s*(\d+(?:\.\d+)?\s*[a-zA-Z%]+)", ">="),
        (r"(?i)\b(?:up to|maximum of|maximum|max|<=)\s*(\d+(?:\.\d+)?\s*[a-zA-Z%]+)", "<="),
        (r"(?i)\b(?:greater than|>)\s*(\d+(?:\.\d+)?\s*[a-zA-Z%]+)", ">"),
        (r"(?i)\b(?:less than|<)\s*(\d+(?:\.\d+)?\s*[a-zA-Z%]+)", "<"),
        (r"(?i)\b(?:exactly|=|==)\s*(\d+(?:\.\d+)?\s*[a-zA-Z%]+)", "="),
    ]

    def _is_relevant_field(self, req_text: str, fact: FactItem, req_unit: str | None = None) -> bool:
        """Verify the fact is actually relevant to the requirement to avoid cross-domain false positives."""
        req_lower = req_text.lower()
        f_name_lower = (fact.field_name or "").lower()
        f_val_lower = fact.value.lower()

        # Check field name words
        if f_name_lower and len(f_name_lower) >= 3:
            f_words = [w for w in re.findall(r"[a-z0-9]+", f_name_lower) if len(w) >= 3]
            if f_words and any(w in req_lower for w in f_words):
                return True

        # Check matching unit families (e.g. both are TB/GB/terabytes)
        if req_unit:
            fact_parsed = parse_numeric_with_unit(fact.value)
            if fact_parsed:
                _, f_unit, _ = fact_parsed
                storage_units = {"tb", "gb", "mb", "pb", "terabytes", "gigabytes", "megabytes", "petabytes"}
                power_units = {"w", "kw", "mw", "watts", "kilowatts"}
                rate_units = {"gbps", "mbps", "tbps", "kbps"}
                freq_units = {"ghz", "mhz", "khz"}

                for u_family in (storage_units, power_units, rate_units, freq_units):
                    if req_unit.lower() in u_family and f_unit.lower() in u_family:
                        return True

        # Common domain matches
        domains = ["power", "watt", "throughput", "bandwidth", "memory", "ram", "storage", "capacity", "fan", "cooling", "psu"]
        for d in domains:
            if d in req_lower and (d in f_name_lower or d in f_val_lower):
                return True

        return False

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

        # 1. Redundancy / Dual architecture verification
        if any(rk in req_lower for rk in ("redundant", "redundancy", "dual power")):
            redundancy_keywords = ("redundant", "dual", "hot-swap", "hot-pluggable", "2x", "n+1")
            for fact in candidate_facts:
                if not self._is_relevant_field(requirement_text, fact):
                    continue
                f_val_lower = fact.value.lower()
                if any(rk in f_val_lower for rk in redundancy_keywords):
                    citation_ref = f"Page {fact.source_page}" if fact.source_page else "Document reference"
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

        # 2. Check numeric quantity operator rules with strict unit and field validation
        for pat, op in self.OP_PATTERNS:
            match = re.search(pat, requirement_text)
            if match:
                req_threshold_str = match.group(1).strip()
                req_parsed = parse_numeric_with_unit(req_threshold_str)
                if not req_parsed:
                    continue

                _, req_unit, _ = req_parsed
                best_res: LayerResult | None = None

                for fact in candidate_facts:
                    if not self._is_relevant_field(requirement_text, fact, req_unit=req_unit):
                        continue

                    # Strict quantity comparison with unit conversion
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

        # Defer all complex / semantic matching to the AI reasoning layer
        return None
