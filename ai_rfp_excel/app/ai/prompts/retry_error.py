def build_retry_error_prompt(
    previous_raw_output: str,
    validation_error: str,
    schema_json: str,
) -> str:
    """Generate retry prompt providing previous failed output and validation error context."""
    return (
        "Your previous response failed JSON schema validation.\n\n"
        f"Validation Error Details:\n{validation_error}\n\n"
        f"Your Previous Response Was:\n{previous_raw_output}\n\n"
        "Please fix the error and return ONLY a valid JSON object matching this schema:\n"
        f"{schema_json}\n\n"
        "Do NOT include markdown explanations or code fences outside the JSON object."
    )
