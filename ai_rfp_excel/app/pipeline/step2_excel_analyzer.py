#!/usr/bin/env python3
"""
Step 2: PRD-Compliant Dynamic Excel Workbook & Requirement Analyzer (Sections 16, 17, 18, 19).
Analyzes uploaded Excel workbooks dynamically without hardcoded cell addresses:
- Detects sheets, dimensions, merged cell ranges, and hidden rows/columns.
- Dynamically locates header rows and composite sub-headers.
- Classifies columns (Index, Section, Requirement, Compliance, Marks, Remarks, Answer).
- Extracts sections, requirements, and fillable target slots.
- Exports validated JSON artifacts per Rule 8.
"""

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import TypedDict

import openpyxl
from openpyxl.cell.cell import MergedCell
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

# Classification dictionaries per PRD Section 18 & 19
REQUIREMENT_KEYWORDS = {
    "requirement", "requirements", "specification", "specifications",
    "description", "feature", "features", "criteria",
    "specs", "technical specification", "technical requirement",
    "scope", "question", "questions", "item description", "parameter",
    "parameters", "item description / specification",
}

COMPLIANCE_KEYWORDS = {
    "compliance", "compliant", "complied", "status", "meet", "meets",
    "y/n", "c/nc", "conformity", "compliance (yes/no)", "compliance status",
    "complied / not complied", "vendor compliance",
}

TOTAL_MARKS_KEYWORDS = {
    "total marks", "total mark", "max marks", "max mark", "max score",
    "weight", "weightage", "allocated marks",
}

MARKS_KEYWORDS = {
    "marks obtained", "marks obtain", "marks", "score obtained",
    "score", "points obtained", "points", "awarded marks",
}

REMARKS_KEYWORDS = {
    "remarks", "remark", "comments", "comment", "notes", "note",
    "clarification", "explanation", "deviation", "reference",
    "evidence", "source section", "source reference", "citation",
}

ANSWER_KEYWORDS = {
    "answer", "proposed", "offered", "vendor response", "bidder response",
    "offered specification", "offered spec", "compliance details",
}


class TargetSlot(TypedDict):
    slot_type: str  # "compliance", "answer", "remarks", "marks"
    header_name: str
    column_letter: str
    column_index: int
    cell_coordinate: str
    current_value: str | None
    has_formula: bool
    formula: str | None


class ParsedRequirement(TypedDict):
    requirement_id: str
    sheet_name: str
    row_number: int
    section: str | None
    requirement_text: str
    source_cell: str
    target_slots: dict[str, TargetSlot]


class DetectedColumn(TypedDict):
    column_index: int
    column_letter: str
    header_name: str
    column_type: str


class SheetAnalysis(TypedDict):
    sheet_name: str
    sheet_index: int
    max_row: int
    max_column: int
    header_row: int
    data_start_row: int
    columns: list[DetectedColumn]
    requirements: list[ParsedRequirement]


class WorkbookAnalysis(TypedDict):
    workbook_id: str
    source_file: str
    file_hash: str
    sheet_names: list[str]
    sheets: list[SheetAnalysis]
    total_requirements: int


def get_merged_cell_value(ws: Worksheet, row: int, col: int) -> object:
    """Safely retrieves cell value, resolving merged cell master values."""
    cell = ws.cell(row=row, column=col)
    if not isinstance(cell, MergedCell):
        return cell.value

    for rng in ws.merged_cells.ranges:
        if row in range(rng.min_row, rng.max_row + 1) and col in range(rng.min_col, rng.max_col + 1):
            master_cell = ws.cell(row=rng.min_row, column=rng.min_col)
            return master_cell.value

    return None


def classify_column_header(header_text: str) -> str:
    """Classifies a column header into functional categories."""
    lower_raw = header_text.lower().strip()
    clean = re.sub(r"[^\w\s/]", " ", lower_raw).strip()
    clean = re.sub(r"\s+", " ", clean)
    tokens = set(clean.split())

    # 1. Compliance
    if any(k in clean for k in COMPLIANCE_KEYWORDS) or "yes/no" in lower_raw or "y/n" in lower_raw:
        return "compliance"

    # 2. Remarks
    if any(k in clean for k in REMARKS_KEYWORDS):
        return "remarks"

    # 3. Index / Serial
    if (
        clean in ("item", "clause", "cl", "ref", "index")
        or any(phrase in clean for phrase in ("s no", "sr no", "sl no", "item no", "serial no", "clause no", "clause #", "cl no"))
        or any(k in tokens for k in ("s.no", "s/no", "sr.no", "sl.no", "#", "serial"))
    ):
        return "index"

    # 4. Total Marks
    if any(k in clean for k in TOTAL_MARKS_KEYWORDS):
        return "total_marks"

    # 5. Marks (ensure 'remarks' does not match)
    if any(k in clean for k in MARKS_KEYWORDS) or "marks" in tokens:
        return "marks"

    # 6. Answer
    if any(k in clean for k in ANSWER_KEYWORDS):
        return "answer"

    # 7. Requirement
    if any(k in clean for k in REQUIREMENT_KEYWORDS):
        return "requirement"

    # Default fallback
    return "unknown"


