def build_spec_extraction_prompt(
    text_content: str,
    page_number: int | None = None,
    table_context: str | None = None,
) -> str:
    """Generate prompt to extract technical specifications and hardware/software parameters."""
    page_info = f" on Page {page_number}" if page_number else ""
    table_info = f"\nTable Data:\n{table_context}\n" if table_context else ""

    return (
        f"You are a technical document analyst extracting factual equipment specifications from an RFP document{page_info}.\n\n"
        "Extract all distinct technical specifications, constraints, quantities, models, and capabilities found in the text.\n"
        "Do NOT invent or hallucinate specifications not present in the source.\n\n"
        f"Document Content:\n{text_content}\n"
        f"{table_info}\n"
        "Return a JSON object matching the following schema:\n"
        "{\n"
        '  "specifications": [\n'
        '    {"feature": "Feature name", "value": "Extracted value", "source_snippet": "Exact quote", "confidence": 1.0}\n'
        "  ],\n"
        '  "summary": "Brief summary of extracted items"\n'
        "}"
    )
