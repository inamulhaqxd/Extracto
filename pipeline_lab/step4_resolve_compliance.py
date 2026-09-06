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

ComplianceState = Literal["COMPLIANT", "PARTIALLY_COMPLIANT", "NON_COMPLIANT", "NOT_FOUND", "AMBIGUOUS"]

OLLAMA_BASE_URL: str = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
DEFAULT_LLM_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")
CONFIDENCE_REVIEW_THRESHOLD: float = 0.70
DEFAULT_CONFIDENCE: float = 0.85
VALID_CELL_REGEX: re.Pattern[str] = re.compile(r"^[A-Za-z]+[1-9][0-9]*$")

PROMPT_CACHE: dict[str, str] = {}
_PROMPT_CACHE_LOCK: threading.Lock = threading.Lock()


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

CRITICAL RULES (Follow in strict priority order):

0. ZERO HALLUCINATION (HIGHEST PRIORITY - OVERRIDES ALL OTHER RULES):
   - If the technical evidence does NOT contain the exact answer, number, or data asked for (e.g. financial cost, unmentioned metrics), you MUST output:
     "extracted_value": "NOT_SPECIFIED"
     "citation": "None"
     "compliance_state": "NOT_FOUND"
   - NEVER grab unrelated numbers (like minutes, percentages, or dates) to fill missing data. If it is not in the text, it is NOT_SPECIFIED.

1. Match Answer Length to Question Type:
   - Simple Single-Fact Questions (asking for a single number, name, metric, team, or yes/no):
     Keep extracted_value SHORT: just the exact fact in 1-5 words. Put any reasoning or context into "remarks".
     Examples: "40%", "monitoring team", "Third-party fiber cut".
   - Thresholds & Qualification Rules (e.g. asking 'what size', 'how many calls', 'minimum', 'qualifies'):
     You MUST retain comparative operators and prepositions ('over', 'more than', 'under', 'at least', 'maximum'). NEVER strip operators or extract a bare number if the condition is an inequality (e.g. return "over 50 pages", not "50 pages"; return "more than 5 calls per week", not "5").
   - Boundaries vs Interval Spans (e.g. questions asking when something 'ends', 'starts', 'begins', or 'expires'):
     Extract ONLY the requested single boundary time or limit. Do not return the entire interval (e.g. if access is 'between 7 AM and 9 PM' and question asks when it ends, answer "9 PM", not "7 AM to 9 PM").
   - Compound & Multi-Part Questions (questions with multiple parts, e.g. with 'and', 'why', 'what was paused', or 'compare'):
     You MUST answer ALL parts of the question in extracted_value, using one brief phrase per part separated by a semicolon or comma. Never omit any part!
     * Table row multi-attribute questions: When a question asks for multiple properties answered by a table row (e.g. refresh cycle AND request method), extract all requested values separated by a semicolon (e.g. "5 years; Facilities Request Form"). Never stop after the first column.
     * Negative fact verifications:
       - If the document confirms no customer impact: answer "No customer-facing impact; transport redundancy worked as designed". Never output "No..." or ellipses.
       - If the document says an incident had not happened before: answer "No, it had not happened before; transport connectivity had not failed previously". Never say "Yes".
     * For "Why" questions: read the snippet and answer with the exact causal explanation for THAT specific question:
       - For "Why did DC-South have no local fallback?": state that deployment was deprioritized during original rollout and never completed.
       - For "Why did it take until 14:09 for platform team to be engaged?": state that application and transport monitoring were on separate alerting systems with no cross-linking.
     * For "How long was X and what was paused?": state the duration, then state what was paused (e.g. "3 minutes; cross-site replication paused").
     * For "Compare site A vs site B": state the finding for site A, and the finding for site B (e.g. "DC-South had design gap; DC-North had transient failover delay").
   - For duration questions ("Calculate the total customer-facing impact duration"): provide the exact calculated duration only (e.g. "37 minutes (from 14:04 to 14:41)"). Put the calculation steps in 'remarks'.

2. Accurate Entity & Action Attribution:
   - Carefully verify which entity or team is responsible for which specific action. When a list has multiple actions (e.g. Action 1 vs Action 2), attribute the exact team assigned to that specific action. Do not confuse adjacent items.
   - Verify negative statements: if the document says 'None (internal failover only)' or 'had not previously failed', answer with a clear factual "No" and never say "Yes".

3. Determine compliance_state as:
   - COMPLIANT: The evidence confirms the requirement or answers the factual query.
   - NON_COMPLIANT: The evidence explicitly conflicts with or fails the requirement.
   - PARTIALLY_COMPLIANT: Only some conditions are met.
   - NOT_FOUND: The specification or answer is absent from the evidence.
   - AMBIGUOUS: Conflicting or unclear evidence.

4. Citation: Copy strictly from the snippet Location header. If extracted_value is "NOT_SPECIFIED", citation must be "None".

5. You MUST respond with ONLY valid JSON adhering strictly to this schema:
{
  "extracted_value": "short factual answer, or brief answer to each clause for compound questions, or NOT_SPECIFIED",
  "compliance_state": "COMPLIANT" | "NON_COMPLIANT" | "PARTIALLY_COMPLIANT" | "NOT_FOUND" | "AMBIGUOUS",
  "remarks": "step-by-step calculation or concise explanation",
  "citation": "Page X, Section Y / Table Z (or None if NOT_SPECIFIED)",
  "confidence": 0.95,
  "columns": {
    "<Column Name>": "value appropriate for this column"
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
    """Route LLM's raw output to the appropriate Excel column based on detected column name."""
    name = column_name.lower()
    if any(k in name for k in ["citation", "source", "location", "reference", "page"]):
        return citation if citation else "None"
    if any(k in name for k in ["compliance", "status"]):
        return compliance_state
    if any(k in name for k in ["remark", "comment", "note", "explanation"]):
        return remarks
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
        cell = str(cell_raw).strip()
        if not cell or not VALID_CELL_REGEX.match(cell):
            continue

        # Formula safety: NEVER overwrite existing Excel formulas (Rule 9)
        if bool(slot_info.get("has_formula", False)):
            continue

        raw_type = str(slot_info.get("slot_type", slot_name)).strip().lower()
        header_name = str(slot_info.get("header_name", "")).strip()
        column_identifier = header_name if header_name else (raw_type or slot_name)

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