def detect_headers(ws: Worksheet) -> tuple[int | None, int, dict[int, str]]:
    """
    Dynamically discovers primary header row and handles composite subheaders.
    Returns: (header_row, data_start_row, {col_idx: composite_header_label})
    """
    max_r = ws.max_row or 1
    max_c = ws.max_column or 1
    header_row: int | None = None
    headers: dict[int, str] = {}

    # 1. Scan rows 1 to min(35, max_r + 1) for row with >= 2 DISTINCT concise text labels
    for r in range(1, min(35, max_r + 1)):
        row_labels: list[str] = []
        for c in range(1, max_c + 1):
            val = get_merged_cell_value(ws, r, c)
            if val is not None:
                s_val = str(val).strip()
                # Accept headers up to 120 chars as long as they aren't multi-line paragraphs
                if 1 <= len(s_val) < 120 and "\n\n" not in s_val:
                    row_labels.append(s_val)

        # Avoid title banners merged across all columns
        if len(set(row_labels)) >= 2:
            header_row = r
            break

    if header_row is None:
        return None, 1, {}

    # 2. Check for multi-level composite sub-headers in next row
    has_sub_header = False
    sub_row = header_row + 1
    if sub_row <= max_r:
        # Check if header row has merged multi-column ranges
        header_has_merged_cols = False
        for rng in ws.merged_cells.ranges:
            if rng.min_row <= header_row <= rng.max_row and rng.max_col > rng.min_col:
                header_has_merged_cols = True
                break

        if header_has_merged_cols:
            sub_labels: list[str] = []
            long_data_found = False
            for c in range(1, max_c + 1):
                v_main = get_merged_cell_value(ws, header_row, c)
                v_sub = get_merged_cell_value(ws, sub_row, c)
                if v_sub is not None and v_sub != v_main:
                    s_sub = str(v_sub).strip()
                    # Sentences, punctuation, or long texts indicate data rows rather than column headers
                    if len(s_sub) > 80 or s_sub.endswith("."):
                        long_data_found = True
                    elif 1 <= len(s_sub) < 60:
                        sub_labels.append(s_sub)
            if len(set(sub_labels)) >= 2 and not long_data_found:
                has_sub_header = True

    data_start_row = (header_row + 2) if has_sub_header else (header_row + 1)

    # 3. Assemble composite column names
    for c in range(1, max_c + 1):
        top_val = get_merged_cell_value(ws, header_row, c)
        if has_sub_header:
            sub_val = get_merged_cell_value(ws, sub_row, c)
            if top_val and sub_val and str(top_val).strip() != str(sub_val).strip():
                headers[c] = f"{str(top_val).strip()} - {str(sub_val).strip()}"
            elif top_val:
                headers[c] = str(top_val).strip()
            elif sub_val:
                headers[c] = str(sub_val).strip()
        else:
            if top_val:
                headers[c] = str(top_val).strip()

    return header_row, data_start_row, headers


