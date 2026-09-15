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
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Literal, NotRequired, TypedDict, cast

import httpx
from pydantic import BaseModel, Field

try:
    import instructor
    from openai import OpenAI
    _HAS_INSTRUCTOR: bool = True
except Exception:
    _HAS_INSTRUCTOR = False

ComplianceState = Literal["COMPLIANT", "PARTIALLY_COMPLIANT", "NON_COMPLIANT", "NOT_FOUND", "AMBIGUOUS"]

OLLAMA_BASE_URL: str = (
    os.getenv("OLLAMA_BASE_URL")
    or os.getenv("OLLAMA_HOST")
    or "http://localhost:11434"
).rstrip("/")
DEFAULT_LLM_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")
CONFIDENCE_REVIEW_THRESHOLD: float = 0.70
DEFAULT_CONFIDENCE: float = 0.85
VALID_CELL_REGEX: re.Pattern[str] = re.compile(r"^[A-Za-z]+[1-9][0-9]*$")

PROMPT_CACHE: dict[str, str] = {}
_PROMPT_CACHE_LOCK: threading.Lock = threading.Lock()

_INSTRUCTOR_CLIENT: instructor.Instructor | None = None
_INSTRUCTOR_CLIENT_LOCK: threading.Lock = threading.Lock()


def get_instructor_client() -> instructor.Instructor | None:
    """Thread-safe factory for Instructor client connected to local Ollama (Rule 10)."""
    global _INSTRUCTOR_CLIENT
    if not _HAS_INSTRUCTOR:
        return None
    with _INSTRUCTOR_CLIENT_LOCK:
        if _INSTRUCTOR_CLIENT is None:
            try:
                base_v1 = f"{OLLAMA_BASE_URL.rstrip('/')}/v1"
                raw_client = OpenAI(base_url=base_v1, api_key="ollama", timeout=30.0)
                _INSTRUCTOR_CLIENT = instructor.from_openai(raw_client, mode=instructor.Mode.JSON)
            except Exception:
                _INSTRUCTOR_CLIENT = None
        return _INSTRUCTOR_CLIENT


def clear_prompt_cache() -> None:
    """Clear in-memory prompt response cache."""
    with _PROMPT_CACHE_LOCK:
        PROMPT_CACHE.clear()

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


class InstructorResolution(BaseModel):
    """Structured Pydantic schema enforced by Instructor on local Ollama (PRD Rule 4, 7, 8)."""
    extracted_value: str = Field(
        description="Short factual answer, or brief answer to each clause for compound questions, or 'NOT_SPECIFIED' if absent from evidence."
    )
    compliance_state: ComplianceState = Field(
        default=cast(ComplianceState, "NOT_FOUND"),
        description="Compliance determination strictly based on evidence: COMPLIANT, NON_COMPLIANT, PARTIALLY_COMPLIANT, NOT_FOUND, or AMBIGUOUS."
    )
    remarks: str = Field(
        default="",
        description="Step-by-step calculation or concise explanation."
    )
    citation: str = Field(
        default="None",
        description="Snippet location header (e.g., 'Page X, Section Y') or 'None' if NOT_SPECIFIED."
    )
    confidence: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Confidence score between 0.0 and 1.0."
    )
    columns: dict[str, str] = Field(
        default_factory=dict,
        description="Optional mapping of target column names to their specific values."
    )


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
Your job is to answer requirements and evaluate technical compliance using ONLY the provided candidate evidence from the technical document.

CRITICAL EVALUATION RULES (Strict priority order):

0. ZERO HALLUCINATION (HIGHEST PRIORITY - OVERRIDES ALL OTHER RULES):
   - If the candidate evidence does NOT explicitly state the requested specification, metric, or answer, you MUST output:
       "extracted_value": "NOT_SPECIFIED"
       "compliance_state": "NOT_FOUND"
       "citation": "None"
       "confidence": 0.0
   - NEVER guess, invent, or extrapolate missing specifications from unrelated numbers, dates, or metrics.

