#!/usr/bin/env python3
"""
Unit tests for Step 4: "The Compliance & Answer Resolver".
Tests:
- Rule 7 Zero-Hallucination: empty evidence produces NOT_SPECIFIED.
- Fallback zero-hallucination on offline execution.
- Structured prompt formatting.
- Strict LLM JSON response parsing and normalization (null values, hyphenated states).
- Target slot mapping, formula preservation, coordinate validation, and slot aliases.
- Low-confidence and ambiguous needs_review propagation to slots.
- End-to-end execution writing compliance_decisions.json.

Strict typing only — zero Any (Rule 4). 100% offline (Rule 10).
"""

from __future__ import annotations

import json
from pathlib import Path

from ai_rfp_excel.app.pipeline.step4_compliance_resolver import (
    DEFAULT_LLM_MODEL,
    PROMPT_CACHE,
    LLMResolution,
    build_prompt,
    call_local_ollama,
    check_numeric_compliance,
    clear_prompt_cache,
    evaluate_numeric_compliance,
    extract_numeric_value_and_unit,
    format_for_column,
    map_slots,
    offline_deterministic_fallback,
    parse_llm_json_response,
    parse_numeric_constraint,
    resolve_requirement,
    run_compliance_resolution,
)


def test_empty_evidence_produces_not_specified() -> None:
    """Rule 7: Requirements with no candidate evidence MUST yield NOT_SPECIFIED with zero hallucination."""
    req: dict[str, object] = {
        "requirement_id": "REQ-TEST-01",
        "sheet_name": "Sheet1",
        "row_number": 5,
        "section": "General",
        "requirement_text": "What is the warranty period for power supplies?",
        "candidate_snippets": [],
        "target_slots": {
            "answer": {
                "slot_type": "answer",
                "cell_coordinate": "B5",
                "has_formula": False,
            }
        },
    }

    decision = resolve_requirement(req, use_ollama=False)
    assert decision["extracted_value"] == "NOT_SPECIFIED"
    assert decision["compliance_state"] == "NOT_FOUND"
    assert decision["confidence"] == 0.0
    assert decision["needs_review"] is True
    assert decision["slot_assignments"]["answer"]["value"] == "NOT_SPECIFIED"
    assert decision["slot_assignments"]["answer"]["needs_review"] is True


def test_whitespace_only_snippets_treated_as_missing() -> None:
    """Rule 7: Candidate snippets with only whitespace MUST be treated as missing evidence."""
    req: dict[str, object] = {
        "requirement_id": "REQ-TEST-BLANK",
        "sheet_name": "Sheet1",
        "row_number": 6,
        "section": "General",
        "requirement_text": "Is dual power supply supported?",
        "candidate_snippets": [
            {"page_number": 1, "snippet": "   \n\t  "},
            {"page_number": 2, "snippet": ""},
        ],
        "target_slots": {
            "answer": {
                "slot_type": "answer",
                "cell_coordinate": "B6",
                "has_formula": False,
            }
        },
    }

    decision = resolve_requirement(req, use_ollama=False)
    assert decision["extracted_value"] == "NOT_SPECIFIED"
    assert decision["compliance_state"] == "NOT_FOUND"
    assert decision["confidence"] == 0.0
    assert decision["needs_review"] is True


def test_fallback_zero_hallucination_universal() -> None:
    """Rule 7: Fallback must NOT guess or invent data, always returning NOT_SPECIFIED."""
    snippets: list[dict[str, object]] = [
        {
            "page_number": 1,
            "snippet": "General Company Information. This document outlines general guidelines for facilities.",
        }
    ]

    res = offline_deterministic_fallback(snippets)
    assert res["extracted_value"] == "NOT_SPECIFIED"
    assert res["compliance_state"] == "NOT_FOUND"
    assert res["confidence"] == 0.0
    assert "Page 1" in res["citation"]


def test_build_prompt_structure() -> None:
    req_text = "What is the warranty period for hardware modules?"
    section = "Warranty Policy"
    snippets: list[dict[str, object]] = [
        {
            "page_number": 2,
            "source_type": "text",
            "snippet": "All chassis modules carry a 3-year standard manufacturer warranty.",
        }
    ]

    prompt = build_prompt(req_text, section, snippets)
    assert "What is the warranty period for hardware modules?" in prompt
    assert "Section Context: Warranty Policy" in prompt
    assert "[1] Page 2 (text):" in prompt
    assert "3-year standard manufacturer warranty" in prompt