def analyze_sheet(ws: Worksheet, sheet_index: int) -> SheetAnalysis:
    """Analyzes an individual sheet, extracting column models, sections, and requirements."""
    sheet_name = ws.title
    max_r = ws.max_row or 0
    max_c = ws.max_column or 0

    header_row, data_start_row, raw_headers = detect_headers(ws)
    if header_row is None:
        return {
            "sheet_name": sheet_name,
            "sheet_index": sheet_index,
            "max_row": max_r,
            "max_column": max_c,
            "header_row": 0,
            "data_start_row": 1,
            "columns": [],
            "requirements": [],
        }

    # Build Classified Columns
    columns: list[DetectedColumn] = []
    col_types: dict[int, str] = {}
    req_col: int | None = None

    for col_idx, h_text in raw_headers.items():
        c_type = classify_column_header(h_text)
        col_types[col_idx] = c_type
        columns.append({
            "column_index": col_idx,
            "column_letter": get_column_letter(col_idx),
            "header_name": h_text,
            "column_type": c_type,
        })
        if c_type == "requirement" and req_col is None:
            req_col = col_idx

    # If no explicit requirement column detected, pick first candidate text column
    if req_col is None:
        candidate_cols: list[int] = []
        for col_idx in sorted(raw_headers.keys()):
            if col_types.get(col_idx) not in ("index", "compliance", "marks", "total_marks", "remarks", "answer"):
                candidate_cols.append(col_idx)

        if len(candidate_cols) == 1:
            req_col = candidate_cols[0]
        elif len(candidate_cols) > 1:
            # Pick candidate column with longest average text length in first 20 data rows
            best_col = candidate_cols[0]
            max_avg_len = -1.0
            for c in candidate_cols:
                lengths: list[int] = []
                for r_scan in range(data_start_row, min(data_start_row + 20, max_r + 1)):
                    v = get_merged_cell_value(ws, r_scan, c)
                    if v is not None and isinstance(v, str):
                        lengths.append(len(v.strip()))
                avg_len = (sum(lengths) / len(lengths)) if lengths else 0.0
                if avg_len > max_avg_len:
                    max_avg_len = avg_len
                    best_col = c
            req_col = best_col
        else:
            req_col = 1

    # Extract Requirements & Fillable Target Slots
    parsed_reqs: list[ParsedRequirement] = []
    current_section: str | None = None
    req_counter = 1

    for r in range(data_start_row, max_r + 1):
        row_vals = [get_merged_cell_value(ws, r, c) for c in range(1, max_c + 1)]
        non_empty = [v for v in row_vals if v is not None and str(v).strip()]
        if not non_empty:
            continue  # Skip blank row

        distinct_non_empty = set(non_empty)

        # Check for section banner row (merged across columns or explicit section heading outside req_col)
        # Note: Do NOT mistake an unfilled requirement row (where target slots are empty) for a banner!
        is_merged_banner = any(
            rng.min_row <= r <= rng.max_row and (rng.max_col - rng.min_col >= 2)
            for rng in ws.merged_cells.ranges
        )
        val_in_req_col = get_merged_cell_value(ws, r, req_col)

        if len(distinct_non_empty) == 1 and not any(isinstance(v, (int, float)) for v in non_empty):
            banner_val = str(next(iter(distinct_non_empty))).strip()
            is_section_keyword = bool(
                re.match(r"^(?:section|part|category|annex|appendix|module|clause)\b", banner_val, re.IGNORECASE)
            )
            has_spec_verbs = bool(
                re.search(r"\b(?:must|shall|should|require|required|minimum|delivers?|supports?|provides?|includes?)\b", banner_val, re.IGNORECASE)
            )

            # Classify as banner if:
            # 1. Row is merged across multiple columns without spec verbs, OR
            # 2. Text is NOT in requirement column and is concise/section-like, OR
            # 3. Explicit section keyword without spec verbs
            is_banner = False
            if is_merged_banner and not has_spec_verbs and not banner_val.endswith("?"):
                is_banner = True
            elif val_in_req_col is None and (is_section_keyword or len(banner_val) < 60) and not banner_val.endswith("?"):
                is_banner = True
            elif is_section_keyword and not has_spec_verbs and len(banner_val) < 80 and not banner_val.endswith("?"):
                is_banner = True

            if is_banner:
                if len(banner_val) > 2:
                    current_section = banner_val
                continue

        req_text_val = get_merged_cell_value(ws, r, req_col)
        req_text = str(req_text_val).strip() if req_text_val is not None else ""

        if not req_text:
            continue

        # Map Target Slots for this requirement row
        target_slots: dict[str, TargetSlot] = {}
        for c in range(1, max_c + 1):
            c_type = col_types.get(c, "unknown")
            if c_type in ("compliance", "answer", "remarks", "marks"):
                raw_cell = ws.cell(row=r, column=c)
                val = get_merged_cell_value(ws, r, c)
                val_str = str(val).strip() if val is not None else None

                # Check if cell contains an existing Excel formula (e.g. =IF(...) in marks column)
                raw_val = raw_cell.value
                has_formula = isinstance(raw_val, str) and raw_val.startswith("=")
                formula_str = raw_val if has_formula and isinstance(raw_val, str) else None

                slot_key = c_type if c_type not in target_slots else f"{c_type}_{c}"
                target_slots[slot_key] = {
                    "slot_type": c_type,
                    "header_name": raw_headers.get(c, ""),
                    "column_letter": get_column_letter(c),
                    "column_index": c,
                    "cell_coordinate": f"{get_column_letter(c)}{r}",
                    "current_value": val_str,
                    "has_formula": has_formula,
                    "formula": formula_str,
                }

        req_id = f"REQ-S{sheet_index:02d}-R{req_counter:03d}"
        source_coord = f"{get_column_letter(req_col)}{r}"

        parsed_reqs.append({
            "requirement_id": req_id,
            "sheet_name": sheet_name,
            "row_number": r,
            "section": current_section,
            "requirement_text": req_text,
            "source_cell": source_coord,
            "target_slots": target_slots,
        })
        req_counter += 1

    return {
        "sheet_name": sheet_name,
        "sheet_index": sheet_index,
        "max_row": max_r,
        "max_column": max_c,
        "header_row": header_row,
        "data_start_row": data_start_row,
        "columns": columns,
        "requirements": parsed_reqs,
    }


