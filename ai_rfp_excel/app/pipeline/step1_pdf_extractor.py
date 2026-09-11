#!/usr/bin/env python3
"""
Step 1: PRD-Compliant PDF Ingestion (Sections 6, 7, 8, 10, 12).
Extracts native text, structured tables with table IDs, image metadata,
and executes OCR on image-heavy / scanned pages (PRD Section 10).
Outputs the Unified Page-Level Document Representation defined in PRD Section 12.

Strict typing only — zero Any (Rule 4). 100% offline (Rule 10).
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from importlib.machinery import ModuleSpec
from pathlib import Path
from types import ModuleType
from typing import TypedDict

if importlib.util.find_spec("pandas") is None and "pandas" not in sys.modules:
    _pandas_stub = ModuleType("pandas")
    _pandas_stub.__spec__ = ModuleSpec(name="pandas", loader=None)
    sys.modules["pandas"] = _pandas_stub

try:
    from docling.document_converter import DocumentConverter
    _HAS_DOCLING: bool = True
except Exception:
    _HAS_DOCLING = False

import pdfplumber
import pytesseract

# Configure Tesseract path if available
_default_tess = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if Path(_default_tess).exists():
    pytesseract.pytesseract.tesseract_cmd = _default_tess
elif shutil.which("tesseract"):
    pytesseract.pytesseract.tesseract_cmd = shutil.which("tesseract") or "tesseract"


class ExtractedTable(TypedDict):
    table_id: str
    headers: list[str]
    rows: list[list[str]]


class ExtractedImage(TypedDict):
    image_id: str
    page_number: int
    name: str


class PageRepresentation(TypedDict):
    page_number: int
    text: str
    tables: list[ExtractedTable]
    images: list[ExtractedImage]
    ocr: list[str]
    vision_analysis: list[dict[str, str]]


class NormalizedDocument(TypedDict):
    document_id: str
    source_file: str
    total_pages: int
    pages: list[PageRepresentation]


def is_ocr_available() -> bool:
    """Checks if Tesseract binary is accessible on the host."""
    try:
        cmd_path = Path(getattr(pytesseract.pytesseract, "tesseract_cmd", "tesseract"))
        return cmd_path.exists() or shutil.which("tesseract") is not None
    except Exception:
        return False


def table_to_markdown(headers: list[str], rows: list[list[str]], title: str = "") -> str:
    """
    Convert structured table headers and rows into clean GitHub-flavored Markdown table format.
    Guarantees table columns (pricing, BOQ items, capacities) are searchable and retain row context.
    """
    if not headers and not rows:
        return ""
    col_count = max(len(headers), max((len(r) for r in rows), default=0))
    if col_count == 0:
        return ""

    padded_headers = list(headers) + [""] * (col_count - len(headers))
    header_line = "| " + " | ".join(h.replace("|", "\\|").replace("\n", " ").strip() for h in padded_headers) + " |"
    separator_line = "| " + " | ".join("---" for _ in range(col_count)) + " |"

    row_lines: list[str] = []
    for r in rows:
        padded_row = list(r) + [""] * (col_count - len(r))
        row_str = "| " + " | ".join(cell.replace("|", "\\|").replace("\n", " ").strip() for cell in padded_row) + " |"
        row_lines.append(row_str)

    md = [header_line, separator_line, *row_lines]
    prefix = f"[Table {title}]:\n" if title else ""
    return prefix + "\n".join(md)


def extract_pdf_with_docling(pdf_path: Path) -> NormalizedDocument | None:
    """
    Extracts PDF pages and tables using Docling (Rule 1: No vision models, OCR only; Rule 4: Zero Any).
    Converts document into PRD Section 12 Unified Page-Level Document Representation with rich Markdown tables.
    """
    if not _HAS_DOCLING:
        return None

    try:
        converter = DocumentConverter()
        result = converter.convert(str(pdf_path.resolve()))
        doc = result.document
        doc_id = pdf_path.stem

        full_md: str = doc.export_to_markdown() if hasattr(doc, "export_to_markdown") else ""
        num_pages: int = int(getattr(doc, "num_pages", 0) or 0)

        all_tables: list[ExtractedTable] = []
        if hasattr(doc, "tables") and doc.tables:
            for t_idx, tbl in enumerate(doc.tables, start=1):
                try:
                    df = tbl.export_to_dataframe()
                    t_headers = [str(c).strip() for c in df.columns]
                    t_rows = [[str(cell).strip() for cell in row] for row in df.values.tolist()]
                    page_no = int(getattr(tbl, "page_no", 1) or 1)
                    all_tables.append({
                        "table_id": f"T{page_no:02d}-{t_idx:02d}",
                        "headers": t_headers,
                        "rows": t_rows,
                    })
                except Exception:
                    continue

        pages_data: list[PageRepresentation] = []
        if num_pages > 0:
            for p_idx in range(1, num_pages + 1):
                p_tables = [t for t in all_tables if t["table_id"].startswith(f"T{p_idx:02d}-")]
                p_text = ""
                try:
                    if hasattr(doc, "export_to_markdown"):
                        p_text = doc.export_to_markdown(page_no=p_idx)
                except Exception:
                    p_text = ""

                if not p_text.strip() and p_idx == 1:
                    p_text = full_md

                pages_data.append({
                    "page_number": p_idx,
                    "text": p_text,
                    "tables": p_tables,
                    "images": [],
                    "ocr": [],
                    "vision_analysis": [],
                })
        else:
            pages_data.append({
                "page_number": 1,
                "text": full_md,
                "tables": all_tables,
                "images": [],
                "ocr": [],
                "vision_analysis": [],
            })

        return {
            "document_id": doc_id,
            "source_file": str(pdf_path.resolve()),
            "total_pages": len(pages_data),
            "pages": pages_data,
        }
    except Exception as err:
        print(f"  [WARN] Docling extraction failed, falling back to pdfplumber: {err}")
        return None


def extract_pdf_with_pdfplumber(pdf_path: Path, enable_ocr: bool = True) -> NormalizedDocument:
    """
    Extracts text, structured tables, and image metadata from a PDF using pdfplumber.
    Runs local Tesseract OCR on low-text / diagram pages (< 50 chars) per PRD Section 10.
    Converts structured tables into clean Markdown tables directly embedded in primary_text.
    """
    pages_data: list[PageRepresentation] = []
    doc_id = pdf_path.stem
    ocr_ready = enable_ocr and is_ocr_available()

    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)

        for page_idx, page in enumerate(pdf.pages, start=1):
            # 1. Native text extraction (PRD Section 7)
            raw_text: str = page.extract_text() or ""
            clean_text = raw_text.strip()

            # 2. Structured table extraction (PRD Section 8)
            raw_tables = page.extract_tables() or []
            structured_tables: list[ExtractedTable] = []

            for t_idx, table in enumerate(raw_tables, start=1):
                if not table:
                    continue

                cleaned_rows: list[list[str]] = [
                    [cell.strip() if cell else "" for cell in row]
                    for row in table
                ]

                # Filter out completely empty rows
                cleaned_rows = [row for row in cleaned_rows if any(row)]
                if not cleaned_rows:
                    continue

                table_id = f"T{page_idx:02d}-{t_idx:02d}"
                headers = cleaned_rows[0]
                rows = cleaned_rows[1:] if len(cleaned_rows) > 1 else []

                structured_tables.append({
                    "table_id": table_id,
                    "headers": headers,
                    "rows": rows,
                })

            # 3. Image extraction metadata (PRD Section 9)
            raw_images = getattr(page, "images", [])
            extracted_images: list[ExtractedImage] = []
            for img_idx, img in enumerate(raw_images, start=1):
                extracted_images.append({
                    "image_id": f"IMG{page_idx:02d}-{img_idx:02d}",
                    "page_number": page_idx,
                    "name": str(img.get("name", f"img_{img_idx}")),
                })

            # 4. OCR on image-heavy, scanned pages, or embedded diagrams (PRD Section 10)
            ocr_text_list: list[str] = []
            if ocr_ready:
                if len(clean_text) < 50:
                    try:
                        # Full page scanned: render at 200 DPI for high-accuracy local OCR
                        page_img = page.to_image(resolution=200).original
                        ocr_res = pytesseract.image_to_string(page_img).strip()
                        if ocr_res:
                            ocr_text_list.append(ocr_res)
                    except Exception as err:
                        print(f"  [WARN] OCR failed on page {page_idx}: {err}")
                elif raw_images:
                    # Hybrid page: native text present, but page also contains embedded images/diagrams
                    for img in raw_images:
                        x0 = img.get("x0")
                        top = img.get("top")
                        x1 = img.get("x1")
                        bottom = img.get("bottom")
                        if x0 is not None and top is not None and x1 is not None and bottom is not None:
                            w = float(x1) - float(x0)
                            h = float(bottom) - float(top)
                            if w >= 80 and h >= 80:
                                try:
                                    cropped = page.crop((x0, top, x1, bottom))
                                    img_obj = cropped.to_image(resolution=200).original
                                    img_text = pytesseract.image_to_string(img_obj).strip()
                                    if img_text:
                                        ocr_text_list.append(img_text)
                                except Exception as err:
                                    print(f"  [WARN] Embedded image OCR failed on page {page_idx}: {err}")

            # If native text is absent/minimal, promote OCR text; otherwise append embedded image OCR
            if len(clean_text) < 50:
                primary_text = "\n\n".join(ocr_text_list).strip() or clean_text
            elif ocr_text_list:
                primary_text = clean_text + "\n\n" + "\n\n".join(f"[Embedded Diagram OCR]:\n{t}" for t in ocr_text_list)
            else:
                primary_text = clean_text

            # Embed structured tables as Markdown tables to preserve cell columns & row context
            table_md_blocks: list[str] = []
            for tbl in structured_tables:
                t_md = table_to_markdown(tbl["headers"], tbl["rows"], title=tbl["table_id"])
                if t_md:
                    table_md_blocks.append(t_md)

            if table_md_blocks:
                primary_text = (primary_text + "\n\n" + "\n\n".join(table_md_blocks)).strip()

            # 5. Assemble Page Representation (PRD Section 12)
            pages_data.append({
                "page_number": page_idx,
                "text": primary_text,
                "tables": structured_tables,
                "images": extracted_images,
                "ocr": ocr_text_list,
                "vision_analysis": [],  # Strictly zero vision AI (Rule 1)
            })

    return {
        "document_id": doc_id,
        "source_file": str(pdf_path.resolve()),
        "total_pages": total_pages,
        "pages": pages_data,
    }


def extract_pdf(pdf_path: Path, enable_ocr: bool = True, prefer_docling: bool = True) -> NormalizedDocument:
    """
    Extracts text, structured tables, and image metadata from a PDF.
    Attempts Docling extraction first if available and prefer_docling=True.
    Falls back gracefully to high-accuracy pdfplumber extraction with local Tesseract OCR (PRD Section 10).
    Conforms to PRD Section 12 Unified Page-Level Document Representation.
    """
    if prefer_docling and _HAS_DOCLING:
        docling_result = extract_pdf_with_docling(pdf_path)
        if docling_result is not None and docling_result["pages"] and any(p["text"].strip() for p in docling_result["pages"]):
            return docling_result

    return extract_pdf_with_pdfplumber(pdf_path=pdf_path, enable_ocr=enable_ocr)


def save_pdf_output(data: NormalizedDocument, output_path: Path) -> Path:
    """Save normalized PDF representation as an inspectable JSON artifact (Rule 8)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return output_path
