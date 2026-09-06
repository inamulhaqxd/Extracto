#!/usr/bin/env python3
"""
Unit tests for Step 2: Dynamic Excel Workbook & Requirement Analyzer.
Tests PRD Sections 16, 17, 18, 19 adherence:
- Dynamic header detection
- Multi-level composite sub-headers
- Merged cell resolution
- Section hierarchy & requirement extraction
- Target fillable slots mapping
- Zero Any typing compliance
"""

from pathlib import Path

import openpyxl
import pytest

try:
    from pipeline_lab.step2_parse_excel import (
        classify_column_header,
        detect_headers,
        export_questions_list,
        get_merged_cell_value,
        parse_excel_workbook,
    )
except ModuleNotFoundError:
    from step2_parse_excel import (  # type: ignore[no-redef]
        classify_column_header,
        detect_headers,
        export_questions_list,
        get_merged_cell_value,
        parse_excel_workbook,
    )


@pytest.fixture
def sample_rfp_excel(tmp_path: Path) -> Path:
    """Generates a realistic RFP Excel workbook with sections, merged cells, and composite subheaders."""
    excel_path = tmp_path / "test_rfp_spec.xlsx"
    wb = openpyxl.Workbook()

    # Sheet 1: Server Requirements (Multi-level headers)
    ws1 = wb.active
    ws1.title = "Server Specs"

    # Row 1: Document title banner
    ws1.merge_cells("A1:E1")
    ws1["A1"] = "SECTION 3: TECHNICAL SERVER SPECIFICATIONS"

    # Row 2: Header Level 1
    ws1["A2"] = "S.No"
    ws1["B2"] = "Technical Requirement"
    ws1.merge_cells("C2:E2")
    ws1["C2"] = "Bidder Evaluation (Techaccess)"

    # Row 3: Subheader Level 2
    ws1["A3"] = "#"
    ws1["B3"] = "Specification Details"
    ws1["C3"] = "Compliance (Yes/No)"
    ws1["D3"] = "Marks Obtained"
    ws1["E3"] = "Remarks & Evidence"

    # Row 4: Section Banner
    ws1.merge_cells("A4:E4")
    ws1["A4"] = "3.1 Compute & Processor Specifications"

    # Row 5: Requirement 1
    ws1["A5"] = 1
    ws1["B5"] = "Dual Intel Xeon 6th Gen Scalable Processors (48-Core min)"
    ws1["C5"] = None  # Empty slot to be filled
    ws1["D5"] = None  # Empty slot to be filled
    ws1["E5"] = None  # Empty slot to be filled

    # Row 6: Requirement 2
    ws1["A6"] = 2
    ws1["B6"] = "Minimum 512GB DDR5 Registered ECC Memory (16x32GB)"
    ws1["C6"] = None
    ws1["D6"] = None
    ws1["E6"] = None

    # Row 7: Section Banner
    ws1.merge_cells("A7:E7")
    ws1["A7"] = "3.2 Storage & Controller"

    # Row 8: Requirement 3
    ws1["A8"] = 3
    ws1["B8"] = "All-Flash Storage delivering 350 TB RAW Capacity with NVMe SSDs"
    ws1["C8"] = None
    ws1["D8"] = None
    ws1["E8"] = None

    # Sheet 2: Simple Flat Requirements
    ws2 = wb.create_sheet("Network Specs")
    ws2["A1"] = "Item No"
    ws2["B1"] = "Requirement Description"
    ws2["C1"] = "Complied / Not Complied"
    ws2["D1"] = "Bidder Notes"

    ws2["A2"] = 1
    ws2["B2"] = "8x 32G Fibre Channel Host Ports"
    ws2["C2"] = None
    ws2["D2"] = None

    wb.save(excel_path)
    wb.close()
    return excel_path


def test_classify_column_header() -> None:
    """Validates classification of various industry column headers."""
    assert classify_column_header("S.No") == "index"
    assert classify_column_header("Sr No") == "index"
    assert classify_column_header("Technical Requirement") == "requirement"
    assert classify_column_header("Specification Details") == "requirement"
    assert classify_column_header("Compliance (Yes/No)") == "compliance"
    assert classify_column_header("Complied / Not Complied") == "compliance"
    assert classify_column_header("Total Marks") == "total_marks"
    assert classify_column_header("Marks Obtained") == "marks"
    assert classify_column_header("Remarks & Evidence") == "remarks"
    assert classify_column_header("Offered Specification") == "answer"


