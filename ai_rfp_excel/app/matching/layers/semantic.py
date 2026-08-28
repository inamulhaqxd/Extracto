import re

from ai_rfp_excel.app.matching.models import (
    ComplianceState,
    EvidenceItem,
    FactItem,
    LayerResult,
)

TECH_SYNONYMS: dict[str, set[str]] = {
    "cpu": {"cpu", "processor", "processors", "cores", "compute", "xeon", "epyc"},
    "processor": {"cpu", "processor", "processors", "cores", "compute", "xeon", "epyc"},
    "ram": {"ram", "memory", "dimm", "ddr4", "ddr5", "ecc"},
    "memory": {"ram", "memory", "dimm", "ddr4", "ddr5", "ecc"},
    "storage": {"storage", "disk", "disks", "drive", "drives", "ssd", "hdd", "nvme", "array"},
    "ssd": {"ssd", "flash", "nvme", "solid state", "all-flash"},
    "nic": {"nic", "adapter", "network card", "port", "ports", "interface", "interfaces", "ethernet"},
    "switch": {"switch", "fabric", "tor", "spine", "leaf"},
    "power": {"power", "psu", "power supply", "watt", "watts", "w", "feed"},
    "fan": {"fan", "fans", "cooling", "blower", "thermal"},
}


def tokenize(text: str) -> set[str]:
    """Tokenize text into lowercase alphanumeric words, filtering out short stopwords."""
    stopwords = {"the", "a", "an", "and", "or", "of", "to", "in", "is", "for", "with", "must", "have", "be", "at", "by"}
    words = re.findall(r"[a-zA-Z0-9]+", text.lower())
    return {w for w in words if len(w) > 1 and w not in stopwords}


class SemanticMatchLayer:
    """Layer 4: Semantic keyword similarity, token overlap, and tech synonyms."""

    name = "semantic_match"

    def evaluate(
        self,
        requirement_text: str,
        facts: list[FactItem],
        vendor_name: str | None = None,
    ) -> LayerResult | None:
        req_tokens = tokenize(requirement_text)
        if not req_tokens or not facts:
            return None

        # Expand requirement tokens with synonyms
        expanded_req_tokens = set(req_tokens)
        for t in req_tokens:
            if t in TECH_SYNONYMS:
                expanded_req_tokens.update(TECH_SYNONYMS[t])

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

        best_score = 0.0
        best_fact: FactItem | None = None

        for fact in candidate_facts:
            fact_tokens = tokenize(fact.value)
            if not fact_tokens:
                continue

            expanded_fact_tokens = set(fact_tokens)
            for t in fact_tokens:
                if t in TECH_SYNONYMS:
                    expanded_fact_tokens.update(TECH_SYNONYMS[t])

            # Calculate token intersection / overlap
            common = expanded_req_tokens.intersection(expanded_fact_tokens)
            if not common:
                continue

            # Jaccard and recall scores
            recall = len(common) / len(req_tokens)
            precision = len(common) / len(fact_tokens)
            jaccard = len(common) / len(expanded_req_tokens.union(expanded_fact_tokens))

            # Combined heuristic score
            score = (recall * 0.6) + (precision * 0.2) + (jaccard * 0.2)
            if score > best_score:
                best_score = score
                best_fact = fact

        if best_fact and best_score >= 0.50:
            confidence = min(0.89, round(0.70 + (best_score * 0.2), 2))
            citation_ref = f"Page {best_fact.source_page}" if best_fact.source_page else "Document reference"
            if best_fact.source_table_id:
                citation_ref += f", Table {best_fact.source_table_id}"

            evidence = EvidenceItem(
                source_document_id=best_fact.source_document_id,
                source_page=best_fact.source_page,
                source_table_id=best_fact.source_table_id,
                source_image_id=best_fact.source_image_id,
                source_type=best_fact.source_type,
                value=best_fact.value,
                confidence=confidence,
                extraction_method=self.name,
                citation=citation_ref,
                reasoning=f"Semantic matching identified relevant technical match ({int(best_score*100)}% keyword overlap).",
            )

            state = ComplianceState.COMPLIANT if best_score >= 0.60 else ComplianceState.PARTIALLY_COMPLIANT

            return LayerResult(
                layer_name=self.name,
                state=state,
                confidence=confidence,
                reasoning=f"Semantic similarity match with source fact '{best_fact.value}'.",
                matched_value=best_fact.value,
                evidence=[evidence],
            )

        return None
