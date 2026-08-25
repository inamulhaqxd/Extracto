import os
import tempfile
from pathlib import Path

import openpyxl
import pytest

from app.excel.analyzer import ExcelAnalyzer


@pytest.fixture
def sample_excel():
    wb = openpyxl.Workbook()

    ws1 = wb.active
    ws1.title = "Requirements"
    ws1["A1"] = "Requirement"
    ws1["B1"] = "DWP"
    ws1["C1"] = "Premier"
    ws1["A2"] = "Minimum 32 cores per controller"
    ws1["A3"] = "Should have at least 350 TB RAW capacity"
    ws1["A4"] = "Per Disk capacity = 15TB"

    ws2 = wb.create_sheet("Specifications")
    ws2["A1"] = "Component"
    ws2["B1"] = "Value"
    ws2["A2"] = "CPU"
    ws2["B2"] = "Intel Xeon"

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        wb.save(f.name)
        yield f.name

    os.unlink(f.name)


def test_analyze_excel(sample_excel):
    analyzer = ExcelAnalyzer()
    result = analyzer.analyze(sample_excel)

    assert result["sheet_count"] == 2
    assert result["total_requirements"] > 0
    assert len(result["sheets"]) == 2

    analyzer.close()


def test_detect_headers(sample_excel):
    analyzer = ExcelAnalyzer()
    result = analyzer.analyze(sample_excel)

    sheets = result["sheets"]
    assert len(sheets) > 0

    first_sheet = sheets[0]
    assert "Requirement" in first_sheet["headers"]
    assert "DWP" in first_sheet["headers"]

    analyzer.close()


def test_detect_vendor_columns(sample_excel):
    analyzer = ExcelAnalyzer()
    result = analyzer.analyze(sample_excel)

    sheets = result["sheets"]
    first_sheet = sheets[0]

    assert "DWP" in first_sheet["vendor_columns"]
    assert "Premier" in first_sheet["vendor_columns"]

    analyzer.close()


def test_detect_requirements(sample_excel):
    analyzer = ExcelAnalyzer()
    result = analyzer.analyze(sample_excel)

    assert result["total_requirements"] > 0

    req_texts = [r["requirement_text"] for r in result["requirements"]]
    assert any("32 cores" in text for text in req_texts)

    analyzer.close()