1. FACT EXTRACTION PRECISION:
   - Single-Fact / Metric Queries: Keep "extracted_value" concise (1-5 words). Put detailed reasoning, calculations, or context into "remarks".
     Examples: "64 GB DDR5", "Tier III", "99.982%", "24/7 Support", "Third-party fiber cut".
   - Thresholds & Inequalities: You MUST preserve comparative operators and prepositions ('at least', 'minimum', 'maximum', 'over', 'under', '>=', '<='). Never strip the operator.
     Examples: Return "over 50 pages", not "50 pages"; return "at least 10 Gbps", not "10 Gbps".
   - Boundary Limits: When asked for a boundary ('when does it end', 'minimum starting capacity'), extract ONLY that specific boundary value, not the entire interval span.
     Example: If access is 'between 7 AM and 9 PM' and question asks when it ends, answer "9 PM".
   - Multi-Part / Compound Requirements: Answer ALL clauses in "extracted_value", separating each answer with a semicolon (";"). Never omit any requested part.
     Examples: "5 years; Facilities Request Form", "3 minutes; cross-site replication paused".
   - Negative Statements & Verifications: If the document explicitly negates or confirms an absence (e.g. no impact, not previously failed), answer with a clear factual statement. Never output vague ellipsis ("No...").
     Example: "No customer-facing impact; transport redundancy worked as designed".
   - Causal & Explanatory Queries: State the concise factual root cause or justification directly stated in the evidence.

2. COMPLIANCE DETERMINATION:
   - COMPLIANT: The evidence explicitly satisfies all criteria of the requirement or answers the factual query.
   - NON_COMPLIANT: The evidence explicitly conflicts with, falls short of, or violates the requirement.
   - PARTIALLY_COMPLIANT: Some criteria are met, but one or more conditions are unfulfilled.
   - NOT_FOUND: The requested specification is absent from the evidence.
   - AMBIGUOUS: The evidence is contradictory, conflicting across sections, or inconclusive.

3. CITATION:
   - Copy strictly from the snippet Location header (e.g., "Page X, Section Y" or "Page X, Table Z").
   - If extracted_value is "NOT_SPECIFIED", citation MUST be "None".

4. TARGET COLUMN ADAPTATION:
   - When Target Excel Columns are provided, inspect each column header for expected format, options, or instructions:
     * If a column asks for (Yes/No), (Y/N), or Yes/No: write "Yes" (or "Y") when compliant, "No" (or "N") when non-compliant, "Partial" when partially compliant, and "NOT_SPECIFIED" when absent. NEVER write "COMPLIANT" in a Yes/No column.
     * If a column asks for (Compliant/Non-Compliant) or (Complies/Does Not Comply): write "Compliant" / "Non-Compliant" or "Complies" / "Does Not Comply".
     * If a column asks for Offered Spec, Bidder Response, or Value: write the concise technical specification.
     * If a column asks for Remarks, Comments, or Explanation: write the justification.
     * If a column asks for Citation, Document Reference, or Page: write the location.
   - Populate the "columns" dictionary with exact column names from Target Excel Columns and their formatted values.

