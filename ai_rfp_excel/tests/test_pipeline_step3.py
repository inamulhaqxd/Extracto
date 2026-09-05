#!/usr/bin/env python3
"""
Unit tests for Step 3: Simple Hybrid Evidence Retrieval.
Tests:
- step3_indexer: tokenization, paragraph stitching, table row formatting, OCR chunking
- step3_search: technical code extraction, cosine similarity, hybrid matching, anti-hallucination
- step3_retrieve_evidence: end-to-end candidate_evidence.json artifact generation
Strict typing only — zero Any (Rule 4). 100% offline (Rule 10).
"""

from __future__ import annotations

import json
from pathlib import Path

from ai_rfp_excel.app.pipeline.step3_evidence_retriever import (
    run_evidence_retrieval,
)
from ai_rfp_excel.app.pipeline.step3_indexer import (
    DocumentChunk,
    build_document_chunks,
    split_into_paragraphs,
    tokenize,
)
from ai_rfp_excel.app.pipeline.step3_search import (
    cosine_similarity,
    extract_technical_codes,
    matches_code,
    simple_hybrid_search,
)


def test_indexer_tokenize() -> None:
    text = "What is the maximum prefix limit for UpstreamA at EDGE-1 with AS-7018?"
    tokens = tokenize(text)
    assert "maximum" in tokens
    assert "prefix" in tokens
    assert "upstreama" in tokens
    assert "edge-1" in tokens
    assert "as-7018" in tokens


def test_indexer_build_document_chunks_from_pdf() -> None:
    mock_pdf: dict[str, object] = {
        "document_id": "TEST_DOC",
        "pages": [
            {
                "page_number": 1,
                "text": "1. Peering Overview\nThis line is wrapped visually\nin the source PDF document.",
                "tables": [
                    {
                        "table_id": "T01",
                        "headers": ["Peer", "ASN", "Site"],
                        "rows": [["UpstreamA", "AS-7018", "EDGE-1"]],
                    }
                ],
                "ocr": ["Scanned header line on page 1"],
            }
        ],
    }

    chunks = build_document_chunks(mock_pdf)
    assert len(chunks) == 3

    types = {c["source_type"] for c in chunks}
    assert types == {"text", "table", "ocr"}

    # Verify visual line wraps are normalized in text chunks
    text_chunk = next(c for c in chunks if c["source_type"] == "text")
    assert "1. Peering Overview This line is wrapped visually in the source PDF document." in text_chunk["content"]

    # Verify table formatting
    table_chunk = next(c for c in chunks if c["source_type"] == "table")
    assert table_chunk["table_id"] == "T01"
    assert "Table T01 (Row 1) -> Peer: UpstreamA | ASN: AS-7018 | Site: EDGE-1" in table_chunk["content"]


def test_search_extract_technical_codes() -> None:
    text = "Check neighbor 198.51.100.1 with AS-7018 at EDGE-1 setting tag 64500:100 with bandwidth 10 Gbps and DSCP"
    codes = extract_technical_codes(text)
    assert any("as-7018" in c.lower() for c in codes)
    assert "198.51.100.1" in codes
    assert "EDGE-1" in codes
    assert "64500:100" in codes
    assert any("10 gbps" in c.lower() for c in codes)
    assert "DSCP" in codes


def test_search_extract_technical_codes_filters_stopwords() -> None:
    text = "WHAT IS THE MAXIMUM SLA REQUIREMENT AND DOES IT MEET DSCP?"
    codes = extract_technical_codes(text)
    assert "SLA" in codes
    assert "DSCP" in codes
    for forbidden in ["WHAT", "IS", "THE", "AND", "DOES", "IT"]:
        assert forbidden not in codes


def test_search_cosine_similarity() -> None:
    v1 = [1.0, 0.0, 1.0]
    v2 = [1.0, 0.0, 1.0]
    v3 = [0.0, 1.0, 0.0]
    assert cosine_similarity(v1, v2) == 1.0
    assert cosine_similarity(v1, v3) == 0.0
    assert cosine_similarity([], []) == 0.0


def test_search_hybrid_exact_code_matching() -> None:
    chunks: list[DocumentChunk] = [
        {
            "page_number": 1,
            "source_type": "table",
            "content": "Table T01 (Row 1) -> Peer: UpstreamA | ASN: AS-7018 | Max Prefixes: 900,000",
            "table_id": "T01",
            "tokens": ["table", "t01", "row", "1", "peer", "upstreama", "asn", "as-7018", "max", "prefixes", "900000"],
        },
        {
            "page_number": 2,
            "source_type": "text",
            "content": "router bgp 64500 neighbor 198.51.100.1 remote-as 7018 set local-preference 150",
            "table_id": None,
            "tokens": [
                "router", "bgp", "64500", "neighbor", "198.51.100.1", "remote-as",
                "7018", "set", "local-preference", "150",
            ],
        },
    ]

    query = "What is the ASN and Max Prefixes for UpstreamA?"
    results, exact_hits = simple_hybrid_search(
        query=query,
        chunks=chunks,
        top_k=2,
        use_embeddings=False,
    )

    assert len(results) >= 1
    top_chunk, score, hits = results[0]
    assert top_chunk["source_type"] == "table"
    assert "UpstreamA" in top_chunk["content"]
    assert "UpstreamA" in hits
    assert "UpstreamA" in exact_hits
    assert score > 0.0


