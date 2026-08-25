from typing import Any


def extraction_prompt(context: dict[str, Any]) -> str:
    return f"""Extract technical specifications from the following text.

Text:
{context.get('text', '')}

Return a JSON object with the following structure:
{{
    "entity_type": "server|gpu|cpu|memory|storage|disk|network|other",
    "specifications": [
        {{
            "field": "field_name",
            "value": "extracted_value",
            "confidence": 0.95
        }}
    ]
}}

Only extract information that is explicitly stated. If information is not available, use "UNKNOWN"."""


def compliance_prompt(context: dict[str, Any]) -> str:
    requirement = context.get('requirement', '')
    reference = context.get('reference', '')

    return f"""Determine if the reference data meets the requirement.

Requirement: {requirement}

Reference Data: {reference}

Return a JSON object with the following structure:
{{
    "status": "COMPLIANT|PARTIALLY_COMPLIANT|NON_COMPLIANT|NOT_FOUND|AMBIGUOUS",
    "confidence": 0.95,
    "evidence": [
        {{
            "text": "evidence text",
            "page": 1,
            "source_type": "text|table|image"
        }}
    ],
    "reasoning": "brief explanation"
}}

Do not invent information. If evidence is not found, use NOT_FOUND."""


def classification_prompt(context: dict[str, Any]) -> str:
    text = context.get('text', '')

    return f"""Classify the following text into one of these categories:
- technical_specification
- requirement
- compliance_rule
- product_information
- other

Text: {text}

Return a JSON object with the following structure:
{{
    "category": "category_name",
    "confidence": 0.95,
    "subcategory": "optional_subcategory"
}}"""


def mapping_prompt(context: dict[str, Any]) -> str:
    canonical_field = context.get('canonical_field', '')
    excel_headers = context.get('excel_headers', [])

    return f"""Map the canonical field to the most appropriate Excel column.

Canonical Field: {canonical_field}

Available Excel Columns:
{chr(10).join(f'- {h}' for h in excel_headers)}

Return a JSON object with the following structure:
{{
    "matched_column": "column_name",
    "confidence": 0.95,
    "mapping_method": "exact|semantic|partial"
}}"""
