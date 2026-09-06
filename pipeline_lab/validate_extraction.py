#!/usr/bin/env python3
"""
Automated Extraction Validator:
1. Ghost Page & Health Check (Automated Invariants)
2. Automated Ground Truth Probing (Reverse Keyword Test with Synonyms & Alternative Evidence)
3. Dynamic Excel-driven probe loading (when --excel is passed)
4. 1-Page Summary Dashboard with OCR, Word Count, and Page Metrics
"""

import argparse
import json
import re
from pathlib import Path
from typing import TypedDict


class PageCheck(TypedDict):
    page_number: int
    char_count: int
    word_count: int
    table_count: int
    is_ghost_page: bool  # Text < 50 chars, likely image/scanned


class TableCheck(TypedDict):
    table_id: str
    page_number: int
    header_cols: int
    row_count: int
    has_column_mismatch: bool


class ProbeResult(TypedDict):
    term: str
    found: bool
    occurrences: int
    found_on_pages: list[int]
    found_in_tables: list[str]
    match_type: str  # "EXACT", "SYNONYM", "ALTERNATIVE_FOUND", "MISSING"
    evidence_note: str


class OcrPageSummary(TypedDict):
    page_number: int
    words: int
    chars: int


class ValidationReport(TypedDict):
    document_id: str
    total_pages: int
    extracted_text_pages: int
    total_words: int
    total_chars: int
    total_tables: int
    total_images: int
    ocr_used: bool
    ocr_chars: int
    ocr_words: int
    ocr_pages_detail: list[OcrPageSummary]
    ghost_pages: list[int]
    corrupted_char_count: int
    table_issues: list[str]
    probe_results: list[ProbeResult]
    overall_status: str  # "HEALTHY" or "ATTENTION_REQUIRED"


TECHNICAL_SYNONYMS: dict[str, list[str]] = {
    "cpu load": ["cpu usage", "cpu utilization", "processor load", "processor usage"],
    "cpu usage": ["cpu load", "cpu utilization"],
    "memory": ["ram", "dimm", "ddr5", "ddr4"],
    "storage": ["nvme", "san", "raw capacity", "ssd"],
    "fc ports": ["fibre channel", "fiber channel", "fc port", "fc ports"],
    "operating system": ["os", "linux", "rhel", "ubuntu", "windows server"],
}


def find_alternative_evidence(doc_text: str, term: str) -> str | None:
    """Searches for related hardware family in document if an exact model is missing."""
    term_lower = term.lower()

    # 1. Check Xeon / Processor variants
    if "xeon" in term_lower or "cpu" in term_lower or "processor" in term_lower:
        match = re.search(
            r"Xeon\s+[A-Za-z0-9\-\s]{3,25}(?:6747P|6740P|6710E|\d{4}[A-Z]?)",
            doc_text,
            re.IGNORECASE,
        )
        if match:
            clean_m = " ".join(match.group(0).split())
            return f"Alternative CPU in PDF: '{clean_m}'"

    # 2. Check Server Model / Chassis variants
    if "as-" in term_lower or "sys-" in term_lower or "server" in term_lower:
        match = re.search(r"(?:SYS|SSG|SMC|X14|H13)[\w\-]+", doc_text)
        if match:
            return f"Server quoted in PDF: '{match.group(0)}' (Intel solution)"

    # 3. Check GPU / Accelerator variants
    if "gpu" in term_lower or "nvidia" in term_lower or "h100" in term_lower or "l40" in term_lower:
        match = re.search(r"(?:NVIDIA|PCIe|GPU)[\w\-\s]{2,20}", doc_text, re.IGNORECASE)
        if match:
            clean_m = " ".join(match.group(0).split())
            return f"GPU reference in PDF: '{clean_m}'"

    return None


def extract_probe_terms_from_excel(excel_path: Path) -> list[str]:
    """Extracts candidate requirement terms/questions from an Excel sheet."""
    try:
        import openpyxl

        wb = openpyxl.load_workbook(excel_path, read_only=True, data_only=True)
        sheet = wb.active
        terms: list[str] = []
        if sheet is not None:
            for row in sheet.iter_rows(values_only=True):
                for cell in row:
                    if cell and isinstance(cell, str) and 3 < len(cell.strip()) < 100:
                        val = cell.strip()
                        if not val.lower().startswith(
                            ("sl", "no", "item", "s.no", "description", "specification")
                        ):
                            terms.append(val)
                            break
        wb.close()
        return terms[:25]
    except Exception as e:
        print(f"  [WARN] Failed to extract probe terms from Excel: {e}")
        return []