def test_parse_llm_json_response_valid() -> None:
    raw = json.dumps({
        "extracted_value": "3 Years",
        "compliance_state": "COMPLIANT",
        "remarks": "3-year standard manufacturer warranty explicitly documented.",
        "citation": "Page 2, Section 4.1",
        "confidence": 0.98,
    })

    res = parse_llm_json_response(raw)
    assert res["extracted_value"] == "3 Years"
    assert res["compliance_state"] == "COMPLIANT"
    assert res["remarks"] == "3-year standard manufacturer warranty explicitly documented."
    assert res["citation"] == "Page 2, Section 4.1"
    assert res["confidence"] == 0.98


def test_parse_llm_json_response_with_markdown_fences() -> None:
    raw = (
        "Here is the compliance result:\n"
        "```json\n"
        "{\n"
        '  "extracted_value": "30%",\n'
        '  "compliance_state": "COMPLIANT",\n'
        '  "remarks": "Business-Critical traffic is allocated 30% bandwidth.",\n'
        '  "citation": "Page 2, QoS Policy",\n'
        '  "confidence": 0.95\n'
        "}\n"
        "```"
    )

    res = parse_llm_json_response(raw)
    assert res["extracted_value"] == "30%"
    assert res["compliance_state"] == "COMPLIANT"
    assert res["confidence"] == 0.95


def test_parse_llm_json_response_normalizes_null_and_hyphens() -> None:
    # Test null converted to NOT_SPECIFIED
    raw_null = json.dumps({
        "extracted_value": None,
        "compliance_state": "NON-COMPLIANT",
        "remarks": "Missing value",
        "citation": "Page 3",
        "confidence": 0.80,
    })
    res_null = parse_llm_json_response(raw_null)
    assert res_null["extracted_value"] == "NOT_SPECIFIED"
    assert res_null["compliance_state"] == "NOT_FOUND"

    # Test hyphenated and spaced compliance states
    raw_states = json.dumps({
        "extracted_value": "No support",
        "compliance_state": "NON-COMPLIANT",
        "remarks": "Does not support requested protocol",
        "citation": "Page 4",
        "confidence": 0.90,
    })
    res_non = parse_llm_json_response(raw_states)
    assert res_non["compliance_state"] == "NON_COMPLIANT"

    raw_partial = json.dumps({
        "extracted_value": "Only 10G supported",
        "compliance_state": "PARTIALLY COMPLIANT",
        "remarks": "Partial compliance",
        "citation": "Page 4",
        "confidence": 0.85,
    })
    res_part = parse_llm_json_response(raw_partial)
    assert res_part["compliance_state"] == "PARTIALLY_COMPLIANT"


def test_parse_llm_json_response_corrupt_fallback() -> None:
    raw = "I am an AI that cannot answer this in JSON format."
    res = parse_llm_json_response(raw)
    assert res["extracted_value"] == "NOT_SPECIFIED"
    assert res["compliance_state"] == "AMBIGUOUS"
    assert res["confidence"] <= 0.50


def test_map_slots_preserves_formulas_and_maps_aliases() -> None:
    target_slots: dict[str, dict[str, str | int | bool | None]] = {
        "vendor_resp": {
            "slot_type": "vendor_response",
            "cell_coordinate": "B4",
            "has_formula": False,
        },
        "notes": {
            "slot_type": "notes",
            "cell_coordinate": "C4",
            "has_formula": False,
        },
        "status_slot": {
            "slot_type": "status",
            "cell_coordinate": "D4",
            "has_formula": False,
        },
        "formula_slot": {
            "slot_type": "calculated",
            "cell_coordinate": "E4",
            "has_formula": True,  # Protected formula
            "formula": "=SUM(A4:C4)",
        },
        "invalid_cell_slot": {
            "slot_type": "remarks",
            "cell_coordinate": "INVALID_COORD",
            "has_formula": False,
        },
    }

    resolution: LLMResolution = {
        "extracted_value": "Model X-500",
        "compliance_state": "COMPLIANT",
        "remarks": "Specified in technical catalog.",
        "citation": "Page 1",
        "confidence": 0.96,
    }

    assignments = map_slots(target_slots, resolution, needs_review=False)
    assert "vendor_resp" in assignments
    assert assignments["vendor_resp"]["cell_coordinate"] == "B4"
    assert assignments["vendor_resp"]["value"] == "Model X-500"

    assert "notes" in assignments
    assert assignments["notes"]["cell_coordinate"] == "C4"
    assert "Specified in technical catalog." in str(assignments["notes"]["value"])

    assert "status_slot" in assignments
    assert assignments["status_slot"]["value"] == "COMPLIANT"

    # Formula cell MUST NEVER be in assignments to protect workbook integrity
    assert "formula_slot" not in assignments

    # Invalid coordinate MUST NOT be assigned
    assert "invalid_cell_slot" not in assignments