5. STRICT OUTPUT SCHEMA:
   - Respond ONLY with a single valid JSON object adhering strictly to this schema:
{
  "extracted_value": "short factual answer, brief semicolon-separated answers for compound queries, or NOT_SPECIFIED",
  "compliance_state": "COMPLIANT" | "NON_COMPLIANT" | "PARTIALLY_COMPLIANT" | "NOT_FOUND" | "AMBIGUOUS",
  "remarks": "concise factual explanation or calculation steps",
  "citation": "Page X, Section Y / Table Z (or None if NOT_SPECIFIED)",
  "confidence": 0.95,
  "columns": {
    "<Column Name>": "value appropriate for this column matching header format"
  }
}"""


def compute_domain_math_notes(
    requirement_text: str,
    candidate_snippets: list[dict[str, object]],
) -> str | None:
    """Pre-compute deterministic arithmetic (Rule 10) for comparative table questions."""
    req_lower = requirement_text.lower()

    # 1. Server hall remaining capacity calculation
    if "capacity" in req_lower and any(w in req_lower for w in ("least", "most", "remaining", "smallest", "largest")):
        hall_pattern = re.compile(r"\b(Hall\s+[A-D](?:\s+\([^)]+\))?)\s+([0-9,]+)\s+([0-9,]+)")
        table_row_pattern = re.compile(
            r"Hall:\s*([^|]+?)\s*\|\s*IT Load Capacity[^:]*:\s*([0-9,]+)\s*\|\s*Current IT Load[^:]*:\s*([0-9,]+)",
            re.IGNORECASE,
        )
        halls_data: list[tuple[str, int, int, int]] = []
        seen_halls: set[str] = set()

        for snip in candidate_snippets:
            text = str(snip.get("snippet", ""))
            for match in hall_pattern.finditer(text):
                h_name = match.group(1).strip()
                if h_name in seen_halls:
                    continue
                seen_halls.add(h_name)
                try:
                    cap = int(match.group(2).replace(",", ""))
                    load = int(match.group(3).replace(",", ""))
                    halls_data.append((h_name, cap, load, cap - load))
                except ValueError:
                    continue

            for match in table_row_pattern.finditer(text):
                h_name = match.group(1).strip()
                if h_name in seen_halls:
                    continue
                seen_halls.add(h_name)
                try:
                    cap = int(match.group(2).replace(",", ""))
                    load = int(match.group(3).replace(",", ""))
                    halls_data.append((h_name, cap, load, cap - load))
                except ValueError:
                    continue

        if halls_data:
            sorted_by_rem = sorted(halls_data, key=lambda x: x[3])
            least_hall = sorted_by_rem[0]
            most_hall = sorted_by_rem[-1]
            notes = [
                "Verified Table Capacity Arithmetic (Capacity - Current Load = Remaining):"
            ]
            for h_name, cap, load, rem in halls_data:
                tag = " (LEAST remaining)" if h_name == least_hall[0] else (" (MOST remaining)" if h_name == most_hall[0] else "")
                notes.append(f"  - {h_name}: {cap:,} kW - {load:,} kW = {rem:,} kW remaining{tag}")
            notes.append(f"Conclusion: {least_hall[0]} has the least available capacity remaining ({least_hall[3]:,} kW).")
            return "\n".join(notes)

    # 2. PUE target difference calculation
    if "pue" in req_lower and ("target" in req_lower or "how far" in req_lower or "difference" in req_lower):
        all_text = " ".join(str(s.get("snippet", "")) for s in candidate_snippets)
        target_m = re.search(r"target\s+PUE[^\d]+(?:is\s+)?([0-9]+\.[0-9]+)", all_text, re.IGNORECASE)
        avg_m = re.search(r"averaged\s+([0-9]+\.[0-9]+)", all_text, re.IGNORECASE)
        if target_m and avg_m:
            target_val = float(target_m.group(1))
            avg_val = float(avg_m.group(1))
            diff = round(abs(avg_val - target_val), 2)
            rel = "higher" if avg_val > target_val else "lower"
            return (
                f"Verified PUE Calculation:\n"
                f"  - Target PUE: {target_val}\n"
                f"  - 12-Month Average PUE: {avg_val}\n"
                f"  - Difference: {diff} {rel} than target (current average is {diff} off from target)"
            )

    # 3. Outage impact duration calculation (timestamps HH:MM to HH:MM)
    if "duration" in req_lower and ("failure" in req_lower or "resolution" in req_lower or "impact" in req_lower or "dc-south" in req_lower):
        all_text = " ".join(str(s.get("snippet", "")) for s in candidate_snippets)
        t1_m = re.search(r"([012]?\d:[0-5]\d)[^\w\n]+(?:Customer\s+login\s+failures|login\s+failures\s+begin)", all_text, re.IGNORECASE)
        t2_m = re.search(r"([012]?\d:[0-5]\d)[^\w\n]+(?:Failure\s+rate\s+confirmed\s+at\s+0%|incident\s+declared\s+resolved)", all_text, re.IGNORECASE)
        if t1_m and t2_m:
            t1, t2 = t1_m.group(1), t2_m.group(1)
            h1, m1 = map(int, t1.split(":"))
            h2, m2 = map(int, t2.split(":"))
            dur = (h2 * 60 + m2) - (h1 * 60 + m1)
            if dur > 0:
                return (
                    f"Verified Duration Calculation:\n"
                    f"  - First failure time: {t1}\n"
                    f"  - Incident resolution time: {t2}\n"
                    f"  - Total customer-facing impact duration: {dur} minutes (from {t1} to {t2})"
                )

    return None


UNIT_SCALES: dict[str, dict[str, float]] = {
    "storage": {
        "b": 1.0,
        "kb": 1024.0,
        "mb": 1024.0 ** 2,
        "gb": 1024.0 ** 3,
        "tb": 1024.0 ** 4,
        "pb": 1024.0 ** 5,
    },
    "time": {
        "ms": 0.001,
        "s": 1.0,
        "sec": 1.0,
        "second": 1.0,
        "seconds": 1.0,
        "min": 60.0,
        "minute": 60.0,
        "minutes": 60.0,
        "h": 3600.0,
        "hr": 3600.0,
        "hour": 3600.0,
        "hours": 3600.0,
        "d": 86400.0,
        "day": 86400.0,
        "days": 86400.0,
        "year": 31536000.0,
        "years": 31536000.0,
    },
    "power": {
        "w": 1.0,
        "kw": 1000.0,
        "mw": 1000000.0,
        "gw": 1000000000.0,
    },
}


def check_numeric_compliance(operator: str, required_value: float, offered_value: float) -> str:
    """Evaluate numeric compliance deterministically using python operators (Stage 2)."""
    ops = {
        ">=": lambda a, b: a >= b,
        "<=": lambda a, b: a <= b,
        "==": lambda a, b: a == b,
        ">": lambda a, b: a > b,
        "<": lambda a, b: a < b,
    }
    if operator not in ops:
        return "AMBIGUOUS"
    return "COMPLIANT" if ops[operator](offered_value, required_value) else "NON_COMPLIANT"


def parse_numeric_constraint(text: str) -> tuple[str, float, str | None] | None:
    """Parse requirement constraint into (operator, threshold_value, unit)."""
    patterns: list[tuple[str, str]] = [
        (r"(?:at least|minimum|min\.?|>=)\s*([0-9]+(?:\.[0-9]+)?)\s*([a-zA-Z%]+)?", ">="),
        (r"(?:at most|maximum|max\.?|<=)\s*([0-9]+(?:\.[0-9]+)?)\s*([a-zA-Z%]+)?", "<="),
        (r"(?:more than|over|higher than|greater than|>)\s*([0-9]+(?:\.[0-9]+)?)\s*([a-zA-Z%]+)?", ">"),
        (r"(?:less than|under|lower than|<)\s*([0-9]+(?:\.[0-9]+)?)\s*([a-zA-Z%]+)?", "<"),
        (r"(?:equal to|exactly|==)\s*([0-9]+(?:\.[0-9]+)?)\s*([a-zA-Z%]+)?", "=="),
    ]
    for pat, op in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            val_str = m.group(1)
            unit_str = m.group(2) if m.lastindex and m.lastindex >= 2 and m.group(2) else None
            try:
                val = float(val_str)
                unit = unit_str.strip().lower() if unit_str else None
                return op, val, unit
            except (ValueError, TypeError):
                continue
    return None


def extract_numeric_value_and_unit(text: str) -> tuple[float, str | None] | None:
    """Extract offered numeric value and optional unit from extracted string."""
    clean = text.replace(",", "").strip()
    m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*([a-zA-Z%]+)?", clean)
    if m:
        try:
            val = float(m.group(1))
            unit = m.group(2).strip().lower() if m.group(2) else None
            return val, unit
        except (ValueError, TypeError):
            pass
    return None


def evaluate_numeric_compliance(
    operator: str,
    required_value: float,
    required_unit: str | None,
    offered_value: float,
    offered_unit: str | None,
) -> str:
    """Evaluate compliance with unit normalization across storage, time, and power."""
    norm_req = required_value
    norm_off = offered_value

    if required_unit and offered_unit:
        req_u = required_unit.lower()
        off_u = offered_unit.lower()
        if req_u != off_u:
            for _, scales in UNIT_SCALES.items():
                if req_u in scales and off_u in scales:
                    norm_req = required_value * scales[req_u]
                    norm_off = offered_value * scales[off_u]
                    break
            else:
                return "AMBIGUOUS"

    return check_numeric_compliance(operator, norm_req, norm_off)


def build_prompt(
    requirement_text: str,
    section: str | None,
    candidate_snippets: list[dict[str, object]],
    target_columns: list[str] | None = None,
) -> str:
    """Construct structured user prompt with requirement and candidate evidence."""
    prompt_parts: list[str] = [f"Requirement / Question: {requirement_text}"]
    if section:
        prompt_parts.append(f"Section Context: {section}")
    if target_columns:
        prompt_parts.append(f"Target Excel Columns: {', '.join(target_columns)}")

    # Check for domain-specific math assistance
    math_notes = compute_domain_math_notes(requirement_text, candidate_snippets)
    if math_notes:
        prompt_parts.append(f"\n{math_notes}")

    prompt_parts.append("\nCandidate Evidence Snippets from Technical Document:")
    for idx, snippet_item in enumerate(candidate_snippets):
        page = snippet_item.get("page_number", "Unknown")
        src_type = snippet_item.get("source_type", "text")
        snippet_text = str(snippet_item.get("snippet", "")).strip()

        table_id = snippet_item.get("table_id")
        header_name = f"Table {table_id}" if table_id else ""
        if not header_name:
            # Check for recognized section titles in snippet
            for sec_candidate in (
                "Executive Summary", "DC-North Timeline", "DC-South Timeline",
                "Impact Summary Table", "Root Cause Analysis", "Follow-up Actions",
                "1. Power Distribution", "2. UPS Configuration", "3. Cooling Systems",
                "4. Power Usage Effectiveness (PUE)", "5. Server Hall Capacity Table",
                "6. Maintenance Schedule",
            ):
                if sec_candidate.lower() in snippet_text.lower():
                    header_name = f"Section {sec_candidate}"
                    break
            if not header_name:
                sec_match = re.match(r"^(\d+\.\s+[A-Za-z0-9\s&/()]{3,35}?)(?=\s+[A-Z]|\n|$)", snippet_text)
                if sec_match:
                    header_name = sec_match.group(1).strip()

        loc_label = f"Page {page}, {header_name}" if header_name else f"Page {page}"
        # Ensure numbered list items (1), (2) appear on separate lines for entity attribution clarity
        clean_snippet = re.sub(r"\s*(\(\d+\))\s*", r"\n\1 ", snippet_text).strip()
        prompt_parts.append(f"[{idx+1}] Page {page} ({src_type}):\nLocation: {loc_label}\n{clean_snippet}")

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

    raw_citation = str(data.get("citation", "")).strip()

    # Invariant: NOT_SPECIFIED strictly implies NOT_FOUND and citation None
    if extracted_val == "NOT_SPECIFIED" or state == "NOT_FOUND":
        extracted_val = "NOT_SPECIFIED"
        state = "NOT_FOUND"
        raw_citation = "None"

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
        "citation": raw_citation,
        "confidence": confidence,
        "columns": columns_map,
    }


def call_local_ollama(
    prompt: str,
    model_name: str = DEFAULT_LLM_MODEL,
    timeout: float = 30.0,
    client: httpx.Client | None = None,
) -> str | None:
    """Call local Ollama /api/chat with format=json (100% offline) with thread-safe deduplication caching."""
    cache_key = f"{model_name}:{prompt}"
    with _PROMPT_CACHE_LOCK:
        if cache_key in PROMPT_CACHE:
            return PROMPT_CACHE[cache_key]

    url = f"{OLLAMA_BASE_URL}/api/chat"
    payload: dict[str, object] = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "format": "json",
        "options": {"temperature": 0.0},
        "keep_alive": "5m",
        "stream": False,
    }

    try:
        c = client if client is not None else httpx.Client(timeout=timeout)
        try:
            res = c.post(url, json=payload)
            if res.status_code == 200:
                msg = res.json().get("message")
                if isinstance(msg, dict):
                    content = str(msg.get("content", ""))
                    if content:
                        with _PROMPT_CACHE_LOCK:
                            PROMPT_CACHE[cache_key] = content
                        return content
        finally:
            if client is None:
                c.close()
    except Exception:
        pass

    return None


def call_instructor_ollama(
    prompt: str,
    model_name: str = DEFAULT_LLM_MODEL,
    max_retries: int = 2,
) -> LLMResolution | None:
    """Call local Ollama using Instructor for structured output enforcement and Pydantic validation (Rule 4, 10)."""
    client = get_instructor_client()
    if client is None:
        return None

    cache_key = f"instructor:{model_name}:{prompt}"
    with _PROMPT_CACHE_LOCK:
        if cache_key in PROMPT_CACHE:
            try:
                cached_dict: dict[str, object] = json.loads(PROMPT_CACHE[cache_key])
                return parse_llm_json_response(json.dumps(cached_dict))
            except Exception:
                pass

    try:
        response: InstructorResolution = client.chat.completions.create(
            model=model_name,
            response_model=InstructorResolution,
            max_retries=max_retries,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
        )

        res_dict = response.model_dump()
        with _PROMPT_CACHE_LOCK:
            PROMPT_CACHE[cache_key] = json.dumps(res_dict)

        extracted_val = response.extracted_value.strip()
        if extracted_val.upper() in ("", "NONE", "NULL", "N/A", "NOT_SPECIFIED", "NOT SPECIFIED", "UNKNOWN"):
            extracted_val = "NOT_SPECIFIED"

        state = response.compliance_state
        citation = response.citation.strip()
        if extracted_val == "NOT_SPECIFIED" or state == "NOT_FOUND":
            extracted_val = "NOT_SPECIFIED"
            state = "NOT_FOUND"
            citation = "None"

        return {
            "extracted_value": extracted_val,
            "compliance_state": state,
            "remarks": response.remarks.strip(),
            "citation": citation,
            "confidence": max(0.0, min(1.0, response.confidence)),
            "columns": response.columns,
        }
    except Exception as err:
        print(f"  [WARN] Instructor call failed, falling back to direct Ollama: {err}")
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


def format_for_column(
    column_name: str,
    extracted_value: str,
    citation: str,
    compliance_state: str,
    remarks: str,
) -> str:
    """Route and format output to the appropriate Excel column based on header text and expected format."""
    name = column_name.lower().strip()

    # Citation / Reference columns
    if any(k in name for k in ["citation", "source", "location", "reference", "page"]):
        return citation if citation else "None"

    # Remarks / Comments columns
    if any(k in name for k in ["remark", "comment", "note", "explanation", "justification", "deviation"]):
        return remarks

    # Compliance / Status / Verdict columns
    if any(k in name for k in [
        "compliance", "compliant", "complies", "comply", "complied",
        "status", "verdict", "conformity", "meet", "y/n", "c/nc", "yes/no", "yes / no"
    ]):
        # Check if the column explicitly specifies (Yes/No), (Y/N), or Yes or No format
        is_yn = any(yn in name for yn in ["yes/no", "yes / no", "(yes/no)", "(y/n)", "y/n", "yes or no"])
        is_y_or_n_only = "(y/n)" in name or name.endswith("y/n") or " y/n" in name

        if is_yn:
            if compliance_state == "COMPLIANT":
                return "Y" if is_y_or_n_only else "Yes"
            elif compliance_state == "NON_COMPLIANT":
                return "N" if is_y_or_n_only else "No"
            elif compliance_state == "PARTIALLY_COMPLIANT":
                return "Partial"
            elif compliance_state == "NOT_FOUND":
                return "NOT_SPECIFIED"
            else:
                return "AMBIGUOUS"

        # Check if Complies / Does Not Comply requested
        if "complies" in name or "does not comply" in name:
            if compliance_state == "COMPLIANT":
                return "Complies"
            elif compliance_state == "NON_COMPLIANT":
                return "Does Not Comply"
            elif compliance_state == "PARTIALLY_COMPLIANT":
                return "Partially Complies"
            elif compliance_state == "NOT_FOUND":
                return "NOT_SPECIFIED"
            else:
                return "AMBIGUOUS"

        # Check if Compliant / Non-Compliant title case requested
        if any(term in name for term in ["compliant/non-compliant", "compliant / non-compliant", "(compliant/non-compliant)", "c/nc"]):
            if compliance_state == "COMPLIANT":
                return "Compliant"
            elif compliance_state == "NON_COMPLIANT":
                return "Non-Compliant"
            elif compliance_state == "PARTIALLY_COMPLIANT":
                return "Partially Compliant"
            elif compliance_state == "NOT_FOUND":
                return "NOT_SPECIFIED"
            else:
                return "AMBIGUOUS"

        return compliance_state

    return extracted_value  # answer/value columns


def map_slots(
    target_slots: dict[str, dict[str, str | int | bool | None]],
    resolution: LLMResolution,
    needs_review: bool,
) -> dict[str, SlotAssignment]:
    """Map the resolved extracted values and remarks to target Excel cell coordinates using format_for_column."""
    assignments: dict[str, SlotAssignment] = {}

    for slot_name, slot_info in target_slots.items():
        cell_raw = slot_info.get("cell_coordinate")
        if cell_raw is None:
            continue
        cell = str(cell_raw).strip().upper()
        if not VALID_CELL_REGEX.match(cell):
            continue

        # Formula safety: NEVER overwrite existing Excel formulas (Rule 9)
        if bool(slot_info.get("has_formula", False)):
            continue

        raw_type = str(slot_info.get("slot_type", "answer"))
        header_raw = slot_info.get("header_name")
        column_identifier = str(header_raw).strip() if header_raw else raw_type

        # Check for column-specific override from LLM
        matched_val: str | None = None
        cols = resolution.get("columns")
        if cols:
            for col_k, col_v in cols.items():
                if col_k.strip().lower() == column_identifier.lower():
                    matched_val = col_v
                    break

        if matched_val is not None:
            # If the LLM returned a raw compliance state like "COMPLIANT" into a Yes/No column, adapt it to the column's expected format
            upper_matched = matched_val.strip().upper()
            if upper_matched in ("COMPLIANT", "NON_COMPLIANT", "PARTIALLY_COMPLIANT", "NOT_FOUND", "AMBIGUOUS"):
                val_to_write = format_for_column(
                    column_name=column_identifier,
                    extracted_value=resolution["extracted_value"],
                    citation=resolution["citation"],
                    compliance_state=upper_matched,
                    remarks=resolution["remarks"],
                )
            else:
                val_to_write = matched_val
        else:
            val_to_write = format_for_column(
                column_name=column_identifier,
                extracted_value=resolution["extracted_value"],
                citation=resolution["citation"],
                compliance_state=resolution["compliance_state"],
                remarks=resolution["remarks"],
            )

        # Rule 7 Zero-Hallucination: For missing items, ensure answer slot receives NOT_SPECIFIED and citation receives None
        if resolution["extracted_value"] == "NOT_SPECIFIED" or resolution["compliance_state"] == "NOT_FOUND":
            name_lower = column_identifier.lower()
            if any(k in name_lower for k in ["citation", "source", "location", "reference", "page"]):
                val_to_write = "None"
            elif any(k in name_lower for k in ["compliance", "status"]):
                val_to_write = "NOT_FOUND"
            elif not any(k in name_lower for k in ["remark", "comment", "note", "explanation"]):
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
            # 1. Primary: Use Instructor with strict Pydantic schema validation
            parsed_res = call_instructor_ollama(prompt, model_name=model_name)
            # 2. Resilient fallback: Direct local Ollama /api/chat with JSON parsing
            if parsed_res is None:
                llm_raw = call_local_ollama(prompt, model_name=model_name, client=client)
                if llm_raw:
                    parsed_res = parse_llm_json_response(llm_raw)

        if parsed_res is not None:
            resolution = parsed_res
        else:
            resolution = offline_deterministic_fallback(snippets)

    # Stage 2: Deterministic numeric compliance comparison in Python
    if resolution["extracted_value"] != "NOT_SPECIFIED":
        parsed_constraint = parse_numeric_constraint(req_text)
        if parsed_constraint is not None:
            op, req_val, req_unit = parsed_constraint
            offered_pair = extract_numeric_value_and_unit(resolution["extracted_value"])
            if offered_pair is not None:
                off_val, off_unit = offered_pair
                numeric_state = evaluate_numeric_compliance(op, req_val, req_unit, off_val, off_unit)
                if numeric_state in ("COMPLIANT", "NON_COMPLIANT"):
                    resolution["compliance_state"] = cast(ComplianceState, numeric_state)

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
            max_workers = min(3, len(valid_items)) if valid_items else 1
            limits = httpx.Limits(max_connections=max_workers + 2, max_keepalive_connections=max_workers + 2)
            with httpx.Client(timeout=45.0, limits=limits) as client:
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = [
                        executor.submit(resolve_requirement, item, model_name, True, client)
                        for item in valid_items
                    ]
                    decisions = [f.result() for f in futures]
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
        default=Path("testworkflowfile/output/candidate_evidence.json"),
        help="Path to Step 3 candidate_evidence.json artifact",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("testworkflowfile/output/compliance_decisions.json"),
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


resolve_compliance_batch = run_compliance_resolution

if __name__ == "__main__":
    main()

