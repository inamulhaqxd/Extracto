#!/usr/bin/env python3
"""
Adaptive Pipeline: PDF → Extract → Analyze Excel → LLM Fill → Output
Works for ANY Excel format — auto-detects structure, column types, and filling strategy.
"""

import json
import re
import sys
import time
from pathlib import Path

import pymupdf  # PyMuPDF
import httpx
import openpyxl
import pdfplumber
import pytesseract
from PIL import Image

# ─── CONFIG ───────────────────────────────────────────────
OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen3:8b"
DEFAULT_INPUT_DIR = Path("testworkflowfile")
# ──────────────────────────────────────────────────────────


# ══════════════════════════════════════════════════════════
# STEP 1: PDF EXTRACTION
# ══════════════════════════════════════════════════════════
def extract_pdf(pdf_path: Path) -> dict:
    """Extract text, tables, and OCR from images in PDF."""
    print(f"\n{'='*60}")
    print(f"  STEP 1: PDF EXTRACTION")
    print(f"{'='*60}")
    print(f"  File: {pdf_path}")

    result = {"text": "", "tables": [], "ocr_text": [], "page_count": 0}

    # --- PyMuPDF: text + images ---
    doc = pymupdf.open(str(pdf_path))
    result["page_count"] = len(doc)
    print(f"  Pages: {len(doc)}")

    full_text = []
    for page_num in range(len(doc)):
        page = doc[page_num]

        # Extract text
        page_text = page.get_text()
        full_text.append(page_text)

        # Extract images → OCR them
        image_list = page.get_images(full=True)
        for img_idx, img in enumerate(image_list):
            try:
                xref = img[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                pil_image = Image.open(__import__("io").BytesIO(image_bytes))
                ocr_text = pytesseract.image_to_string(pil_image)
                if ocr_text.strip():
                    result["ocr_text"].append({
                        "page": page_num + 1,
                        "image_index": img_idx,
                        "text": ocr_text.strip(),
                    })
            except Exception:
                pass

    result["text"] = "\n".join(full_text)
    doc.close()

    # --- pdfplumber: tables ---
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page_num, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            for t_idx, table in enumerate(tables):
                # Clean table cells
                cleaned = []
                for row in table:
                    cleaned.append([str(c).strip() if c else "" for c in row])
                result["tables"].append({
                    "page": page_num + 1,
                    "rows": cleaned,
                    "row_count": len(cleaned),
                })

    # Combine all text (including OCR)
    all_text = result["text"]
    for ocr in result["ocr_text"]:
        all_text += f"\n[OCR Page {ocr['page']} Image {ocr['image_index']}]: {ocr['text']}"
    result["full_text"] = all_text

    print(f"  Text: {len(result['text'])} chars")
    print(f"  OCR text blocks: {len(result['ocr_text'])}")
    print(f"  Tables: {len(result['tables'])}")

    # Save extracted text
    out_dir = Path("data/extracted")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "pdf_text.txt").write_text(all_text)
    print(f"  Saved: data/extracted/pdf_text.txt")

    return result


# ══════════════════════════════════════════════════════════
# STEP 2: EXCEL ANALYSIS (dynamic, format-agnostic)
# ══════════════════════════════════════════════════════════

# Column type detection keywords
COLUMN_TYPE_KEYWORDS = {
    "compliance": ["compliance", "comply", "yes/no", "y/n", "status", "conformance"],
    "marks": ["marks", "score", "points", "total marks", "marks obtained", "weight"],
    "remarks": ["remarks", "notes", "comments", "source section", "source", "reference"],
    "question": ["question", "questions", "query"],
    "answer": ["answer", "ai answer", "response", "reply", "solution"],
    "description": ["description", "spec", "specification", "requirement", "details"],
    "item": ["item", "items", "component", "scope", "feature"],
    "serial": ["s#", "s no", "s no.", "serial", "#", "s.n"],
}


def classify_column(header_text: str) -> str:
    """Classify a column header into a type."""
    text = header_text.lower().strip().strip("'\"")
    for col_type, keywords in COLUMN_TYPE_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                return col_type
    return "unknown"