def run_health_checks(
    doc_data: dict[str, object],
) -> tuple[list[PageCheck], list[TableCheck], list[int], int, list[str]]:
    """Evaluates page continuity, text density, and table row alignments."""
    pages_raw = doc_data.get("pages", [])
    if not isinstance(pages_raw, list):
        pages_raw = []

    page_checks: list[PageCheck] = []
    table_checks: list[TableCheck] = []
    ghost_pages: list[int] = []
    table_issues: list[str] = []
    corrupted_chars = 0

    for idx, p in enumerate(pages_raw, start=1):
        if not isinstance(p, dict):
            continue

        p_num = int(p.get("page_number", idx))
        text = str(p.get("text", ""))
        tables = p.get("tables", [])
        if not isinstance(tables, list):
            tables = []

        # Check for corrupted Unicode characters
        corrupted_chars += text.count("\ufffd") + text.count("\x00")

        # Ghost Page Detection: Less than 50 characters of text
        is_ghost = len(text.strip()) < 50
        if is_ghost:
            ghost_pages.append(p_num)

        page_checks.append({
            "page_number": p_num,
            "char_count": len(text),
            "word_count": len(text.split()),
            "table_count": len(tables),
            "is_ghost_page": is_ghost,
        })

        # Table Grid Invariants
        for t in tables:
            if not isinstance(t, dict):
                continue
            t_id = str(t.get("table_id", f"T{p_num:02d}"))
            headers = t.get("headers", [])
            rows = t.get("rows", [])
            if not isinstance(headers, list) or not isinstance(rows, list):
                continue

            num_headers = len(headers)
            has_mismatch = False

            if num_headers == 0 and len(rows) > 0:
                has_mismatch = True
                table_issues.append(f"{t_id}: Missing table headers")

            for r_idx, row in enumerate(rows, start=1):
                if isinstance(row, list) and len(row) != num_headers:
                    has_mismatch = True
                    table_issues.append(
                        f"{t_id} Row {r_idx}: Column count ({len(row)}) != headers ({num_headers})"
                    )
                    break

            table_checks.append({
                "table_id": t_id,
                "page_number": p_num,
                "header_cols": num_headers,
                "row_count": len(rows),
                "has_column_mismatch": has_mismatch,
            })

    return page_checks, table_checks, ghost_pages, corrupted_chars, table_issues


def probe_ground_truth(
    doc_data: dict[str, object], search_terms: list[str]
) -> list[ProbeResult]:
    """Automated Reverse Test: checks if expected technical keywords exist in JSON."""
    pages_raw = doc_data.get("pages", [])
    if not isinstance(pages_raw, list):
        pages_raw = []

    # Build full document text cache for alternative evidence search
    all_text_snippets: list[str] = []
    for p in pages_raw:
        if isinstance(p, dict):
            all_text_snippets.append(str(p.get("text", "")))
            ocr_items = p.get("ocr", [])
            if isinstance(ocr_items, list):
                for ocr_str in ocr_items:
                    all_text_snippets.append(str(ocr_str))
            tables = p.get("tables", [])
            if isinstance(tables, list):
                for tbl in tables:
                    all_text_snippets.append(json.dumps(tbl))
    full_doc_text = "\n".join(all_text_snippets)

    results: list[ProbeResult] = []

    for term in search_terms:
        clean_term = term.strip()
        if not clean_term:
            continue

        target = clean_term.lower()
        found_pages: list[int] = []
        found_tables: list[str] = []
        total_occurrences = 0

        for idx, p in enumerate(pages_raw, start=1):
            if not isinstance(p, dict):
                continue
            p_num = int(p.get("page_number", idx))
            text = str(p.get("text", "")).lower()

            # Search in text
            text_matches = text.count(target)
            if text_matches > 0:
                found_pages.append(p_num)
                total_occurrences += text_matches

            # Search in tables
            tables = p.get("tables", [])
            if isinstance(tables, list):
                for t in tables:
                    if not isinstance(t, dict):
                        continue
                    t_id = str(t.get("table_id", ""))
                    t_str = json.dumps(t).lower()
                    t_matches = t_str.count(target)
                    if t_matches > 0:
                        found_tables.append(t_id)
                        total_occurrences += t_matches

            # Search in OCR text from images/diagrams
            ocr_entries = p.get("ocr", [])
            if isinstance(ocr_entries, list):
                for ocr_item in ocr_entries:
                    ocr_matches = str(ocr_item).lower().count(target)
                    if ocr_matches > 0:
                        found_pages.append(p_num)
                        total_occurrences += ocr_matches

        # Determine match type and evidence note
        if total_occurrences > 0:
            match_type = "EXACT"
            page_count = len(set(found_pages))
            evidence_note = f"Found {total_occurrences} match(es) across {page_count} page(s)"
            is_found = True
        else:
            # 1. Check synonyms
            synonyms = TECHNICAL_SYNONYMS.get(target, [])
            syn_found = False
            for syn in synonyms:
                syn_target = syn.lower()
                for idx, p in enumerate(pages_raw, start=1):
                    if not isinstance(p, dict):
                        continue
                    p_num = int(p.get("page_number", idx))
                    p_full = (
                        str(p.get("text", ""))
                        + " "
                        + " ".join(str(x) for x in p.get("ocr", []))
                    ).lower()
                    if syn_target in p_full:
                        found_pages.append(p_num)
                        total_occurrences += p_full.count(syn_target)
                        syn_found = True
                if syn_found:
                    match_type = "SYNONYM"
                    evidence_note = f"Matched synonym '{syn}' on {len(set(found_pages))} page(s)"
                    is_found = True
                    break

            if not syn_found:
                # 2. Check for alternative evidence (e.g. Xeon 6747P instead of 6710E)
                alt_evidence = find_alternative_evidence(full_doc_text, clean_term)
                if alt_evidence:
                    match_type = "ALTERNATIVE_FOUND"
                    evidence_note = alt_evidence
                    is_found = False
                else:
                    match_type = "MISSING"
                    evidence_note = "Not present in PDF (Rule 7: NOT_SPECIFIED)"
                    is_found = False

        results.append({
            "term": clean_term,
            "found": is_found,
            "occurrences": total_occurrences,
            "found_on_pages": sorted(list(set(found_pages))),
            "found_in_tables": sorted(list(set(found_tables))),
            "match_type": match_type,
            "evidence_note": evidence_note,
        })

    return results