def parse_excel_workbook(excel_path: Path) -> WorkbookAnalysis:
    """Parses an Excel workbook into structured WorkbookAnalysis representation."""
    with open(excel_path, "rb") as f:
        file_bytes = f.read()
    file_hash = hashlib.sha256(file_bytes).hexdigest()[:16]

    wb = openpyxl.load_workbook(excel_path, data_only=False)
    sheet_analyses: list[SheetAnalysis] = []
    total_reqs = 0

    for idx, name in enumerate(wb.sheetnames, start=1):
        ws = wb[name]
        if not isinstance(ws, Worksheet):
            continue
        sheet_result = analyze_sheet(ws, idx)
        sheet_analyses.append(sheet_result)
        total_reqs += len(sheet_result["requirements"])

    wb.close()

    return {
        "workbook_id": excel_path.stem,
        "source_file": str(excel_path.resolve()),
        "file_hash": file_hash,
        "sheet_names": wb.sheetnames,
        "sheets": sheet_analyses,
        "total_requirements": total_reqs,
    }


def export_questions_list(analysis: WorkbookAnalysis) -> list[dict[str, str]]:
    """Exports a flattened list of candidate requirements for probe search and matching."""
    questions: list[dict[str, str]] = []
    for s in analysis["sheets"]:
        for r in s["requirements"]:
            questions.append({
                "requirement_id": r["requirement_id"],
                "sheet_name": r["sheet_name"],
                "row_number": str(r["row_number"]),
                "section": r["section"] or "",
                "requirement_text": r["requirement_text"],
                "source_cell": r["source_cell"],
            })
    return questions


def main() -> None:
    parser = argparse.ArgumentParser(description="Step 2: Dynamic Excel Workbook Analyzer")
    parser.add_argument(
        "--excel",
        "-e",
        type=Path,
        required=True,
        help="Path to Excel (.xlsx) file",
    )
    parser.add_argument(
        "--output-analysis",
        "-o",
        type=Path,
        default=Path("data/generated/excel_analysis.json"),
        help="Path to save workbook analysis JSON",
    )
    parser.add_argument(
        "--output-questions",
        "-q",
        type=Path,
        default=Path("data/generated/excel_questions.json"),
        help="Path to save flattened requirements list JSON",
    )
    args = parser.parse_args()

    if not args.excel.exists():
        print(f"  [ERROR] Excel file not found: {args.excel}")
        return

    print(f"\nAnalyzing Excel Workbook: {args.excel}")
    analysis = parse_excel_workbook(args.excel)
    questions = export_questions_list(analysis)

    # Save inspectable artifacts (Rule 8)
    with open(args.output_analysis, "w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)

    with open(args.output_questions, "w", encoding="utf-8") as f:
        json.dump(questions, f, indent=2, ensure_ascii=False)

    print(f"  [SUCCESS] Workbook Analysis: {len(analysis['sheets'])} sheet(s), {analysis['total_requirements']} requirement(s)")
    print(f"  -> Saved analysis:  {args.output_analysis.resolve()}")
    print(f"  -> Saved questions: {args.output_questions.resolve()}\n")


analyze_workbook = parse_excel_workbook

if __name__ == "__main__":
    main()

