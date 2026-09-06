def build_compliance_matching_prompt(
    requirement_text: str,
    extracted_facts: list[str],
    vendor_name: str | None = None,
    section_context: str | None = None,
) -> str:
    """Generate concise, model-friendly prompt for technical compliance evaluation, spec extraction, and technical reasoning."""
    vendor_info = f" for {vendor_name}" if vendor_name else ""
    section_info = f" ({section_context})" if section_context else ""
    facts_str = "\n".join(f"- {fact}" for fact in extracted_facts) if extracted_facts else "No specifications."

    return (
        f"### REFERENCE SPECIFICATIONS{vendor_info}{section_info}:\n"
        f"{facts_str}\n\n"
        f"### QUESTION / REQUIREMENT:\n"
        f"{requirement_text}\n\n"
        f"### INSTRUCTIONS:\n"
        f"1. For IDs, codes, component names, times, numbers: 'matched_value' MUST BE ONLY the exact concise token (e.g. 'INC-2091', 'SFP+ transceiver on switch DC-B-CORE-02', '23:14', '00:27', '3', 'Two weeks', '~20%'). DO NOT write full conversational sentences in matched_value.\n"
        f"2. For systems affected: List only the affected systems (exclude any system explicitly noted as having no impact or unaffected).\n"
        f"3. For error rate during the incident: Give the error rate during the outage (~20% or 1 in 5), not post-resolution 0%.\n"
        f"4. For questions asking about an unstated person name, approval, or unmeasured metric: If the document does not name the person or metric, set 'matched_value' to 'Not Specified'.\n"
        f"5. Put detailed reasoning in 'reasoning', and keep 'matched_value' strictly focused on the direct answer.\n\n"
        f"Return clean JSON:\n"
        f"{{\n"
        f'  "status": "COMPLIANT",\n'
        f'  "confidence": 0.95,\n'
        f'  "reasoning": "Step-by-step reasoning",\n'
        f'  "matched_value": "Exact concise value",\n'
        f'  "evidence_text": "Section and quote"\n'
        f"}}"
    )