def test_merged_cell_resolution(sample_rfp_excel: Path) -> None:
    """Ensures get_merged_cell_value retrieves master cell value across merged spans."""
    wb = openpyxl.load_workbook(sample_rfp_excel, data_only=False)
    ws = wb["Server Specs"]

    # In A1:E1, cells B1..E1 should resolve to A1's value
    assert get_merged_cell_value(ws, 1, 1) == "SECTION 3: TECHNICAL SERVER SPECIFICATIONS"
    assert get_merged_cell_value(ws, 1, 3) == "SECTION 3: TECHNICAL SERVER SPECIFICATIONS"
    assert get_merged_cell_value(ws, 1, 5) == "SECTION 3: TECHNICAL SERVER SPECIFICATIONS"

    wb.close()


def test_detect_multi_level_headers(sample_rfp_excel: Path) -> None:
    """Validates composite header resolution for multi-level tables."""
    wb = openpyxl.load_workbook(sample_rfp_excel, data_only=False)
    ws = wb["Server Specs"]

    header_row, data_start, headers = detect_headers(ws)
    assert header_row == 2
    assert data_start == 4  # Row 2 (main) + Row 3 (sub) -> Data starts at row 4
    assert "S.No" in headers[1]
    assert "Requirement" in headers[2]
    assert "Compliance" in headers[3]
    assert "Marks" in headers[4]
    assert "Remarks" in headers[5]

    wb.close()


def test_parse_excel_workbook(sample_rfp_excel: Path) -> None:
    """Validates complete WorkbookAnalysis extraction and slot mapping."""
    analysis = parse_excel_workbook(sample_rfp_excel)

    assert analysis["workbook_id"] == "test_rfp_spec"
    assert len(analysis["sheets"]) == 2
    assert analysis["total_requirements"] == 4  # 3 in Sheet 1, 1 in Sheet 2

    # Verify Sheet 1
    s1 = analysis["sheets"][0]
    assert s1["sheet_name"] == "Server Specs"
    assert len(s1["requirements"]) == 3

    # Check Requirement 1
    req1 = s1["requirements"][0]
    assert req1["requirement_id"] == "REQ-S01-R001"
    assert "Intel Xeon" in req1["requirement_text"]
    assert req1["row_number"] == 5
    assert req1["source_cell"] == "B5"
    assert req1["section"] == "3.1 Compute & Processor Specifications"

    # Verify Target Slots
    slots = req1["target_slots"]
    assert "compliance" in slots
    assert slots["compliance"]["cell_coordinate"] == "C5"
    assert "marks" in slots
    assert slots["marks"]["cell_coordinate"] == "D5"
    assert "remarks" in slots
    assert slots["remarks"]["cell_coordinate"] == "E5"

    # Check Requirement 3 (Section change)
    req3 = s1["requirements"][2]
    assert req3["section"] == "3.2 Storage & Controller"
    assert "350 TB" in req3["requirement_text"]

    # Verify Sheet 2
    s2 = analysis["sheets"][1]
    assert s2["sheet_name"] == "Network Specs"
    assert len(s2["requirements"]) == 1
    assert "Fibre Channel" in s2["requirements"][0]["requirement_text"]


def test_export_questions_list(sample_rfp_excel: Path) -> None:
    """Validates export of flattened question/requirement list for reverse probing."""
    analysis = parse_excel_workbook(sample_rfp_excel)
    questions = export_questions_list(analysis)

    assert len(questions) == 4
    texts = [q["requirement_text"] for q in questions]
    assert any("Xeon" in t for t in texts)
    assert any("512GB" in t for t in texts)
    assert any("350 TB" in t for t in texts)
    assert any("Fibre Channel" in t for t in texts)


def test_numbered_requirement_not_discarded_as_section_banner(tmp_path: Path) -> None:
    """
    Edge Case: Unfilled row with numbered specification (e.g. '1.1 Server must support 64GB')
    must NOT be misclassified as a Section Banner and discarded.
    """
    excel_path = tmp_path / "numbered_req.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Specs"

    # Header Row
    ws["A1"] = "Item"
    ws["B1"] = "Specification Details"
    ws["C1"] = "Compliance (Yes/No)"
    ws["D1"] = "Remarks"

    # Row 2: Numbered requirement in Col B with empty slots in C & D
    ws["A2"] = None
    ws["B2"] = "1.1 Server must support redundant hot-swap power supplies"
    ws["C2"] = None
    ws["D2"] = None

    # Row 3: Standard requirement
    ws["A3"] = "1.2"
    ws["B3"] = "2x 10GbE SFP+ Network Interface Ports"
    ws["C3"] = None
    ws["D3"] = None

    wb.save(excel_path)
    wb.close()

    analysis = parse_excel_workbook(excel_path)
    assert analysis["total_requirements"] == 2
    req_texts = [r["requirement_text"] for r in analysis["sheets"][0]["requirements"]]
    assert "1.1 Server must support redundant hot-swap power supplies" in req_texts
    assert "2x 10GbE SFP+ Network Interface Ports" in req_texts


