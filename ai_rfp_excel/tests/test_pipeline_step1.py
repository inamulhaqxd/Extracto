#!/usr/bin/env python3
"""
Unit tests for Step 1: PRD-Compliant PDF Ingestion and Automated Validation.
Validates adherence to PRD Sections 6, 7, 8, and 12 on reference PDFs.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import ai_rfp_excel.app.pipeline.step1_pdf_extractor as step1_extract_pdf
from ai_rfp_excel.app.pipeline.step1_pdf_extractor import extract_pdf
from ai_rfp_excel.app.pipeline.validate_extraction import validate


@pytest.fixture
def sample_pdf_path() -> Path:
    candidates = [
        Path("data/uploads/sample.pdf"),
        Path("data/sample.pdf"),
        Path("data/uploads/reference.pdf"),
    ]
    for p in candidates:
        if p.exists():
            return p
    pytest.skip("No reference PDF found in data directory.")


def test_prd_section12_document_structure(sample_pdf_path: Path) -> None:
    """Validates top-level fields defined in PRD Section 12."""
    doc = extract_pdf(sample_pdf_path)
    assert "document_id" in doc
    assert "source_file" in doc
    assert "total_pages" in doc
    assert "pages" in doc
    assert doc["total_pages"] > 0
    assert len(doc["pages"]) == doc["total_pages"]


def test_prd_section7_page_text_continuity(sample_pdf_path: Path) -> None:
    """Validates native text preservation and sequential page numbering."""
    doc = extract_pdf(sample_pdf_path)
    for idx, page in enumerate(doc["pages"], start=1):
        assert page["page_number"] == idx
        assert isinstance(page["text"], str)


def test_prd_section8_structured_tables(sample_pdf_path: Path) -> None:
    """Validates structured table fields (table_id, headers, rows) per PRD Section 8."""
    doc = extract_pdf(sample_pdf_path)
    found_table = False
    for page in doc["pages"]:
        for t in page["tables"]:
            found_table = True
            assert "table_id" in t
            assert "headers" in t
            assert "rows" in t
            assert isinstance(t["headers"], list)
            assert isinstance(t["rows"], list)
            assert t["table_id"].startswith("T")
    assert found_table, "Expected at least one table extracted in document."


def test_prd_section12_reserved_fields(sample_pdf_path: Path) -> None:
    """Validates presence of images, ocr, and vision_analysis per PRD Section 12."""
    doc = extract_pdf(sample_pdf_path)
    for p in doc["pages"]:
        assert "images" in p
        assert isinstance(p["images"], list)
        assert "ocr" in p
        assert isinstance(p["ocr"], list)
        assert "vision_analysis" in p
        assert isinstance(p["vision_analysis"], list)


def test_json_roundtrip(sample_pdf_path: Path, tmp_path: Path) -> None:
    doc = extract_pdf(sample_pdf_path)
    json_path = tmp_path / "test_prd_doc.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)

    with open(json_path, "r", encoding="utf-8") as f:
        loaded = json.load(f)

    assert loaded["document_id"] == doc["document_id"]
    assert loaded["total_pages"] == doc["total_pages"]
    assert len(loaded["pages"]) == len(doc["pages"])


def test_automated_validation(sample_pdf_path: Path, tmp_path: Path) -> None:
    """Tests automated health checks, reverse ground truth probing, and report generation."""
    ref_json = Path("ai_rfp_excel/tests/fixtures/reference_pdf_output.json")
    if ref_json.exists():
        json_path = ref_json
    else:
        doc = extract_pdf(sample_pdf_path)
        json_path = tmp_path / "sample_output.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False)

    report = validate(json_path, search_terms=["Outage", "Report", "Network"])
    assert report["total_pages"] > 0
    assert report["total_chars"] > 0
    assert report["corrupted_char_count"] == 0
    assert len(report["table_issues"]) == 0
    assert len(report["probe_results"]) == 3


def test_synonym_and_alternative_probing(sample_pdf_path: Path, tmp_path: Path) -> None:
    """Tests that synonyms and alternative evidence are detected."""
    ref_json = Path("ai_rfp_excel/tests/fixtures/reference_pdf_output.json")
    if not ref_json.exists():
        pytest.skip("reference_pdf_output.json required for synonym probe tests")

    report = validate(ref_json, search_terms=["CPU Load", "Xeon 6710E"])
    assert len(report["probe_results"]) == 2
    res_cpu = next(r for r in report["probe_results"] if r["term"] == "CPU Load")
    assert res_cpu["match_type"] == "SYNONYM"
    assert res_cpu["found"] is True

    res_xeon = next(r for r in report["probe_results"] if r["term"] == "Xeon 6710E")
    assert res_xeon["match_type"] == "ALTERNATIVE_FOUND"
    assert res_xeon["found"] is False  # Rule 7 zero hallucination preserved
    assert "Xeon" in res_xeon["evidence_note"]


def test_scanned_page_ocr_trigger_without_image_objects(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """
    Edge Case: Scanned pages without embedded raster images (images=[])
    must still trigger OCR and promote extracted OCR text to primary text.
    """
    dummy_pdf = tmp_path / "dummy_scan.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4 dummy")

    # Mock OCR availability
    monkeypatch.setattr(step1_extract_pdf, "is_ocr_available", lambda: True)

    # Mock pytesseract.image_to_string
    mock_ocr_output = "SCANNED SPECIFICATION: DUAL REDUNDANT 1200W POWER SUPPLY"
    monkeypatch.setattr(step1_extract_pdf.pytesseract, "image_to_string", lambda img: mock_ocr_output)

    # Mock pdfplumber page
    mock_page = MagicMock()
    mock_page.extract_text.return_value = ""  # No native text
    mock_page.extract_tables.return_value = []
    mock_page.images = []  # No image objects embedded
    mock_page.to_image.return_value.original = MagicMock()

    mock_pdf = MagicMock()
    mock_pdf.pages = [mock_page]
    mock_pdf.__enter__.return_value = mock_pdf

    monkeypatch.setattr(step1_extract_pdf.pdfplumber, "open", lambda p: mock_pdf)

    doc = step1_extract_pdf.extract_pdf(dummy_pdf, enable_ocr=True)
    assert doc["total_pages"] == 1
    page = doc["pages"][0]
    assert mock_ocr_output in page["ocr"]
    assert mock_ocr_output == page["text"]  # Promoted for downstream searchability

