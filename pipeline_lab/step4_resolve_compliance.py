#!/usr/bin/env python3
"""
Step 4: "The Compliance & Answer Resolver" — AI Spec Matching & Value Extraction.
Consumes Step 3 (candidate_evidence.json) and uses local Ollama reasoning to:
1. Extract concise, factual answers to Excel requirements.
2. Determine compliance status (COMPLIANT, NON_COMPLIANT, PARTIALLY_COMPLIANT, NOT_FOUND, AMBIGUOUS).
3. Enforce Rule 7 Zero-Hallucination: Missing evidence strictly outputs 'NOT_SPECIFIED'.
4. Map extracted values directly to target Excel cells (answer, remarks, compliance).
5. Output clean, validated artifact in compliance_decisions.json (Rule 8).

Strict typing only — zero Any (Rule 4). 100% offline (Rule 10).
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Literal, NotRequired, TypedDict, cast

import httpx

ComplianceState = Literal["COMPLIANT", "PARTIALLY_COMPLIANT", "NON_COMPLIANT", "NOT_FOUND", "AMBIGUOUS"]

OLLAMA_BASE_URL: str = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
DEFAULT_LLM_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")
CONFIDENCE_REVIEW_THRESHOLD: float = 0.70
DEFAULT_CONFIDENCE: float = 0.85
VALID_CELL_REGEX: re.Pattern[str] = re.compile(r"^[A-Za-z]+[1-9][0-9]*$")

ANSWER_SLOT_TYPES: set[str] = {
    "answer", "value", "vendor", "response", "vendor_response",
    "extracted_value", "result_value", "specification",
}
REMARKS_SLOT_TYPES: set[str] = {
    "remarks", "evidence", "citation", "notes", "comment",
    "comments", "description", "explanation", "details",
}
COMPLIANCE_SLOT_TYPES: set[str] = {
    "compliance", "status", "compliance_state", "compliance_status",
    "result", "verdict",
}


class LLMResolution(TypedDict):
    extracted_value: str
    compliance_state: ComplianceState
    remarks: str
    citation: str
    confidence: float
    columns: NotRequired[dict[str, str]]


class SlotAssignment(TypedDict):
    slot_type: str
    cell_coordinate: str
    value: str | int | float | bool | None
    needs_review: bool


class ComplianceDecision(TypedDict):
    requirement_id: str
    sheet_name: str
    row_number: int
    section: str | None
    requirement_text: str
    extracted_value: str
    compliance_state: ComplianceState
    remarks: str
    citation: str
    confidence: float
    needs_review: bool
    slot_assignments: dict[str, SlotAssignment]


class Step4Output(TypedDict):
    document_id: str
    workbook_id: str
    total_requirements: int
    compliant_count: int
    non_compliant_count: int
    partially_compliant_count: int
    not_specified_count: int
    ambiguous_count: int
    items: list[ComplianceDecision]


SYSTEM_PROMPT: str = """You are a strict, factual AI technical compliance analyst evaluating RFP tender specifications.
Your job is to answer the question using ONLY the provided candidate evidence from the technical document.

Rules for deciding answer format and length:
1. Answer Length & Format:
   - If the question asks for a specific fact, number, metric, capacity, time, period, or model (e.g. 'How many', 'What is the limit', 'RAM', 'Hours', 'Refresh cycle', 'Which model'), provide ONLY the concise value or short phrase (e.g. '16 GB', '3 years', 'Over 50 pages', '5 business days'). Do NOT repeat the question or add conversational fluff.
   - If the question asks to explain, describe, compare, or give reason ('Why?', 'Explain', 'What happens if?'), provide a clear, concise 1-2 sentence explanation.
2. Excel Target Columns ("columns" dictionary):
   - You must evaluate what each target column expects based on its name:
     * Answer/Value columns (e.g. 'AI Answer', 'Specification', 'Response', 'Value'): provide ONLY the concise answer value.
     * Source/Citation columns (e.g. 'Source Section', 'Citation', 'Location', 'Page', 'Reference'): provide ONLY the exact document location (e.g. 'Page 1, Table T02-01' or 'Page 1, Section 3.2'). Do NOT write full explanation sentences in a source column.
     * Remarks/Notes columns (e.g. 'Remarks', 'Comments', 'Notes', 'Explanation'): provide the explanation sentence.
     * Status/Compliance columns (e.g. 'Compliance', 'Status'): provide 'COMPLIANT' or 'NON_COMPLIANT'.
