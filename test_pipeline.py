#!/usr/bin/env python3
"""
Test Pipeline: PDF → Extract → Match → Fill Excel
Uses: PyMuPDF, pdfplumber, pytesseract, openpyxl, Ollama
"""

import json
import sys
import time
from pathlib import Path

import fitz  # PyMuPDF
import httpx
import openpyxl
import pdfplumber

# ─── CONFIG ───────────────────────────────────────────────
PDF_PATH = Path("testworkflowfile/network_basics.pdf")
EXCEL_PATH = Path("testworkflowfile/network_basics_questions.xlsx")
OUTPUT_PATH = Path("testworkflowfile/network_basics_output.xlsx")

OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen3:8b"
# ──────────────────────────────────────────────────────────


# ─── STEP 1: PDF EXTRACTION ──────────────────────────────
def extract_pdf(pdf_path: Path) -> dict:
    """Extract text, tables, and images from PDF."""
    print("\n[STEP 1] PDF Extraction")
    print(f"  File: {pdf_path}")

    result = {"text": "", "tables": [], "images": [], "page_count": 0}

    # --- PyMuPDF: text + images ---
    doc = fitz.open(str(pdf_path))
    result["page_count"] = len(doc)
    print(f"  Pages: {len(doc)}")

    full_text = []
    for page_num in range(len(doc)):
        page = doc[page_num]

        # Text
        page_text = page.get_text()
        full_text.append(page_text)

        # Images
        image_list = page.get_images(full=True)
        for img_idx, img in enumerate(image_list):
            result["images"].append({
                "page": page_num + 1,
                "image_index": img_idx,
                "xref": img[0],
            })

    result["text"] = "\n".join(full_text)
    doc.close()

    # --- pdfplumber: tables ---
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page_num, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            for t_idx, table in enumerate(tables):
                result["tables"].append({
                    "page": page_num + 1,
                    "table_index": t_idx,
                    "rows": table,
                    "row_count": len(table),
                })

    print(f"  Text length: {len(result['text'])} chars")
    print(f"  Tables found: {len(result['tables'])}")
    print(f"  Images found: {len(result['images'])}")

    # Save extracted text for reference
    extracted_path = Path("data/extracted/pdf_text.txt")
    extracted_path.parent.mkdir(parents=True, exist_ok=True)
    extracted_path.write_text(result["text"])
    print(f"  Saved: {extracted_path}")

    return result


# ─── STEP 2: EXCEL ANALYSIS ──────────────────────────────
def analyze_excel(excel_path: Path) -> dict:
    """Detect questions and empty slots in Excel."""
    print("\n[STEP 2] Excel Analysis")
    print(f"  File: {excel_path}")

    wb = openpyxl.load_workbook(str(excel_path))
    result = {"sheets": [], "questions": []}

    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        print(f"  Sheet: {sheet_name} ({ws.max_row} rows, {ws.max_column} cols)")

        # Find header row: look for a row where a cell is exactly "question" (not a sentence)
        header_row = None
        headers = {}
        for row in range(1, min(10, ws.max_row + 1)):
            row_vals = {}
            for col in range(1, ws.max_column + 1):
                val = ws.cell(row=row, column=col).value
                if val:
                    row_vals[col] = str(val).strip().strip("'\"").lower()
            # Exact match: a cell value should be "question" or "questions", not a full sentence
            for col, val in row_vals.items():
                if val in ("question", "questions"):
                    header_row = row
                    headers = row_vals
                    break
            if header_row:
                break

        if not header_row:
            print(f"  No header row found in {sheet_name}")
            continue

        print(f"  Header row: {header_row}")
        print(f"  Headers: {headers}")

        # Detect column roles
        q_col = None
        answer_col = None
        source_col = None
        for col, val in headers.items():
            if "question" in val:
                q_col = col
            elif "answer" in val or "ai answer" in val:
                answer_col = col
            elif "source" in val:
                source_col = col

        print(f"  Question col: {q_col}, Answer col: {answer_col}, Source col: {source_col}")

        # Find questions with empty answer slots
        for row in range(header_row + 1, ws.max_row + 1):
            question = ws.cell(row=row, column=q_col).value if q_col else None
            answer = ws.cell(row=row, column=answer_col).value if answer_col else None
            source = ws.cell(row=row, column=source_col).value if source_col else None

            if question and str(question).strip():
                q_text = str(question).strip()
                a_text = str(answer).strip() if answer else ""
                s_text = str(source).strip() if source else ""

                needs_fill = not a_text
                result["questions"].append({
                    "sheet": sheet_name,
                    "row": row,
                    "question": q_text,
                    "existing_answer": a_text,
                    "existing_source": s_text,
                    "answer_cell": f"{_col_letter(answer_col)}{row}" if answer_col else None,
                    "source_cell": f"{_col_letter(source_col)}{row}" if source_col else None,
                    "needs_fill": needs_fill,
                })

    wb.close()

    filled = [q for q in result["questions"] if not q["needs_fill"]]
    empty = [q for q in result["questions"] if q["needs_fill"]]
    print(f"  Total questions: {len(result['questions'])}")
    print(f"  Already filled: {len(filled)}")
    print(f"  Need filling: {len(empty)}")

    return result


