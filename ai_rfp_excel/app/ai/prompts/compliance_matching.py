def build_compliance_matching_prompt(
    requirement_text: str,
    extracted_facts: list[str],
    vendor_name: str | None = None,
    section_context: str | None = None,
) -> str:
    """Generate prompt to evaluate compliance of vendor specifications against RFP requirement."""
    vendor_info = f" for vendor '{vendor_name}'" if vendor_name else ""
    section_info = f" (Section: {section_context})" if section_context else ""
    facts_str = "\n".join(f"- {fact}" for fact in extracted_facts) if extracted_facts else "No direct facts found."

    return (
        f"You are a strict technical compliance evaluator assessing RFP criteria{vendor_info}{section_info}.\n\n"
        f"RFP Requirement:\n\"{requirement_text}\"\n\n"
        f"Extracted Vendor Data / Document Facts:\n{facts_str}\n\n"
        "Evaluate compliance and choose one status:\n"
        "- COMPLIANT: The vendor fully meets or exceeds all criteria specified.\n"
        "- NON_COMPLIANT: The vendor fails to meet one or more mandatory criteria.\n"
        "- PARTIAL: The vendor partially meets criteria or meets with exceptions.\n"
        "- AMBIGUOUS: Information is contradictory, missing, or insufficient to decide.\n\n"
        "Return a JSON object matching this schema:\n"
        "{\n"
        '  "status": "COMPLIANT" | "NON_COMPLIANT" | "PARTIAL" | "AMBIGUOUS",\n'
        '  "confidence": 0.95,\n'
        '  "reasoning": "Clear, concise technical justification",\n'
        '  "matched_value": "Extract ONLY the exact technical value, measurement, price, count, or spec (e.g. \'$4,250\', \'16 ports\', \'3 years\'). Do NOT return product names, subject nouns, or headers.",\n'
        '  "evidence_text": "Exact supporting text quote from facts"\n'
        "}"
    )