def print_dashboard(report: ValidationReport) -> None:
    """Renders the 1-page high-visibility summary dashboard."""
    sep = "=" * 68
    sub_sep = "-" * 68

    print(f"\n{sep}")
    print("        AUTOMATED PDF EXTRACTION HEALTH DASHBOARD")
    print(f"{sep}")
    print(f"  Document ID:        {report['document_id']}")
    print(f"  Overall Status:     [{report['overall_status']}]")
    print(
        f"  Total Ingested:     {report['total_pages']} pages ({report['extracted_text_pages']} with text)"
    )
    print(
        f"  Total Volume:       {report['total_words']:,} words | {report['total_chars']:,} characters"
    )
    print(f"  Total Tables:       {report['total_tables']} tables detected")
    ocr_status_str = (
        f"Active ({report['ocr_chars']} chars from images)"
        if report["ocr_used"]
        else "Not Used (Native Digital PDF)"
    )
    print(f"  OCR Status:         {ocr_status_str}")
    print(f"  Corrupted Chars:    {report['corrupted_char_count']}")
    print(f"{sub_sep}")

    # 1. Ghost Page / Density Check
    ghosts = report["ghost_pages"]
    ocr_details = report.get("ocr_pages_detail", [])
    if not ghosts:
        print("  1. GHOST PAGE CHECK:  [PASS] Zero empty or ghost pages detected.")
    else:
        print(
            f"  1. GHOST PAGE CHECK:  [!] {len(ghosts)} image-heavy/low-text page(s) flagged:"
        )
        ghost_str = ", ".join(f"Page {p}" for p in ghosts[:10])
        print(f"     Flagged Pages:    [{ghost_str}]")
        if ocr_details:
            for op in ocr_details:
                print(
                    f"     OCR Executed:     Page {op['page_number']} -> {op['words']} words ({op['chars']} chars) extracted from diagram/image."
                )
        else:
            print("     Action Needed:    Review if these pages require OCR.")

    print(f"{sub_sep}")

    # 2. Table Invariant Check
    issues = report["table_issues"]
    if not issues:
        print("  2. TABLE ALIGNMENT:   [PASS] 100% of tables have aligned columns & headers.")
    else:
        print(f"  2. TABLE ALIGNMENT:   [!] {len(issues)} table issue(s) detected:")
        for iss in issues[:4]:
            print(f"     * {iss}")
        if len(issues) > 4:
            print(f"     * ... and {len(issues) - 4} more")

    print(f"{sub_sep}")

    # 3. Ground Truth Probing (Reverse Test)
    probes = report["probe_results"]
    if probes:
        print("  3. TARGET SPEC CHECK (Keyword Reverse Probing & Evidence):")
        for pr in probes:
            status_tag = f"[{pr['match_type']}]"
            loc_details: list[str] = []
            if pr["found_on_pages"]:
                loc_details.append(f"Pages {pr['found_on_pages'][:4]}")
            if pr["found_in_tables"]:
                loc_details.append(f"Tables {pr['found_in_tables'][:3]}")

            loc_str = " | " + ", ".join(loc_details) if loc_details else ""
            print(
                f"     {status_tag:<20} '{pr['term']}': {pr['evidence_note']}{loc_str}"
            )
    else:
        print("  3. TARGET SPEC CHECK: No test terms provided (use --probe or --excel).")

    print(f"{sep}\n")