def analyze_excel(excel_path: Path) -> dict:
    """Dynamically detect Excel structure, column types, and empty slots."""
    print(f"\n{'='*60}")
    print(f"  STEP 2: EXCEL ANALYSIS")
    print(f"{'='*60}")
    print(f"  File: {excel_path}")

    wb = openpyxl.load_workbook(str(excel_path))
    result = {"sheets": [], "all_slots": []}

    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        print(f"\n  Sheet: {sheet_name} ({ws.max_row} rows × {ws.max_column} cols)")

        # --- Find header row ---
        header_row = None
        headers = {}
        for row in range(1, min(15, ws.max_row + 1)):
            row_vals = {}
            for col in range(1, ws.max_column + 1):
                val = ws.cell(row=row, column=col).value
                if val:
                    cleaned = str(val).strip().strip("'\"").lower()
                    row_vals[col] = cleaned
            # A valid header row has multiple short labels, not full sentences
            short_labels = [v for v in row_vals.values() if len(v) < 30]
            if len(short_labels) >= 2:
                header_row = row
                headers = row_vals
                break

        if not header_row:
            print(f"    No header row found — skipping")
            continue

        # --- Classify columns ---
        col_types = {}
        for col, header_text in headers.items():
            col_type = classify_column(header_text)
            col_types[col] = col_type
            print(f"    Col {chr(64+col)}: {header_text[:40]:<40} → {col_type}")

        # --- Find empty slots that need filling ---
        # Identify "fill" columns (compliance, marks, remarks, answer)
        fill_types = {"compliance", "marks", "remarks", "answer", "unknown"}
        # Identify "context" columns (question, description, item)
        context_types = {"question", "description", "item"}

        # Find the primary context column (what each row is about)
        context_col = None
        for col, ct in col_types.items():
            if ct in ("question", "description", "item"):
                context_col = col
                break

        # Find serial number column
        serial_col = None
        for col, ct in col_types.items():
            if ct == "serial":
                serial_col = col
                break

        sheet_slots = []
        for row in range(header_row + 1, ws.max_row + 1):
            # Skip empty rows
            row_has_content = any(
                ws.cell(row=row, column=c).value
                for c in range(1, ws.max_column + 1)
            )
            if not row_has_content:
                continue

            # Get context for this row
            context = ""
            if context_col:
                cv = ws.cell(row=row, column=context_col).value
                if cv:
                    context = str(cv).strip()

            serial = ""
            if serial_col:
                sv = ws.cell(row=row, column=serial_col).value
                if sv:
                    serial = str(sv).strip()

            # Also grab description if available
            desc = ""
            for col, ct in col_types.items():
                if ct == "description":
                    dv = ws.cell(row=row, column=col).value
                    if dv:
                        desc = str(dv).strip()
                        break

            # Find empty fill-type cells
            for col, ct in col_types.items():
                if ct not in fill_types:
                    continue
                cell_val = ws.cell(row=row, column=col).value
                if cell_val and str(cell_val).strip():
                    continue  # Already filled

                # Build slot
                cell_ref = f"{_col_letter(col)}{row}"
                slot = {
                    "sheet": sheet_name,
                    "row": row,
                    "col": col,
                    "cell_ref": cell_ref,
                    "col_type": ct,
                    "header": headers.get(col, ""),
                    "context": context,
                    "description": desc,
                    "serial": serial,
                    "all_row_values": _get_row_values(ws, row, headers),
                }
                sheet_slots.append(slot)

        result["sheets"].append({
            "name": sheet_name,
            "header_row": header_row,
            "headers": headers,
            "col_types": col_types,
            "slot_count": len(sheet_slots),
        })
        result["all_slots"].extend(sheet_slots)

        print(f"    Header row: {header_row}")
        print(f"    Fillable slots: {len(sheet_slots)}")

    wb.close()

    # Summary
    by_type = {}
    for s in result["all_slots"]:
        by_type.setdefault(s["col_type"], []).append(s)
    print(f"\n  Total slots: {len(result['all_slots'])}")
    for ct, slots in by_type.items():
        print(f"    {ct}: {len(slots)}")

    return result