def test_map_slots_propagates_needs_review() -> None:
    target_slots: dict[str, dict[str, str | int | bool | None]] = {
        "answer": {
            "slot_type": "answer",
            "cell_coordinate": "B10",
            "has_formula": False,
        }
    }

    resolution: LLMResolution = {
        "extracted_value": "Ambiguous value",
        "compliance_state": "AMBIGUOUS",
        "remarks": "Uncertain matching",
        "citation": "Page 1",
        "confidence": 0.50,
    }

    assignments = map_slots(target_slots, resolution, needs_review=True)
    assert assignments["answer"]["needs_review"] is True


def test_run_compliance_resolution_end_to_end(tmp_path: Path) -> None:
    evidence_path = tmp_path / "mock_candidate_evidence.json"
    output_path = tmp_path / "compliance_decisions.json"

    evidence_data: dict[str, object] = {
        "document_id": "TEST_DOC_4",
        "workbook_id": "TEST_WB_4",
        "total_requirements": 2,
        "items": [
            {
                "requirement_id": "REQ-01",
                "sheet_name": "Sheet1",
                "row_number": 4,
                "section": "General",
                "requirement_text": "What is the warranty period?",
                "target_slots": {
                    "answer": {
                        "slot_type": "answer",
                        "cell_coordinate": "B4",
                        "has_formula": False,
                    }
                },
                "candidate_snippets": [
                    {
                        "page_number": 1,
                        "source_type": "text",
                        "snippet": "Warranty: Standard 3 years full coverage on parts and labor.",
                    }
                ],
            },
            {
                "requirement_id": "REQ-02",
                "sheet_name": "Sheet1",
                "row_number": 5,
                "section": "Certification",
                "requirement_text": "Is ISO 9001 certification provided?",
                "target_slots": {
                    "answer": {
                        "slot_type": "answer",
                        "cell_coordinate": "B5",
                        "has_formula": False,
                    }
                },
                "candidate_snippets": [],  # Missing evidence
            },
        ],
    }

    with open(evidence_path, "w", encoding="utf-8") as f:
        json.dump(evidence_data, f)

    # In offline fallback mode, all unverified items strictly output NOT_SPECIFIED (Rule 7)
    result = run_compliance_resolution(
        candidate_evidence_path=evidence_path,
        output_path=output_path,
        use_ollama=False,
    )

    assert result["document_id"] == "TEST_DOC_4"
    assert result["total_requirements"] == 2
    assert result["not_specified_count"] == 2

    for item in result["items"]:
        assert item["extracted_value"] == "NOT_SPECIFIED"
        assert item["compliance_state"] == "NOT_FOUND"
        assert item["needs_review"] is True

    assert output_path.exists()