def validate(json_path: Path, search_terms: list[str]) -> ValidationReport:
    """Executes validation pipeline and returns structured report."""
    with open(json_path, "r", encoding="utf-8") as f:
        doc_data: dict[str, object] = json.load(f)

    doc_id = str(doc_data.get("document_id", json_path.stem))
    pages_raw_val = doc_data.get("pages", [])
    pages_list_len = len(pages_raw_val) if isinstance(pages_raw_val, list) else 0
    total_pages_val = doc_data.get("total_pages")
    total_pages = (
        int(total_pages_val)
        if isinstance(total_pages_val, (int, str))
        else pages_list_len
    )

    pages_raw = doc_data.get("pages", [])
    total_chars = 0
    total_words = 0
    extracted_text_pages = 0
    ocr_chars = 0
    ocr_words = 0
    ocr_used = False
    ocr_pages_detail: list[OcrPageSummary] = []
    total_images = 0

    if isinstance(pages_raw, list):
        for p in pages_raw:
            if isinstance(p, dict):
                p_num = int(p.get("page_number", 0))
                text = str(p.get("text", ""))
                if text.strip():
                    total_chars += len(text)
                    total_words += len(text.split())
                    extracted_text_pages += 1

                # Check OCR
                ocr_entries = p.get("ocr", [])
                p_ocr_chars = 0
                p_ocr_words = 0
                if isinstance(ocr_entries, list) and ocr_entries:
                    for ocr_item in ocr_entries:
                        ocr_str = str(ocr_item)
                        if ocr_str.strip():
                            ocr_used = True
                            p_ocr_chars += len(ocr_str)
                            p_ocr_words += len(ocr_str.split())
                    if p_ocr_chars > 0:
                        ocr_chars += p_ocr_chars
                        ocr_words += p_ocr_words
                        ocr_pages_detail.append({
                            "page_number": p_num,
                            "words": p_ocr_words,
                            "chars": p_ocr_chars,
                        })

                # Check Images
                images = p.get("images", [])
                if isinstance(images, list):
                    total_images += len(images)

    _page_checks, table_checks, ghost_pages, corrupted_chars, table_issues = run_health_checks(
        doc_data
    )
    probe_results = probe_ground_truth(doc_data, search_terms)

    # Calculate overall health status
    missing_probes = sum(1 for pr in probe_results if not pr["found"])
    if corrupted_chars == 0 and len(table_issues) == 0 and missing_probes == 0:
        overall_status = "HEALTHY"
    else:
        overall_status = "ATTENTION_REQUIRED"

    report: ValidationReport = {
        "document_id": doc_id,
        "total_pages": total_pages,
        "extracted_text_pages": extracted_text_pages,
        "total_words": total_words,
        "total_chars": total_chars,
        "total_tables": len(table_checks),
        "total_images": total_images,
        "ocr_used": ocr_used,
        "ocr_chars": ocr_chars,
        "ocr_words": ocr_words,
        "ocr_pages_detail": ocr_pages_detail,
        "ghost_pages": ghost_pages,
        "corrupted_char_count": corrupted_chars,
        "table_issues": table_issues,
        "probe_results": probe_results,
        "overall_status": overall_status,
    }

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Automated PDF Extraction Validator")
    parser.add_argument(
        "--json",
        "-j",
        type=Path,
        default=Path("pipeline_lab/reference_pdf_output.json"),
        help="Path to extracted PDF JSON file",
    )
    parser.add_argument(
        "--probe",
        "-p",
        type=str,
        default="SYS-222C-TN,Xeon 6710E,NVMe,AS-7018,350 TB,Techaccess,CPU Load",
        help="Comma-separated list of target keywords to reverse probe",
    )
    parser.add_argument(
        "--excel",
        "-e",
        type=Path,
        default=None,
        help="Optional path to Excel RFP to auto-extract probe terms",
    )
    parser.add_argument(
        "--save-report",
        "-s",
        type=Path,
        default=Path("pipeline_lab/validation_report.json"),
        help="Path to save validation report JSON",
    )
    args = parser.parse_args()

    target_json = args.json
    if not target_json.exists() and Path("reference_pdf_output.json").exists():
        target_json = Path("reference_pdf_output.json")

    # If Excel path provided, load terms from Excel
    if args.excel and args.excel.exists():
        print(f"Auto-extracting probe terms from Excel: {args.excel}")
        search_terms = extract_probe_terms_from_excel(args.excel)
        if not search_terms:
            search_terms = [t.strip() for t in args.probe.split(",") if t.strip()]
    else:
        search_terms = [t.strip() for t in args.probe.split(",") if t.strip()]

    report = validate(target_json, search_terms)
    print_dashboard(report)

    # Save report
    with open(args.save_report, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
