#!/usr/bin/env python3
"""
Step 1: PRD-Compliant PDF Ingestion (Section 6, 7, 8, 10, 12).
Extracts native text, structured tables with table IDs, image metadata,
and executes OCR on image-heavy / scanned pages (PRD Section 10).
Outputs the Unified Page-Level Document Representation defined in PRD Section 12.
"""

import argparse
import json
import shutil
from pathlib import Path
from typing import TypedDict

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


def extract_pdf(pdf_path: Path, enable_ocr: bool = True) -> NormalizedDocument:
    """
    Extracts text, structured tables, and image metadata from a PDF.
    Runs OCR on low-text / diagram pages (< 50 chars) per PRD Section 10.
    Conforms to PRD Section 12 Unified Page-Level Document Representation.
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

            # 4. OCR on image-heavy and scanned pages (PRD Section 10)
            ocr_text_list: list[str] = []
            if ocr_ready and len(clean_text) < 50:
                try:
                    # Render page at 200 DPI for high-accuracy local OCR
                    page_img = page.to_image(resolution=200).original
                    ocr_res = pytesseract.image_to_string(page_img).strip()
                    if ocr_res:
                        ocr_text_list.append(ocr_res)
                except Exception as err:
                    print(f"  [WARN] OCR failed on page {page_idx}: {err}")

            # If native text is absent/minimal, promote OCR text for primary searchability
            primary_text = clean_text if len(clean_text) >= 50 else ("\n\n".join(ocr_text_list).strip() or clean_text)

            # 5. Assemble Page Representation (PRD Section 12)
            pages_data.append({
                "page_number": page_idx,
                "text": primary_text,
                "tables": structured_tables,
                "images": extracted_images,
                "ocr": ocr_text_list,
                "vision_analysis": [],  # Reserved for vision AI (PRD Section 11)
            })

    return {
        "document_id": doc_id,
        "source_file": str(pdf_path.resolve()),
        "total_pages": total_pages,
        "pages": pages_data,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Step 1: PRD-Compliant PDF Ingestion")
    parser.add_argument(
        "--pdf",
        "-p",
        type=Path,
        default=Path("testworkflowfile/refernce.pdf"),
        help="Path to PDF file",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("pipeline_lab/reference_pdf_output.json"),
        help="Path to output JSON file",
    )
    parser.add_argument(
        "--no-ocr",
        action="store_true",
        help="Disable OCR on image pages",
    )
    args = parser.parse_args()

    pdf_path = args.pdf
    if not pdf_path.exists():
        if (Path("..") / args.pdf).exists():
            pdf_path = Path("..") / args.pdf
        elif Path("testworkflowfile/refernce.pdf").exists():
            pdf_path = Path("testworkflowfile/refernce.pdf")
        else:
            print(f"  [ERROR] PDF file not found: {pdf_path}")
            return

    print(f"Ingesting PDF: {pdf_path} (OCR enabled: {not args.no_ocr})")
    result = extract_pdf(pdf_path, enable_ocr=not args.no_ocr)

    # Save to JSON matching PRD Section 12 format
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"Extracted {result['total_pages']} pages successfully -> {args.output.resolve()}")
    for p in result["pages"]:
        if p["ocr"] or len(p["text"]) < 50:
            ocr_len = sum(len(x) for x in p["ocr"])
            print(f"  Page {p['page_number']}: {len(p['text'])} chars text | OCR: {ocr_len} chars extracted")


if __name__ == "__main__":
    main()