def test_map_slots_with_ai_columns_and_clean_source_citation() -> None:
    """Test AI column mapping where Source Section receives only exact citation, not remarks sentence."""
    target_slots: dict[str, dict[str, str | int | bool | None]] = {
        "answer": {
            "slot_type": "answer",
            "header_name": "AI Answer",
            "cell_coordinate": "B4",
            "has_formula": False,
        },
        "source": {
            "slot_type": "remarks",
            "header_name": "Source Section",
            "cell_coordinate": "C4",
            "has_formula": False,
        },
    }

    # Case A: AI provided specific column dictionary
    resolution_a: LLMResolution = {
        "extracted_value": "16 GB",
        "compliance_state": "COMPLIANT",
        "remarks": "The standard issue desktop computer has 16 GB of RAM.",
        "citation": "Page 1, Table T02-01",
        "confidence": 0.98,
        "columns": {
            "AI Answer": "16 GB",
            "Source Section": "Page 1, Table T02-01",
        },
    }
    assignments_a = map_slots(target_slots, resolution_a, needs_review=False)
    assert assignments_a["answer"]["value"] == "16 GB"
    assert assignments_a["source"]["value"] == "Page 1, Table T02-01"

    # Case B: AI didn't provide columns dictionary; smart fallback detects "Source Section"
    resolution_b: LLMResolution = {
        "extracted_value": "16 GB",
        "compliance_state": "COMPLIANT",
        "remarks": "The standard issue desktop computer has 16 GB of RAM.",
        "citation": "Page 1, Table T02-01",
        "confidence": 0.98,
        "columns": {},
    }
    assignments_b = map_slots(target_slots, resolution_b, needs_review=False)
    assert assignments_b["answer"]["value"] == "16 GB"
    assert assignments_b["source"]["value"] == "Page 1, Table T02-01"


def test_prompt_caching_deduplication() -> None:
    """Verify that duplicate prompts are served directly from PROMPT_CACHE without redundant calls."""
    clear_prompt_cache()
    prompt = "Test prompt for duplication verification"
    cached_content = '{"extracted_value": "100 TB", "compliance_state": "COMPLIANT", "remarks": "Cached", "citation": "Page 1"}'

    cache_key = f"{DEFAULT_LLM_MODEL}:{prompt}"
    PROMPT_CACHE[cache_key] = cached_content

    # Should hit cache immediately and return cached JSON without needing network/Ollama
    result = call_local_ollama(prompt, model_name=DEFAULT_LLM_MODEL)
    assert result == cached_content

    parsed = parse_llm_json_response(result)
    assert parsed["extracted_value"] == "100 TB"
    assert parsed["compliance_state"] == "COMPLIANT"
    clear_prompt_cache()


def test_format_for_column() -> None:
    """Verify deterministic column routing in Python (Stage 1)."""
    val = "16 GB"
    cit = "Page 2, Table 1"
    comp = "COMPLIANT"
    rem = "Supported by default configuration."

    assert format_for_column("AI Answer", val, cit, comp, rem) == "16 GB"
    assert format_for_column("Specification", val, cit, comp, rem) == "16 GB"
    assert format_for_column("Vendor Response", val, cit, comp, rem) == "16 GB"

    assert format_for_column("Source Section", val, cit, comp, rem) == "Page 2, Table 1"
    assert format_for_column("Citation", val, cit, comp, rem) == "Page 2, Table 1"
    assert format_for_column("Page Reference", val, cit, comp, rem) == "Page 2, Table 1"

    assert format_for_column("Compliance Status", val, cit, comp, rem) == "COMPLIANT"
    assert format_for_column("Status", val, cit, comp, rem) == "COMPLIANT"

    assert format_for_column("Remarks", val, cit, comp, rem) == "Supported by default configuration."
    assert format_for_column("Notes", val, cit, comp, rem) == "Supported by default configuration."
    assert format_for_column("Explanation", val, cit, comp, rem) == "Supported by default configuration."


def test_check_numeric_compliance() -> None:
    """Verify raw numeric operator comparison logic (Stage 2)."""
    assert check_numeric_compliance(">=", 16.0, 16.0) == "COMPLIANT"
    assert check_numeric_compliance(">=", 16.0, 32.0) == "COMPLIANT"
    assert check_numeric_compliance(">=", 16.0, 8.0) == "NON_COMPLIANT"

    assert check_numeric_compliance("<=", 50.0, 45.0) == "COMPLIANT"
    assert check_numeric_compliance("<=", 50.0, 55.0) == "NON_COMPLIANT"

    assert check_numeric_compliance(">", 32.0, 64.0) == "COMPLIANT"
    assert check_numeric_compliance(">", 32.0, 32.0) == "NON_COMPLIANT"

    assert check_numeric_compliance("<", 10.0, 5.0) == "COMPLIANT"
    assert check_numeric_compliance("<", 10.0, 15.0) == "NON_COMPLIANT"

    assert check_numeric_compliance("==", 4.0, 4.0) == "COMPLIANT"
    assert check_numeric_compliance("==", 4.0, 5.0) == "NON_COMPLIANT"

    assert check_numeric_compliance("INVALID_OP", 1.0, 1.0) == "AMBIGUOUS"


