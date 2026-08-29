from pathlib import Path

import fitz  # PyMuPDF
import openpyxl
import pytest
from openpyxl.styles import Font, PatternFill

from ai_rfp_excel.app.ai.mock_provider import MockLLMProvider
from ai_rfp_excel.app.matching.models import FactItem


@pytest.fixture
def mock_llm() -> MockLLMProvider:
    """Provide an offline MockLLMProvider for test isolation."""
    return MockLLMProvider()


@pytest.fixture
def sample_facts_corpus() -> list[FactItem]:
    """Provide a standard reference corpus of technical server/storage facts."""
    return [
        FactItem(
            field_name="Compute Architecture",
            value="Dual Intel Xeon Gold 6430 32-core processors",
            source_page=2,
            source_table_id="T2-1",
            confidence=0.98,
        ),
        FactItem(
            field_name="System Memory",
            value="512GB DDR5-4800 ECC Registered RDIMMs",
            source_page=3,
            source_table_id="T3-1",
            confidence=0.95,
        ),
        FactItem(
            field_name="Storage Capacity",
            value="150TB All-Flash NVMe SSDs in RAID 6",
            source_page=4,
            source_table_id="T4-1",
            confidence=0.96,
        ),
        FactItem(
            field_name="Network Connectivity",
            value="4x 25GbE SFP28 ports plus 2x 10GbE Base-T management ports",
            source_page=5,
            confidence=0.92,
        ),
        FactItem(
            field_name="Power & Thermal",
            value="Dual redundant 1600W Titanium hot-pluggable power supplies",
            source_page=6,
            confidence=0.95,
        ),
    ]


@pytest.fixture
def sample_pdf_text_only(tmp_path: Path) -> Path:
    """Create a text-only PDF datasheet."""
    doc = fitz.open()
    page = doc.new_page()
    text = (
        "Enterprise Server Datasheet\n"
        "Model: PowerEdge R760\n"
        "Processors: Dual Intel Xeon Gold 6430\n"
        "Memory: Up to 512GB DDR5 ECC\n"
        "Storage: 150TB All-Flash NVMe\n"
        "Power: Redundant 1600W Titanium PSUs\n"
    )
    page.insert_text((50, 50), text, fontsize=12)
    pdf_path = tmp_path / "text_only_spec.pdf"
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


@pytest.fixture
def sample_pdf_table_heavy(tmp_path: Path) -> Path:
    """Create a table-heavy PDF datasheet."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Technical Specification Matrix", fontsize=14)

    # Draw table borders and cells
    table_text = (
        "Component\tSpecification\tDetails\n"
        "Processor\tIntel Xeon Gold\t32 Cores per socket\n"
        "RAM\t512GB DDR5\tRegistered ECC\n"
        "Disks\t150TB NVMe\tU.2 Hot Swap\n"
    )
    page.insert_text((50, 100), table_text, fontsize=10)
    pdf_path = tmp_path / "table_heavy_spec.pdf"
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


@pytest.fixture
def sample_excel_standard(tmp_path: Path) -> Path:
    """Create a standard RFP Excel template workbook."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Technical Compliance"

    headers = ["Item #", "Technical Requirement", "Compliance Status", "Remarks / Evidence"]
    for col_idx, h in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=h)
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")

    requirements = [
        (1, "Dual Intel Xeon Gold 6430 processors"),
        (2, "Minimum 256GB DDR5 memory"),
        (3, "At least 100TB All-Flash storage"),
        (4, "4x 25GbE network interfaces"),
        (5, "Redundant power supply units"),
    ]

    for r_idx, (num, req_str) in enumerate(requirements, start=2):
        ws.cell(row=r_idx, column=1, value=num)
        ws.cell(row=r_idx, column=2, value=req_str)
        ws.cell(row=r_idx, column=3, value="")
        ws.cell(row=r_idx, column=4, value="")

    # Formula row
    ws.cell(row=7, column=1, value="Total")
    ws.cell(row=7, column=2, value="=COUNT(A2:A6)")

    excel_path = tmp_path / "rfp_standard_template.xlsx"
    wb.save(excel_path)
    return excel_path


@pytest.fixture
def sample_excel_renamed_cols(tmp_path: Path) -> Path:
    """Create an Excel template with non-standard renamed headers and rearranged columns."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Vendor Bids"

    # Rearranged order: Remarks first, then Specs, then Compliance, then Serial
    headers = ["Clarifications & Proof", "Mandatory Specifications", "Vendor Response (Y/N)", "Index"]
    for col_idx, h in enumerate(headers, start=1):
        ws.cell(row=1, column=col_idx, value=h)

    ws.cell(row=2, column=1, value="")
    ws.cell(row=2, column=2, value="512GB DDR5 Registered RAM")
    ws.cell(row=2, column=3, value="")
    ws.cell(row=2, column=4, value="1.1")

    excel_path = tmp_path / "rfp_renamed_template.xlsx"
    wb.save(excel_path)
    return excel_path