def test_search_zero_matches_anti_hallucination() -> None:
    """Missing requirement returns empty results to satisfy Rule 7 Zero-Hallucination."""
    chunks: list[DocumentChunk] = [
        {
            "page_number": 1,
            "source_type": "text",
            "content": "BGP configuration details only.",
            "table_id": None,
            "tokens": ["bgp", "configuration", "details"],
        }
    ]

    query = "What is the warranty period on redundant hot-swap power supplies?"
    results, exact_hits = simple_hybrid_search(
        query=query,
        chunks=chunks,
        top_k=2,
        use_embeddings=False,
    )

    assert len(results) == 0
    assert len(exact_hits) == 0


def test_run_evidence_retrieval_end_to_end(tmp_path: Path) -> None:
    mock_pdf = tmp_path / "mock_pdf.json"
    mock_excel = tmp_path / "mock_excel.json"
    output_json = tmp_path / "candidate_evidence.json"

    pdf_content: dict[str, object] = {
        "document_id": "DOC-SAMPLE",
        "pages": [
            {
                "page_number": 1,
                "text": "UpstreamC uses set community 64500:100 additive for routing policy.",
                "tables": [],
                "ocr": [],
            }
        ],
    }
    with open(mock_pdf, "w", encoding="utf-8") as f:
        json.dump(pdf_content, f)

    excel_content: dict[str, object] = {
        "workbook_id": "WB-SAMPLE",
        "sheets": [
            {
                "sheet_name": "Sheet1",
                "requirements": [
                    {
                        "requirement_id": "REQ-01",
                        "sheet_name": "Sheet1",
                        "row_number": 4,
                        "section": "Section 4",
                        "requirement_text": "What community tag is configured for UpstreamC?",
                        "target_slots": {
                            "answer": {
                                "slot_type": "answer",
                                "column_letter": "B",
                                "column_index": 2,
                                "cell_coordinate": "B4",
                                "current_value": None,
                                "has_formula": False,
                                "formula": None,
                            }
                        },
                    }
                ],
            }
        ],
    }
    with open(mock_excel, "w", encoding="utf-8") as f:
        json.dump(excel_content, f)

    result = run_evidence_retrieval(
        pdf_output_path=mock_pdf,
        excel_analysis_path=mock_excel,
        output_path=output_json,
        top_k=2,
        use_embeddings=False,
    )

    assert result["document_id"] == "DOC-SAMPLE"
    assert result["workbook_id"] == "WB-SAMPLE"
    assert result["total_requirements"] == 1
    assert result["requirements_with_evidence"] == 1
    assert len(result["items"]) == 1

    item = result["items"][0]
    assert item["requirement_id"] == "REQ-01"
    assert item["section"] == "Section 4"
    assert len(item["candidate_snippets"]) > 0
    assert "64500:100" in item["candidate_snippets"][0]["snippet"]
    assert output_json.exists()


def test_indexer_split_into_paragraphs_single_newlines() -> None:
    """Ensure single-newline text with section headers is properly chunked into distinct paragraphs."""
    single_newline_text = (
        "BGP Specification Rev 4.1\n"
        "1. Peering Overview\n"
        "This section defines eBGP peering parameters for edge sites.\n"
        "2. Peer Table\n"
        "UpstreamA AS-7018 EDGE-1\n"
        "3. Sample Configuration\n"
        "router bgp 64500 neighbor 198.51.100.1\n"
    )
    paras = split_into_paragraphs(single_newline_text)
    assert len(paras) == 4
    assert any("1. Peering Overview" in p for p in paras)
    assert any("2. Peer Table" in p for p in paras)
    assert any("3. Sample Configuration" in p for p in paras)


def test_search_extract_technical_codes_case_sensitivity() -> None:
    """Ensure regular English words are NOT classified as technical codes while real IDs are."""
    query = "What local-preference value is set for UpstreamA, and does UpstreamC use the same value?"
    codes = extract_technical_codes(query)
    # Real technical codes and PascalCase identifiers
    assert "UpstreamA" in codes
    assert "UpstreamC" in codes
    assert "local-preference" in codes
    # Normal English words must NEVER be extracted as technical codes
    for normal_word in ["value", "set", "use", "local", "preference", "what", "same"]:
        assert normal_word not in codes
        assert normal_word.capitalize() not in codes


def test_search_matches_code_word_boundaries() -> None:
    """Ensure exact code matching does not produce false substring hits."""
    assert matches_code("IP", "Configure IP address 10.0.0.1") is True
    assert matches_code("IP", "General equipment description") is False  # 'ip' in equipment/description
    assert matches_code("AS", "Fast ethernet link") is False  # 'as' in fast
    assert matches_code("99.9%", "System availability is 99.9% measured monthly") is True


def test_search_anti_hallucination_blocks_weak_semantic() -> None:
    """Rule 7: Unanchored chunks with low baseline similarity must be rejected as anti-hallucination."""
    chunks: list[DocumentChunk] = [
        {
            "page_number": 1,
            "source_type": "text",
            "content": "Optical transceivers must be 100G LR4 single-mode fiber with LC connectors.",
            "table_id": None,
            "tokens": ["optical", "transceivers", "100g", "lr4", "single-mode", "fiber", "lc", "connectors"],
        }
    ]
    # Query completely missing from document
    query = "Does the vendor provide ISO 9001 certified data center facilities?"
    results, exact_hits = simple_hybrid_search(
        query=query,
        chunks=chunks,
        top_k=2,
        use_embeddings=False,
    )
    assert len(results) == 0
    assert len(exact_hits) == 0