def test_parse_numeric_constraint() -> None:
    """Verify regex extraction of operator, threshold value, and unit from requirements (Stage 2)."""
    # At least / Minimum
    res1 = parse_numeric_constraint("Should provide at least 350 TB RAW capacity of SAN")
    assert res1 == (">=", 350.0, "tb")

    res2 = parse_numeric_constraint("Minimum 16 GB memory per blade")
    assert res2 == (">=", 16.0, "gb")

    res3 = parse_numeric_constraint("Chassis must support >= 4 power supplies")
    assert res3 == (">=", 4.0, "power")

    # Higher than / More than
    res4 = parse_numeric_constraint("Higher than 32 cores per controller")
    assert res4 == (">", 32.0, "cores")

    res5 = parse_numeric_constraint("Over 50 pages required")
    assert res5 == (">", 50.0, "pages")

    # Maximum / At most / Under
    res6 = parse_numeric_constraint("Latency under 50 ms")
    assert res6 == ("<", 50.0, "ms")

    res7 = parse_numeric_constraint("Maximum 1.5 PUE target")
    assert res7 == ("<=", 1.5, "pue")

    # Qualitative requirements must return None (correctly classified as qualitative)
    assert parse_numeric_constraint("What model of smartphone is issued to new employees?") is None
    assert parse_numeric_constraint("What is the primary UPS topology?") is None
    assert parse_numeric_constraint("Why does Hall D follow a different inspection schedule?") is None


def test_evaluate_numeric_compliance_with_units() -> None:
    """Verify unit-aware normalization across data storage, time, and power (Stage 2)."""
    # Storage unit conversion: 1 TB required vs 2048 GB offered -> COMPLIANT
    assert evaluate_numeric_compliance(">=", 1.0, "tb", 2048.0, "gb") == "COMPLIANT"
    # Storage unit conversion: 1 TB required vs 500 GB offered -> NON_COMPLIANT
    assert evaluate_numeric_compliance(">=", 1.0, "tb", 500.0, "gb") == "NON_COMPLIANT"

    # Time unit conversion: 1 minute required vs 45 seconds offered with <= operator -> COMPLIANT
    assert evaluate_numeric_compliance("<=", 1.0, "minute", 45.0, "seconds") == "COMPLIANT"
    assert evaluate_numeric_compliance("<=", 1.0, "minute", 90.0, "seconds") == "NON_COMPLIANT"

    # Incompatible units
    assert evaluate_numeric_compliance(">=", 10.0, "gb", 10.0, "seconds") == "AMBIGUOUS"


def test_numeric_compliance_integration_in_resolve() -> None:
    """Verify that resolve_requirement correctly updates compliance_state for numeric constraints."""
    req: dict[str, object] = {
        "requirement_id": "REQ-NUM-01",
        "sheet_name": "Sheet1",
        "row_number": 10,
        "section": "Compute",
        "requirement_text": "Should provide at least 32 GB RAM per compute node",
        "candidate_snippets": [
            {
                "page_number": 1,
                "source_type": "text",
                "snippet": "Compute nodes are populated with 64 GB DDR5 RAM.",
            }
        ],
        "target_slots": {
            "status": {
                "slot_type": "compliance",
                "cell_coordinate": "C10",
                "has_formula": False,
            }
        },
    }

    # Even in offline deterministic fallback, if LLM is offline, extracted_value is NOT_SPECIFIED so state remains NOT_FOUND
    fallback_dec = resolve_requirement(req, use_ollama=False)
    assert fallback_dec["compliance_state"] == "NOT_FOUND"

    # When raw value is extracted as 64 GB:
    extracted_val = "64 GB"
    pair = extract_numeric_value_and_unit(extracted_val)
    assert pair is not None
    assert pair == (64.0, "gb")

    parsed = parse_numeric_constraint("Should provide at least 32 GB RAM per compute node")
    assert parsed is not None
    op, req_v, req_u = parsed
    off_v, off_u = pair
    assert evaluate_numeric_compliance(op, req_v, req_u, off_v, off_u) == "COMPLIANT"