def test_deep_header_row_detection(tmp_path: Path) -> None:
    """
    Edge Case: Tender instructions pushing the header row down to row 18.
    Ensures scanner does not give up after row 15.
    """
    excel_path = tmp_path / "deep_header.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Preamble"

    # Rows 1-17: Instructions and procurement notes
    for r in range(1, 18):
        ws[f"A{r}"] = f"General Instruction Note Paragraph {r}"

    # Row 18: Actual Table Header
    ws["A18"] = "Clause No"
    ws["B18"] = "Technical Requirements"
    ws["C18"] = "Compliance Status"

    # Row 19: Data row
    ws["A19"] = "C-01"
    ws["B19"] = "Minimum 128GB DDR5 ECC Registered Memory"
    ws["C19"] = None

    wb.save(excel_path)
    wb.close()

    analysis = parse_excel_workbook(excel_path)
    s = analysis["sheets"][0]
    assert s["header_row"] == 18
    assert s["data_start_row"] == 19
    assert len(s["requirements"]) == 1
    assert "128GB DDR5" in s["requirements"][0]["requirement_text"]


def test_verbose_column_headers(tmp_path: Path) -> None:
    """
    Edge Case: Column header text longer than 50 characters (e.g. 68 chars)
    must not be ignored when discovering table headers.
    """
    excel_path = tmp_path / "verbose_headers.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Evaluation"

    ws["A1"] = "S.No"
    ws["B1"] = "Detailed Technical Specifications & Minimum Hardware Requirements"
    ws["C1"] = "Bidder Proposed Specifications & Compliance Status"

    ws["A2"] = 1
    ws["B2"] = "Support for OpenFlow 1.3 and BGP EVPN VxLAN"
    ws["C2"] = None

    wb.save(excel_path)
    wb.close()

    analysis = parse_excel_workbook(excel_path)
    s = analysis["sheets"][0]
    assert s["header_row"] == 1
    assert len(s["requirements"]) == 1
    assert "OpenFlow" in s["requirements"][0]["requirement_text"]


def test_formula_preservation_in_target_slots(tmp_path: Path) -> None:
    """
    Edge Case: Target cell containing an Excel formula must have has_formula=True
    and preserve the formula string so downstream writer does not blindly overwrite it.
    """
    excel_path = tmp_path / "formula_slots.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Scoring"

    ws["A1"] = "Item"
    ws["B1"] = "Requirement"
    ws["C1"] = "Compliance (Yes/No)"
    ws["D1"] = "Marks"

    ws["A2"] = 1
    ws["B2"] = "Enterprise NVMe SSD with 1 DWPD endurance"
    ws["C2"] = "Yes"
    ws["D2"] = '=IF(C2="Yes", 10, 0)'  # Formula cell

    wb.save(excel_path)
    wb.close()

    analysis = parse_excel_workbook(excel_path)
    slots = analysis["sheets"][0]["requirements"][0]["target_slots"]
    assert "marks" in slots
    assert slots["marks"]["has_formula"] is True
    assert slots["marks"]["formula"] == '=IF(C2="Yes", 10, 0)'


def test_category_vs_specification_column_selection(tmp_path: Path) -> None:
    """
    Edge Case: Unclassified 'Category' column before 'Specification Details'.
    Must correctly identify 'Specification Details' as the requirement column.
    """
    excel_path = tmp_path / "category_col.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Specs"

    ws["A1"] = "Item"
    ws["B1"] = "Category"  # Short text
    ws["C1"] = "Specification Details"  # Long requirement text
    ws["D1"] = "Compliance"

    ws["A2"] = 1
    ws["B2"] = "Compute"
    ws["C2"] = "Dual 4th Gen AMD EPYC Processors with minimum 64 cores per socket"
    ws["D2"] = None

    wb.save(excel_path)
    wb.close()

    analysis = parse_excel_workbook(excel_path)
    req = analysis["sheets"][0]["requirements"][0]
    assert "AMD EPYC" in req["requirement_text"]
    assert req["requirement_text"] != "Compute"