def _col_letter(col_num: int) -> str:
    result = ""
    while col_num > 0:
        col_num, remainder = divmod(col_num - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _get_row_values(ws, row: int, headers: dict) -> dict:
    """Get all cell values for a row, keyed by header name."""
    values = {}
    for col, header in headers.items():
        v = ws.cell(row=row, column=col).value
        values[header] = str(v).strip() if v else ""
    return values


# ══════════════════════════════════════════════════════════
# STEP 3: LLM FILL (adapts prompt per column type)
# ══════════════════════════════════════════════════════════
def build_prompt(slot: dict, pdf_text: str, col_type: str) -> str:
    """Build a context-aware prompt based on column type."""

    context = slot["context"]
    desc = slot["description"]
    serial = slot["serial"]
    header = slot["header"]

    # Build the "what is this row about" summary
    row_subject = context or desc or ""
    if serial:
        row_subject = f"[{serial}] {row_subject}"

    base_context = f"""You are analyzing a technical document for an RFP/tender evaluation.

DOCUMENT CONTENT:
{pdf_text[:4000]}

CURRENT ITEM: {row_subject}
COLUMN TO FILL: {header}"""

    if col_type == "compliance":
        return f"""{base_context}

TASK: Determine if the proposed solution in the document COMPLIES with this requirement.
- Answer "Yes" or "No" only
- Briefly explain why (1 sentence max)
- Return JSON: {{"compliance": "Yes/No", "reason": "..."}}
"""
    elif col_type == "marks":
        return f"""{base_context}

TASK: Assign marks based on how well the document meets this requirement.
- Consider the requirement and what the document describes
- Return JSON: {{"marks": <number>, "reason": "..."}}
"""
    elif col_type in ("remarks", "answer"):
        return f"""{base_context}

TASK: Provide a detailed technical response/remark for this item.
- Reference specific details from the document
- Be concise but thorough
- Return JSON: {{"response": "...", "source_section": "..."}}
"""
    elif col_type == "unknown":
        return f"""{base_context}

TASK: Fill this cell with appropriate content based on the document.
- Analyze what the column likely represents from context
- Return JSON: {{"response": "..."}}
"""
    else:
        return f"""{base_context}

TASK: Provide relevant information for this cell.
- Return JSON: {{"response": "..."}}
"""


def build_batch_prompt(slots: list, pdf_text: str) -> str:
    """Build a single prompt for multiple slots in the same sheet."""
    items = []
    for i, slot in enumerate(slots):
        subject = slot["context"] or slot["description"] or ""
        if slot["serial"]:
            subject = f"[{slot['serial']}] {subject}"
        items.append(f"Item {i+1} (row {slot['row']}, col {slot['header']}): {subject}")

    items_text = "\n".join(items)

    return f"""You are analyzing a technical document for an RFP/tender evaluation.

DOCUMENT CONTENT:
{pdf_text[:4000]}

ITEMS TO FILL:
{items_text}

For EACH item, provide the appropriate response based on the column type.
Return a JSON array with one object per item, in order:
[
  {{"row": <row_number>, "col": "<column_header>", "response": "<your answer>"}},
  ...
]

Rules:
- For "compliance" columns: answer "Yes" or "No" with brief reason
- For "marks" columns: assign a number 0-10 with brief reason
- For "remarks"/"answer" columns: provide detailed technical response referencing the document
- For "unknown" columns: infer from context and provide appropriate content
- Be concise but accurate
- Reference specific details from the document where possible
"""


def call_llm(prompt: str) -> dict:
    """Call Ollama and parse JSON response."""
    try:
        with httpx.Client(timeout=120.0) as client:
            res = client.post(
                f"{OLLAMA_URL}/api/chat",
                json={
                    "model": OLLAMA_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {"temperature": 0.1},
                },
            )
            res.raise_for_status()
            content = res.json().get("message", {}).get("content", "")

            # Parse JSON
            clean = content.strip()
            if clean.startswith("```"):
                lines = clean.split("\n")
                clean = "\n".join(lines[1:-1])

            try:
                return json.loads(clean)
            except json.JSONDecodeError:
                return {"response": content.strip()}

    except Exception as e:
        return {"response": f"ERROR: {e}"}


def fill_slots(pdf_data: dict, excel_data: dict) -> list:
    """Generate content for each empty slot using LLM (batched per sheet)."""
    print(f"\n{'='*60}")
    print(f"  STEP 3: LLM FILL (batched)")
    print(f"{'='*60}")

    pdf_text = pdf_data.get("full_text", pdf_data["text"])
    results = []

    # Group slots by sheet
    sheet_slots = {}
    for slot in excel_data["all_slots"]:
        sheet_slots.setdefault(slot["sheet"], []).append(slot)

    for sheet_name, slots in sheet_slots.items():
        # Group by column type within the sheet
        col_groups = {}
        for s in slots:
            col_groups.setdefault(s["col_type"], []).append(s)

        for col_type, col_slots in col_groups.items():
            # Batch up to 15 items per LLM call
            batch_size = 15
            for batch_start in range(0, len(col_slots), batch_size):
                batch = col_slots[batch_start:batch_start + batch_size]

                print(f"\n  Sheet: {sheet_name} | {col_type} | batch {batch_start//batch_size + 1} ({len(batch)} items)")

                prompt = build_batch_prompt(batch, pdf_text)
                response = call_llm(prompt)

                # Parse response — could be list or dict
                if isinstance(response, list):
                    items = response
                elif isinstance(response, dict) and "response" in response:
                    # Try to parse the response string as JSON
                    try:
                        items = json.loads(response["response"])
                        if not isinstance(items, list):
                            items = [items]
                    except (json.JSONDecodeError, TypeError):
                        items = [response]
                else:
                    items = [response]

                # Map results back to slots
                for i, slot in enumerate(batch):
                    if i < len(items):
                        item = items[i]
                        if isinstance(item, dict):
                            cell_value = item.get("response", item.get("compliance", item.get("marks", "")))
                            source = item.get("source_section", "")
                            reason = item.get("reason", "")
                            if col_type == "compliance":
                                cell_value = f"{item.get('compliance', cell_value)}"
                                if reason:
                                    cell_value += f" - {reason}"
                            elif col_type == "marks":
                                cell_value = f"{item.get('marks', cell_value)}"
                                if reason:
                                    cell_value += f" ({reason})"
                            elif source:
                                cell_value = f"{cell_value} [Source: {source}]"
                        else:
                            cell_value = str(item)

                        slot["generated_value"] = cell_value
                        display = cell_value[:60] + "..." if len(str(cell_value)) > 60 else cell_value
                        print(f"    {slot['cell_ref']}: {display}")
                    else:
                        slot["generated_value"] = ""

                    results.append(slot)

    return results


# ══════════════════════════════════════════════════════════
# STEP 4: EXCEL OUTPUT
# ══════════════════════════════════════════════════════════
def write_excel(excel_path: Path, output_path: Path, filled_slots: list) -> None:
    """Write generated values back into the Excel."""
    print(f"\n{'='*60}")
    print(f"  STEP 4: EXCEL OUTPUT")
    print(f"{'='*60}")

    wb = openpyxl.load_workbook(str(excel_path))

    for slot in filled_slots:
        ws = wb[slot["sheet"]]
        cell = ws[slot["cell_ref"]]
        cell.value = slot.get("generated_value", "")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(output_path))
    wb.close()

    print(f"  Filled {len(filled_slots)} cells")
    print(f"  Saved: {output_path}")


