def build_evidence_synthesis_prompt(
    requirement_text: str,
    raw_evidence_snippets: list[str],
    page_number: int | None = None,
    table_id: str | None = None,
) -> str:
    """Generate prompt to synthesize concise, auditable evidence statements with citations."""
    ref_parts = []
    if page_number:
        ref_parts.append(f"Page {page_number}")
    if table_id:
        ref_parts.append(f"Table {table_id}")
    ref_str = f" ({', '.join(ref_parts)})" if ref_parts else ""

    snippets_str = "\n".join(f"- {s}" for s in raw_evidence_snippets) if raw_evidence_snippets else "None"

    return (
        f"You are an RFP audit expert synthesizing evidence citations{ref_str}.\n\n"
        f"Requirement:\n{requirement_text}\n\n"
        f"Source Evidence Snippets:\n{snippets_str}\n\n"
        "Synthesize a clear evidence statement that directly proves or disproves compliance.\n"
        "Return a JSON object matching this schema:\n"
        "{\n"
        '  "evidence_text": "Precise quote or verified fact statement",\n'
        f'  "page_reference": "{", ".join(ref_parts) if ref_parts else "N/A"}",\n'
        '  "confidence": 0.95,\n'
        '  "reasoning": "Explanation of how this snippet satisfies or fails the requirement"\n'
        "}"
    )