3. ZERO HALLUCINATION (Rule 7): If the evidence does NOT contain the answer, you MUST set extracted_value to "NOT_SPECIFIED", citation to "None", and compliance_state to "NOT_FOUND".
4. Determine compliance_state as:
   - COMPLIANT: The evidence confirms the requirement or answers the factual query.
   - NON_COMPLIANT: The evidence explicitly conflicts with or fails the requirement.
   - PARTIALLY_COMPLIANT: Only some conditions are met.
   - NOT_FOUND: The specification or answer is absent from the evidence.
   - AMBIGUOUS: Conflicting or unclear evidence.
5. Provide a brief citation citing the page number and sentence/table.
6. You MUST respond with ONLY valid JSON adhering strictly to this schema:
{
  "extracted_value": "exact concise answer or NOT_SPECIFIED",
  "compliance_state": "COMPLIANT" | "NON_COMPLIANT" | "PARTIALLY_COMPLIANT" | "NOT_FOUND" | "AMBIGUOUS",
  "remarks": "concise explanation or calculation",
  "citation": "Page X, Table Y / Section Z",
  "confidence": 0.95,
  "columns": {
    "<Column Name>": "value appropriate for this column"
  }
}"""


def build_prompt(
    requirement_text: str,
    section: str | None,
    candidate_snippets: list[dict[str, object]],
    target_columns: list[str] | None = None,
) -> str:
    """Construct structured user prompt with requirement, candidate evidence, and target Excel columns."""
    prompt_parts: list[str] = [f"Requirement / Question: {requirement_text}"]
    if section:
        prompt_parts.append(f"Section Context: {section}")

    if target_columns:
        prompt_parts.append(
            "\nTarget Excel Columns to fill for this row:\n"
            + "\n".join(f"- {col}" for col in target_columns)
        )

    prompt_parts.append("\nCandidate Evidence Snippets from Technical Document:")
    for idx, snippet_item in enumerate(candidate_snippets):
        page = snippet_item.get("page_number", "Unknown")
        src_type = snippet_item.get("source_type", "text")
        snippet_text = str(snippet_item.get("snippet", "")).strip()
        prompt_parts.append(f"[{idx+1}] Page {page} ({src_type}):\n{snippet_text}")

    prompt_parts.append("\nRespond with the JSON object only:")
    return "\n".join(prompt_parts)


def parse_llm_json_response(raw_response: str) -> LLMResolution:
    """Parse, sanitize, and validate JSON response from local Ollama LLM."""
    match = re.search(r"\{[\s\S]*\}", raw_response)
    clean_text = match.group(0) if match else raw_response.strip()

    try:
        data: dict[str, object] = json.loads(clean_text, strict=False)
    except Exception:
        return {
            "extracted_value": "NOT_SPECIFIED",
            "compliance_state": "AMBIGUOUS",
            "remarks": f"Failed to parse structured response: {raw_response[:100]}",
            "citation": "Parsing Error",
            "confidence": 0.30,
        }

    # Normalize extracted_value
    raw_val = data.get("extracted_value")
    if raw_val is None:
        extracted_val = "NOT_SPECIFIED"
    elif isinstance(raw_val, (list, dict)):
        extracted_val = json.dumps(raw_val)
    else:
        extracted_val = str(raw_val).strip()

    if extracted_val.upper() in ("", "NONE", "NULL", "N/A", "NOT_SPECIFIED", "NOT SPECIFIED", "UNKNOWN"):
        extracted_val = "NOT_SPECIFIED"

    # Normalize compliance_state
    raw_state = str(data.get("compliance_state", "NOT_FOUND")).strip().upper()
    normalized_state = raw_state.replace("-", "_").replace(" ", "_")
    if normalized_state == "PARTIAL":
        normalized_state = "PARTIALLY_COMPLIANT"

    if normalized_state in ("COMPLIANT", "PARTIALLY_COMPLIANT", "NON_COMPLIANT", "NOT_FOUND", "AMBIGUOUS"):
        state: ComplianceState = cast(ComplianceState, normalized_state)
    else:
        state = "NOT_FOUND"

    # Invariant: NOT_SPECIFIED strictly implies NOT_FOUND
    if extracted_val == "NOT_SPECIFIED" or state == "NOT_FOUND":
        extracted_val = "NOT_SPECIFIED"
        state = "NOT_FOUND"

    try:
        confidence = float(str(data.get("confidence", DEFAULT_CONFIDENCE)))
        confidence = max(0.0, min(1.0, confidence))
    except (ValueError, TypeError):
        confidence = DEFAULT_CONFIDENCE if state != "NOT_FOUND" else 0.0

    raw_columns = data.get("columns")
    columns_map: dict[str, str] = {}
    if isinstance(raw_columns, dict):
        for k, v in raw_columns.items():
            if k is not None and v is not None:
                columns_map[str(k).strip()] = str(v).strip()

    return {
        "extracted_value": extracted_val,
        "compliance_state": state,
        "remarks": str(data.get("remarks", "")).strip(),
        "citation": str(data.get("citation", "")).strip(),
        "confidence": confidence,
        "columns": columns_map,
    }


def call_local_ollama(
    prompt: str,
    model_name: str = DEFAULT_LLM_MODEL,
    timeout: float = 30.0,
    client: httpx.Client | None = None,
) -> str | None:
    """Call local Ollama /api/chat with format=json (100% offline)."""
    url = f"{OLLAMA_BASE_URL}/api/chat"
    payload: dict[str, object] = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "format": "json",
        "options": {"temperature": 0.0},
        "stream": False,
    }

    try:
        c = client if client is not None else httpx.Client(timeout=timeout)
        try:
            res = c.post(url, json=payload)
            if res.status_code == 200:
                msg = res.json().get("message")
                if isinstance(msg, dict):
                    return str(msg.get("content", ""))
        finally:
            if client is None:
                c.close()
    except Exception:
        pass

    return None


def offline_deterministic_fallback(candidate_snippets: list[dict[str, object]]) -> LLMResolution:
    """Universal Zero-Hallucination fallback when local AI is offline (Rule 7 & Rule 10)."""
    top_page = candidate_snippets[0].get("page_number", 1) if candidate_snippets else 1
    has_evidence = bool(candidate_snippets)
    return {
        "extracted_value": "NOT_SPECIFIED",
        "compliance_state": "NOT_FOUND",
        "remarks": "AI reasoning offline; unverified evidence flagged for review."
        if has_evidence else "No candidate evidence found in document.",
        "citation": f"Page {top_page}" if has_evidence else "None",
        "confidence": 0.0,
        "columns": {},
    }


def map_slots(
    target_slots: dict[str, dict[str, str | int | bool | None]],
    resolution: LLMResolution,
    needs_review: bool,
) -> dict[str, SlotAssignment]:
    """Map the resolved extracted values and remarks to target Excel cell coordinates."""
    assignments: dict[str, SlotAssignment] = {}
    ai_columns = resolution.get("columns", {})

    for slot_name, slot_info in target_slots.items():
        cell_raw = slot_info.get("cell_coordinate")
        if cell_raw is None:
            continue
        cell = str(cell_raw).strip()
        if not cell or not VALID_CELL_REGEX.match(cell):
            continue

        # Formula safety: NEVER overwrite existing Excel formulas (Rule 9)
        if bool(slot_info.get("has_formula", False)):
            continue

        raw_type = str(slot_info.get("slot_type", slot_name)).strip().lower()
        header_name = str(slot_info.get("header_name", "")).strip()

        # 1. First check if AI directly provided a value for this column header
        val_to_write: str | None = None
        if ai_columns:
            if header_name and header_name in ai_columns:
                val_to_write = ai_columns[header_name]
            elif header_name:
                h_lower = header_name.lower()
                for c_k, c_v in ai_columns.items():
                    if c_k.lower() == h_lower:
                        val_to_write = c_v
                        break
            if val_to_write is None and slot_name in ai_columns:
                val_to_write = ai_columns[slot_name]

        # 2. Smart fallback if column wasn't in AI columns dict
        if val_to_write is None:
            is_source_col = any(
                kw in header_name.lower() or kw in raw_type
                for kw in ("source", "section", "citation", "page", "location", "reference")
            ) and not any(
                kw in header_name.lower() for kw in ("answer", "response", "value")
            )

            if is_source_col:
                val_to_write = resolution["citation"] if resolution["citation"] else "NOT_SPECIFIED"
            elif raw_type in ANSWER_SLOT_TYPES:
                val_to_write = resolution["extracted_value"]
            elif raw_type in REMARKS_SLOT_TYPES:
                citation_suffix = f" ({resolution['citation']})" if resolution["citation"] else ""
                val_to_write = f"{resolution['remarks']}{citation_suffix}"
            elif raw_type in COMPLIANCE_SLOT_TYPES:
                val_to_write = resolution["compliance_state"]
            else:
                val_to_write = resolution["extracted_value"]

        # Rule 7 Zero-Hallucination: For missing items, ensure answer slot receives NOT_SPECIFIED
        if resolution["extracted_value"] == "NOT_SPECIFIED" or resolution["compliance_state"] == "NOT_FOUND":
            if raw_type in ANSWER_SLOT_TYPES or any(kw in header_name.lower() for kw in ("answer", "response", "spec", "value")):
                val_to_write = "NOT_SPECIFIED"

        assignments[slot_name] = {
            "slot_type": raw_type,
            "cell_coordinate": cell,
            "value": val_to_write,
            "needs_review": needs_review,
        }

    return assignments


def resolve_requirement(
    requirement: dict[str, object],
    model_name: str = DEFAULT_LLM_MODEL,
    use_ollama: bool = True,
    client: httpx.Client | None = None,
) -> ComplianceDecision:
    """Resolve a single requirement using local LLM or deterministic fallback."""
    req_id = str(requirement.get("requirement_id", ""))
    sheet = str(requirement.get("sheet_name", ""))
    row = int(str(requirement.get("row_number", 0)))
    section_raw = requirement.get("section")
    section = str(section_raw) if section_raw is not None else None
    req_text = str(requirement.get("requirement_text", ""))

    snippets_raw = requirement.get("candidate_snippets", [])
    snippets: list[dict[str, object]] = [
        snip for snip in (snippets_raw if isinstance(snippets_raw, list) else [])
        if isinstance(snip, dict) and str(snip.get("snippet", "")).strip()
    ]

    slots_raw = requirement.get("target_slots", {})
    target_slots: dict[str, dict[str, str | int | bool | None]] = {
        k: v for k, v in (slots_raw.items() if isinstance(slots_raw, dict) else [])
        if isinstance(v, dict)
    }

    target_columns: list[str] = []
    for s_info in target_slots.values():
        h = str(s_info.get("header_name", "")).strip()
        if h and h not in target_columns:
            target_columns.append(h)

    resolution: LLMResolution
    if not snippets:
        resolution = offline_deterministic_fallback([])
    else:
        parsed_res: LLMResolution | None = None
        if use_ollama:
            prompt = build_prompt(req_text, section, snippets, target_columns=target_columns)
            llm_raw = call_local_ollama(prompt, model_name=model_name, client=client)
            if llm_raw:
                parsed_res = parse_llm_json_response(llm_raw)

        if parsed_res is not None:
            resolution = parsed_res
        else:
            resolution = offline_deterministic_fallback(snippets)

    needs_review = (
        resolution["compliance_state"] in ("NOT_FOUND", "AMBIGUOUS")
        or resolution["confidence"] < CONFIDENCE_REVIEW_THRESHOLD
    )

    slot_assignments = map_slots(target_slots, resolution, needs_review=needs_review)

    return {
        "requirement_id": req_id,
        "sheet_name": sheet,
        "row_number": row,
        "section": section,
        "requirement_text": req_text,
        "extracted_value": resolution["extracted_value"],
        "compliance_state": resolution["compliance_state"],
        "remarks": resolution["remarks"],
        "citation": resolution["citation"],
        "confidence": resolution["confidence"],
        "needs_review": needs_review,
        "slot_assignments": slot_assignments,
    }


def run_compliance_resolution(
    candidate_evidence_path: Path,
    output_path: Path | None = None,
    model_name: str = DEFAULT_LLM_MODEL,
    use_ollama: bool = True,
) -> Step4Output:
    """Execute Step 4 pipeline resolving all requirements and writing compliance_decisions.json."""
    with open(candidate_evidence_path, "r", encoding="utf-8") as f:
        evidence_data: dict[str, object] = json.load(f)

    doc_id = str(evidence_data.get("document_id", "DOC-UNKNOWN"))
    wb_id = str(evidence_data.get("workbook_id", "WB-UNKNOWN"))
    items_raw = evidence_data.get("items", [])

    decisions: list[ComplianceDecision] = []
    if isinstance(items_raw, list):
        valid_items = [item for item in items_raw if isinstance(item, dict)]
        if use_ollama:
            with httpx.Client(timeout=30.0) as client:
                for item in valid_items:
                    decisions.append(
                        resolve_requirement(item, model_name=model_name, use_ollama=True, client=client)
                    )
        else:
            for item in valid_items:
                decisions.append(
                    resolve_requirement(item, model_name=model_name, use_ollama=False)
                )

    result: Step4Output = {
        "document_id": doc_id,
        "workbook_id": wb_id,
        "total_requirements": len(decisions),
        "compliant_count": sum(1 for d in decisions if d["compliance_state"] == "COMPLIANT"),
        "non_compliant_count": sum(1 for d in decisions if d["compliance_state"] == "NON_COMPLIANT"),
        "partially_compliant_count": sum(1 for d in decisions if d["compliance_state"] == "PARTIALLY_COMPLIANT"),
        "not_specified_count": sum(1 for d in decisions if d["compliance_state"] == "NOT_FOUND"),
        "ambiguous_count": sum(1 for d in decisions if d["compliance_state"] == "AMBIGUOUS"),
        "items": decisions,
    }

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Step 4: The Compliance & Answer Resolver.")
    parser.add_argument(
        "--evidence",
        type=Path,
        default=Path("pipeline_lab/candidate_evidence.json"),
        help="Path to Step 3 candidate_evidence.json artifact",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("pipeline_lab/compliance_decisions.json"),
        help="Path to save Step 4 compliance_decisions.json",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_LLM_MODEL,
        help=f"Ollama local model name (default: {DEFAULT_LLM_MODEL})",
    )
    parser.add_argument(
        "--offline-fallback",
        action="store_true",
        help="Force deterministic offline fallback without calling Ollama",
    )
    args = parser.parse_args()

    print(f"Loading candidate evidence from {args.evidence}...")
    result = run_compliance_resolution(
        candidate_evidence_path=args.evidence,
        output_path=args.output,
        model_name=args.model,
        use_ollama=not args.offline_fallback,
    )

    print("\n" + "=" * 60)
    print(" STEP 4 'COMPLIANCE & ANSWER RESOLVER' SUMMARY")
    print("=" * 60)
    print(f" Document ID:            {result['document_id']}")
    print(f" Workbook ID:            {result['workbook_id']}")
    print(f" Total Requirements:     {result['total_requirements']}")
    print(f" Compliant Items:        {result['compliant_count']}")
    print(f" Non-Compliant Items:    {result['non_compliant_count']}")
    print(f" Partially Compliant:    {result['partially_compliant_count']}")
    print(f" Not Specified / Missing:{result['not_specified_count']}")
    print(f" Ambiguous Items:        {result['ambiguous_count']}")
    print(f" Output Artifact:        {args.output}")
    print("=" * 60)


if __name__ == "__main__":
    main()