def _col_letter(col_num: int) -> str:
    """Convert column number to letter (1=A, 2=B, etc.)."""
    result = ""
    while col_num > 0:
        col_num, remainder = divmod(col_num - 1, 26)
        result = chr(65 + remainder) + result
    return result


# ─── STEP 3: LLM ANSWER GENERATION ───────────────────────
def generate_answer(question: str, pdf_text: str) -> dict:
    """Use Ollama to answer a question based on PDF context."""
    prompt = f"""You are a networking expert. Answer the question based ONLY on the provided document context.

DOCUMENT CONTEXT:
{pdf_text[:3000]}

QUESTION: {question}

Instructions:
- Answer concisely and accurately based on the document
- If the document doesn't contain enough info, say so
- Include the relevant section/topic as source reference
- Return JSON format: {{"answer": "...", "source_section": "..."}}
"""

    try:
        with httpx.Client(timeout=60.0) as client:
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

            # Try to parse JSON from response
            # Strip markdown fences if present
            clean = content.strip()
            if clean.startswith("```"):
                lines = clean.split("\n")
                clean = "\n".join(lines[1:-1])

            try:
                parsed = json.loads(clean)
                return {
                    "answer": parsed.get("answer", content),
                    "source_section": parsed.get("source_section", "Networking Basics"),
                }
            except json.JSONDecodeError:
                # Fallback: use raw text as answer
                return {
                    "answer": content.strip(),
                    "source_section": "Networking Basics",
                }

    except Exception as e:
        return {
            "answer": f"ERROR: {e}",
            "source_section": "N/A",
        }


# ─── STEP 4: FILL EXCEL ──────────────────────────────────
def fill_excel(excel_path: Path, output_path: Path, questions: list, pdf_text: str) -> None:
    """Fill empty answer slots in Excel."""
    print("\n[STEP 4] Excel Population")
    print(f"  Output: {output_path}")

    wb = openpyxl.load_workbook(str(excel_path))

    filled_count = 0
    for q in questions:
        if not q["needs_fill"]:
            continue

        print(f"\n  Q: {q['question']}")
        result = generate_answer(q["question"], pdf_text)
        print(f"  A: {result['answer'][:80]}...")
        print(f"  Source: {result['source_section']}")

        # Write to Excel
        ws = wb[q["sheet"]]
        if q["answer_cell"]:
            ws[q["answer_cell"]] = result["answer"]
        if q["source_cell"]:
            ws[q["source_cell"]] = result["source_section"]
        filled_count += 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(output_path))
    wb.close()

    print(f"\n  Filled {filled_count} questions")
    print(f"  Saved to: {output_path}")


# ─── MAIN ─────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  TEST PIPELINE: PDF → Extract → Match → Fill Excel")
    print("=" * 60)

    start = time.time()

    # Step 1: Extract PDF
    pdf_data = extract_pdf(PDF_PATH)

    # Step 2: Analyze Excel
    excel_data = analyze_excel(EXCEL_PATH)

    # Step 3 + 4: Generate answers and fill Excel
    print("\n[STEP 3] LLM Answer Generation")
    print(f"  Model: {OLLAMA_MODEL}")
    print(f"  Questions to answer: {len([q for q in excel_data['questions'] if q['needs_fill']])}")

    fill_excel(EXCEL_PATH, OUTPUT_PATH, excel_data["questions"], pdf_data["text"])

    elapsed = time.time() - start
    print(f"\n{'=' * 60}")
    print(f"  DONE in {elapsed:.1f}s")
    print(f"  Output: {OUTPUT_PATH}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