# ══════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════
def main():
    # Accept specific PDF+XLSX pair via args, or auto-detect from testworkflowfile/
    if len(sys.argv) == 3:
        pdf_path = Path(sys.argv[1])
        xlsx_path = Path(sys.argv[2])
        pairs = [(pdf_path, xlsx_path)]
    else:
        # Auto-detect: pair files by matching base names
        input_dir = DEFAULT_INPUT_DIR
        pdf_files = [f for f in sorted(input_dir.glob("*.pdf"))]
        xlsx_files = [f for f in sorted(input_dir.glob("*.xlsx")) if "output" not in f.name.lower()]

        pairs = []
        for pdf in pdf_files:
            # Find matching Excel by shared prefix or best guess
            matches = [x for x in xlsx_files if x.stem.split("_")[0] in pdf.stem or pdf.stem.split("_")[0] in x.stem]
            if matches:
                for xlsx in matches:
                    pairs.append((pdf, xlsx))
            else:
                # No match — try each Excel
                for xlsx in xlsx_files:
                    pairs.append((pdf, xlsx))

    if not pairs:
        print("No PDF+Excel pairs found.")
        sys.exit(1)

    print("=" * 60)
    print("  ADAPTIVE PIPELINE")
    print("  Auto-detects format and fills any Excel from any PDF")
    print("=" * 60)

    for pdf_path, xlsx_path in pairs:
        print(f"\n{'#'*60}")
        print(f"  PDF:  {pdf_path.name}")
        print(f"  XLSX: {xlsx_path.name}")
        print(f"{'#'*60}")

        start = time.time()

        # Step 1: Extract PDF
        pdf_data = extract_pdf(pdf_path)

        # Step 2: Analyze Excel
        excel_data = analyze_excel(xlsx_path)

        if not excel_data["all_slots"]:
            print("\n  No empty slots to fill!")
            continue

        # Step 3: Generate answers
        filled = fill_slots(pdf_data, excel_data)

        # Step 4: Write output
        out_name = f"{xlsx_path.stem}_output.xlsx"
        out_path = xlsx_path.parent / out_name
        write_excel(xlsx_path, out_path, filled)

        elapsed = time.time() - start
        print(f"\n  DONE in {elapsed:.1f}s")
        print(f"  Output: {out_path}")


if __name__ == "__main__":
    main()
