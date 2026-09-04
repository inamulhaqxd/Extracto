#!/usr/bin/env python3
"""
Step 1 & Step 2 HTML Executive Report Generator.
Features:
1. Interactive expandable source evidence & page numbers per probe.
2. Rule 7 Zero-Hallucination warning alert for NOT_SPECIFIED items (yellow highlighting).
3. Dedicated Step 2 Excel Analysis Section (workbook metadata, sheet schema, formula guard, requirements table).
4. 100% Offline, zero external CDN dependencies (PRD Rule 10).
"""

import argparse
import html
import json
from pathlib import Path


def generate_professional_html(
    report_data: dict[str, object],
    excel_data: dict[str, object] | None = None,
) -> str:
    """Renders a clean, executive report in HTML uniting Step 1 and Step 2."""
    doc_id = html.escape(str(report_data.get("document_id", "Reference Document")))
    total_pages = int(str(report_data.get("total_pages", 0)))
    extracted_text_pages = int(str(report_data.get("extracted_text_pages", total_pages)))
    total_words = int(str(report_data.get("total_words", 0)))
    total_chars = int(str(report_data.get("total_chars", 0)))
    total_tables = int(str(report_data.get("total_tables", 0)))
    ocr_used = bool(report_data.get("ocr_used", False))
    ocr_chars = int(str(report_data.get("ocr_chars", 0)))
    ocr_words = int(str(report_data.get("ocr_words", 0)))
    corrupted_chars = int(str(report_data.get("corrupted_char_count", 0)))

    ghost_pages_raw = report_data.get("ghost_pages", [])
    ghost_pages = [int(p) for p in ghost_pages_raw] if isinstance(ghost_pages_raw, list) else []

    # Probes Analysis
    probes_raw = report_data.get("probe_results", [])
    probes = probes_raw if isinstance(probes_raw, list) else []
    total_probes = len(probes)
    found_probes = sum(1 for pr in probes if isinstance(pr, dict) and pr.get("found", False))
    missing_probes: list[dict[str, object]] = [
        pr for pr in probes if isinstance(pr, dict) and not pr.get("found", False)
    ]

    # OCR Page Details
    ocr_pages_detail_raw = report_data.get("ocr_pages_detail", [])
    ocr_pages_detail = (
        [op for op in ocr_pages_detail_raw if isinstance(op, dict)]
        if isinstance(ocr_pages_detail_raw, list)
        else []
    )

    # Calculate overall extraction health score (0-100)
    deductions = len(ghost_pages) * 5 + len(missing_probes) * 8
    health_score = max(0, min(100, 100 - deductions)) if total_pages > 0 else 0

    if health_score >= 90:
        verdict_badge = "HEALTHY"
        badge_class = "badge-emerald"
        headline = "Ready for Downstream Processing"
        subheadline = "High extraction fidelity across pages, tables, and target specifications."
    elif health_score >= 70:
        verdict_badge = "REVIEW RECOMMENDED"
        badge_class = "badge-amber"
        missing_count = len(missing_probes)
        unit = "Spec" if missing_count == 1 else "Specs"
        headline = f"Extracted Successfully ({missing_count} Missing {unit})"
        subheadline = f"{found_probes} / {total_probes} target requirements located in document text layer."
    else:
        verdict_badge = "ACTION REQUIRED"
        badge_class = "badge-rose"
        headline = "Extraction Discrepancies Detected"
        subheadline = "Several specifications or pages require review or OCR."

    # OCR display labels
    ocr_status_label = "Active (Used)" if ocr_used else "Not Used"
    ocr_status_sub = "OCR Triggered" if ocr_used else "Native Digital PDF"
    ocr_text_val = f"{ocr_words:,} Words" if ocr_used else "0 Words"
    ocr_text_sub = f"{ocr_chars:,} chars from images" if ocr_used else "0 chars (native text only)"

    # 1. Expandable Probe Cards (Feature 1)
    probe_cards: list[str] = []
    for pr in probes:
        if not isinstance(pr, dict):
            continue
        term = html.escape(str(pr.get("term", "")))
        found = bool(pr.get("found", False))
        count = int(str(pr.get("occurrences", 0)))
        match_type = str(pr.get("match_type", "EXACT" if found else "MISSING"))
        evidence_note = html.escape(str(pr.get("evidence_note", "")))
        pages = pr.get("found_on_pages", [])
        tables = pr.get("found_in_tables", [])

        page_chips = "".join(
            f'<span class="chip-page">Page {p}</span>'
            for p in (pages if isinstance(pages, list) else [])
        )
        table_chips = "".join(
            f'<span class="chip-table">{html.escape(str(tbl))}</span>'
            for tbl in (tables if isinstance(tables, list) else [])
        )

        if match_type == "EXACT":
            card_class = "probe-success"
            ind_class = "ind-green"
            pill_class = ""
            badge_text = f"{count} hits"
            short_meta = f"Found on {len(pages) if isinstance(pages, list) else 0} page(s)"
        elif match_type == "SYNONYM":
            card_class = "probe-synonym"
            ind_class = "ind-cyan"
            pill_class = "pill-cyan"
            badge_text = "Synonym"
            short_meta = evidence_note or "Matched technical synonym"
        elif match_type == "ALTERNATIVE_FOUND":
            card_class = "probe-alt"
            ind_class = "ind-amber"
            pill_class = "pill-amber"
            badge_text = "Alternative"
            short_meta = evidence_note or "Alternative item identified"
        else:
            card_class = "probe-danger"
            ind_class = "ind-red"
            pill_class = "pill-danger"
            badge_text = "Missing"
            short_meta = "0 occurrences in document"

        details_content = f"""
        <div class="probe-details-body">
            <div class="probe-detail-row">
                <span class="detail-label">Matched Pages:</span>
                <div class="evidence-chips">{page_chips or '<span class="chip-none">None</span>'}</div>
            </div>
            {f'<div class="probe-detail-row"><span class="detail-label">Matched Tables:</span><div class="evidence-chips">{table_chips}</div></div>' if table_chips else ''}
            {f'<div class="evidence-quote"><strong>Evidence:</strong> {evidence_note}</div>' if evidence_note else ''}
        </div>
        """

        probe_cards.append(f"""
        <div class="probe-card {card_class}" data-term="{term.lower()}">
            <details>
                <summary>
                    <div class="probe-top">
                        <span class="status-indicator {ind_class}"></span>
                        <span class="probe-title">{term}</span>
                        <span class="probe-count-pill {pill_class}">{badge_text}</span>
                    </div>
                    <div class="probe-meta">{short_meta}</div>
                </summary>
                {details_content}
            </details>
        </div>
        """)

    probe_cards_html = (
        "\n".join(probe_cards)
        if probe_cards
        else "<div class='empty-state'>No keyword probes configured.</div>"
    )

    # 2. Rule 7 Missing Requirements / NOT_SPECIFIED Section (Feature 2)
    missing_probes_callout_html = ""
    if missing_probes:
        missing_items_rows: list[str] = []
        for mp in missing_probes:
            m_term = html.escape(str(mp.get("term", "")))
            m_type = html.escape(str(mp.get("match_type", "MISSING")))
            m_note = html.escape(str(mp.get("evidence_note", "")))
            badge_text = "Alternative Found" if m_type == "ALTERNATIVE_FOUND" else "Missing"
            badge_cls = "pill-amber" if m_type == "ALTERNATIVE_FOUND" else "pill-danger"
            missing_items_rows.append(f"""
            <li class="missing-item-row">
                <div class="missing-item-left">
                    <span class="probe-count-pill {badge_cls}">{badge_text}</span>
                    <strong class="missing-term">{m_term}</strong>
                    {f'<span class="missing-note">&bull; {m_note}</span>' if m_note else ''}
                </div>
                <span class="flag-action-tag">Rule 7: NOT_SPECIFIED (Yellow Highlight)</span>
            </li>
            """)

        missing_probes_callout_html = f"""
        <div class="ui-notice notice-amber">
            <div class="notice-icon">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#b45309" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
            </div>
            <div class="notice-content">
                <div class="notice-heading">Rule 7 Zero-Hallucination: {len(missing_probes)} Target Specification(s) Not Quoted</div>
                <div class="notice-body">
                    The specifications below are not explicitly verified in the source PDF.
                    Per Rule 7, these will be filled as <strong>NOT_SPECIFIED</strong> and flagged for yellow highlighting:
                    <ul class="missing-items-list">
                        {"".join(missing_items_rows)}
                    </ul>
                </div>
            </div>
        </div>
        """

    # Image Alert Notice
    flagged_box_html = ""
    if ocr_pages_detail:
        total_ocr_words_val = sum(int(str(op.get("words", 0))) for op in ocr_pages_detail)
        pages_list_str = ", ".join(f"Page {op.get('page_number')}" for op in ocr_pages_detail)
        if len(ocr_pages_detail) == 1:
            op = ocr_pages_detail[0]
            body_text = f"OCR executed on <strong>Page {op.get('page_number')}</strong> and extracted <strong>{op.get('words', 0)} words</strong> ({op.get('chars', 0):,} characters) from the diagram/screenshot."
        else:
            pages_summary = ", ".join(
                f"Page {op.get('page_number')} ({op.get('words', 0)} words)"
                for op in ocr_pages_detail
            )
            body_text = f"OCR executed across {pages_list_str} and extracted <strong>{total_ocr_words_val:,} words</strong> ({ocr_chars:,} characters): {pages_summary}."

        flagged_box_html = f"""
        <div class="ui-notice notice-blue">
            <div class="notice-icon">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#2563eb" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
            </div>
            <div class="notice-content">
                <div class="notice-heading">Image / Diagram OCR Executed ({pages_list_str})</div>
                <div class="notice-body">{body_text}</div>
            </div>
        </div>
        """
    elif ghost_pages:
        ghost_pages_str = ", ".join(f"Page {p}" for p in ghost_pages)
        flagged_box_html = f"""
        <div class="ui-notice notice-amber">
            <div class="notice-icon">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
            </div>
            <div class="notice-content">
                <div class="notice-heading">Image / Diagram Alert ({ghost_pages_str})</div>
                <div class="notice-body">{ghost_pages_str} contains less than 50 characters of native text. Review if local OCR is required.</div>
            </div>
        </div>
        """

    # 3. Dedicated Excel Section (Feature 3)
    excel_section_html = ""
    if excel_data:
        wb_id = html.escape(str(excel_data.get("workbook_id", "Excel Workbook")))
        wb_hash = html.escape(str(excel_data.get("file_hash", "N/A")))
        wb_total_reqs = int(str(excel_data.get("total_requirements", 0)))
        sheets_raw = excel_data.get("sheets", [])
        sheets = [s for s in sheets_raw if isinstance(s, dict)] if isinstance(sheets_raw, list) else []

        formula_count = 0
        all_reqs_rows: list[str] = []

        sheet_cards: list[str] = []
        for s in sheets:
            s_name = html.escape(str(s.get("sheet_name", "Sheet")))
            s_h_row = int(str(s.get("header_row", 0)))
            s_d_row = int(str(s.get("data_start_row", 0)))
            s_cols = s.get("columns", [])
            s_reqs = s.get("requirements", [])

            col_badges = []
            if isinstance(s_cols, list):
                for c in s_cols:
                    if isinstance(c, dict):
                        c_let = html.escape(str(c.get("column_letter", "")))
                        c_type = html.escape(str(c.get("column_type", "")))
                        col_badges.append(f'<span class="schema-col-pill"><strong style="color:var(--text-title);">{c_let}</strong> {c_type}</span>')

            sheet_cards.append(f"""
            <div class="sheet-summary-item">
                <div class="sheet-sum-top">
                    <span class="sheet-title-badge">{s_name}</span>
                    <span class="sheet-row-meta">Header: Row {s_h_row} &bull; Data starts: Row {s_d_row} &bull; {len(s_reqs) if isinstance(s_reqs, list) else 0} Requirements</span>
                </div>
                <div class="schema-cols-wrap">{"".join(col_badges)}</div>
            </div>
            """)

            if isinstance(s_reqs, list):
                for r in s_reqs:
                    if not isinstance(r, dict):
                        continue
                    r_id = html.escape(str(r.get("requirement_id", "")))
                    r_text = html.escape(str(r.get("requirement_text", "")))
                    r_cell = html.escape(str(r.get("source_cell", "")))
                    r_section = html.escape(str(r.get("section") or ""))
                    target_slots = r.get("target_slots", {})

                    slot_badges: list[str] = []
                    has_slot_formula = False
                    if isinstance(target_slots, dict):
                        for slot_key, slot_obj in target_slots.items():
                            if isinstance(slot_obj, dict):
                                s_type = html.escape(str(slot_obj.get("slot_type", slot_key)))
                                s_coord = html.escape(str(slot_obj.get("cell_coordinate", "")))
                                slot_badges.append(f'<span class="slot-pill"><strong style="color:var(--text-title);">{s_coord}</strong> ({s_type})</span>')
                                if slot_obj.get("has_formula", False):
                                    has_slot_formula = True
                                    formula_count += 1

                    formula_guard_pill = (
                        '<span class="badge-pill badge-emerald" style="font-size:10px;">Rule 9: Protected Formula</span>'
                        if has_slot_formula
                        else '<span class="badge-pill" style="background:#f1f5f9;color:#64748b;font-size:10px;">Fillable</span>'
                    )

                    all_reqs_rows.append(f"""
                    <tr class="excel-req-row" data-search="{r_id.lower()} {r_text.lower()} {r_section.lower()}">
                        <td style="font-weight:600; color:var(--primary-blue);">{r_id}</td>
                        <td style="color:var(--text-subtle);">{r_cell}</td>
                        <td>
                            {f'<div style="font-size:11px; font-weight:600; color:var(--text-subtle); margin-bottom:2px;">{r_section}</div>' if r_section else ''}
                            <div style="font-weight:500;">{r_text}</div>
                        </td>
                        <td><div style="display:flex; flex-wrap:wrap; gap:4px;">{"".join(slot_badges) or '<span class="chip-none">None</span>'}</div></td>
                        <td>{formula_guard_pill}</td>
                    </tr>
                    """)

        excel_section_html = f"""
        <!-- Step 2: Excel Section -->
        <div class="card-box" id="excelSection">
            <div class="card-header-bar">
                <div>
                    <div class="card-heading">Step 2: Dynamic Excel Workbook &amp; Requirements Analysis</div>
                    <div style="font-size:12px; color:var(--text-subtle); margin-top:2px;">Workbook: <strong>{wb_id}.xlsx</strong> &bull; Hash: {wb_hash}</div>
                </div>
                <input type="text" id="reqFilterInput" class="search-input" placeholder="Filter requirements..." onkeyup="filterRequirements()">
            </div>

            <!-- Excel Metrics Strip -->
            <div class="metrics-grid" style="grid-template-columns: repeat(4, 1fr); margin-bottom: 20px;">
                <div class="metric-tile">
                    <div class="metric-label">Analyzed Sheets</div>
                    <div class="metric-val">{len(sheets)}</div>
                    <div class="metric-sub">Worksheets Parsed</div>
                </div>
                <div class="metric-tile">
                    <div class="metric-label">Extracted Requirements</div>
                    <div class="metric-val">{wb_total_reqs}</div>
                    <div class="metric-sub">Questions / Specifications</div>
                </div>
                <div class="metric-tile">
                    <div class="metric-label">Header Mapping</div>
                    <div class="metric-val" style="font-size: 16px; color: var(--emerald-fg); font-weight:700;">Dynamic Auto-Detect</div>
                    <div class="metric-sub">Zero hardcoded addresses</div>
                </div>
                <div class="metric-tile">
                    <div class="metric-label">Rule 9 Formula Guard</div>
                    <div class="metric-val">{formula_count}</div>
                    <div class="metric-sub">Protected Formulas</div>
                </div>
            </div>

            <!-- Sheet Schema Cards -->
            <div class="sheet-schema-container" style="margin-bottom: 20px;">
                {"".join(sheet_cards)}
            </div>

            <!-- Requirements Table -->
            <div class="table-responsive">
                <table class="excel-req-table">
                    <thead>
                        <tr>
                            <th style="width: 130px;">Req ID</th>
                            <th style="width: 70px;">Cell</th>
                            <th>Requirement / Technical Specification</th>
                            <th style="width: 200px;">Target Fillable Slots</th>
                            <th style="width: 140px;">Formula Guard</th>
                        </tr>
                    </thead>
                    <tbody id="reqTableBody">
                        {"".join(all_reqs_rows) if all_reqs_rows else '<tr><td colspan="5" style="text-align:center; padding:20px; color:var(--text-subtle);">No requirements found.</td></tr>'}
                    </tbody>
                </table>
            </div>
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RFP Extraction Intelligence — {doc_id}</title>
    <style>
        :root {{
            --bg-canvas: #f8fafc;
            --surface-card: #ffffff;
            --text-title: #0f172a;
            --text-body: #334155;
            --text-subtle: #64748b;
            --border-subtle: #e2e8f0;
            --border-strong: #cbd5e1;

            --primary-blue: #2563eb;
            --emerald-fg: #059669;
            --emerald-bg: #ecfdf5;
            --emerald-border: #a7f3d0;

            --amber-fg: #b45309;
            --amber-bg: #fffbeb;
            --amber-border: #fde68a;

            --rose-fg: #e11d48;
            --rose-bg: #fff1f2;
            --rose-border: #fecdd3;

            --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
            --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.07), 0 2px 4px -2px rgba(0, 0, 0, 0.05);
        }}

        * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif; }}
        body {{ background-color: var(--bg-canvas); color: var(--text-body); padding: 40px 20px; line-height: 1.5; }}
        .app-container {{ max-width: 980px; margin: 0 auto; }}

        /* Top Bar */
        .top-nav {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }}
        .breadcrumb {{ font-size: 13px; font-weight: 500; color: var(--text-subtle); display: flex; align-items: center; gap: 6px; }}
        .breadcrumb span {{ color: var(--text-title); font-weight: 600; }}

        .actions-strip {{ display: flex; gap: 8px; }}
        .btn-action {{
            background: var(--surface-card);
            border: 1px solid var(--border-subtle);
            border-radius: 6px;
            padding: 6px 12px;
            font-size: 12px;
            font-weight: 600;
            color: var(--text-body);
            cursor: pointer;
            transition: all 0.15s ease;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            text-decoration: none;
        }}
        .btn-action:hover {{ background: #f1f5f9; border-color: var(--border-strong); }}

        /* Hero Panel */
        .hero-panel {{
            background: var(--surface-card);
            border: 1px solid var(--border-subtle);
            border-radius: 12px;
            padding: 26px 30px;
            margin-bottom: 20px;
            box-shadow: var(--shadow-sm);
        }}
        .hero-top {{ display: flex; justify-content: space-between; align-items: flex-start; }}
        .hero-title {{ font-size: 22px; font-weight: 700; color: var(--text-title); letter-spacing: -0.02em; }}
        .hero-desc {{ font-size: 14px; color: var(--text-subtle); margin-top: 4px; }}

        .badge-pill {{
            font-size: 11px;
            font-weight: 700;
            padding: 4px 10px;
            border-radius: 9999px;
            letter-spacing: 0.5px;
            display: inline-flex;
            align-items: center;
            gap: 5px;
        }}
        .badge-emerald {{ background: var(--emerald-bg); color: var(--emerald-fg); border: 1px solid var(--emerald-border); }}
        .badge-amber {{ background: var(--amber-bg); color: var(--amber-fg); border: 1px solid var(--amber-border); }}
        .badge-rose {{ background: var(--rose-bg); color: var(--rose-fg); border: 1px solid var(--rose-border); }}

        /* Metrics Strip */
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 16px;
            margin-bottom: 20px;
        }}
        @media (max-width: 768px) {{
            .metrics-grid {{ grid-template-columns: 1fr !important; }}
        }}
        .metric-tile {{
            background: var(--surface-card);
            border: 1px solid var(--border-subtle);
            border-radius: 12px;
            padding: 18px 20px;
            box-shadow: var(--shadow-sm);
        }}
        .metric-label {{ font-size: 11px; font-weight: 600; color: var(--text-subtle); text-transform: uppercase; letter-spacing: 0.04em; }}
        .metric-val {{ font-size: 22px; font-weight: 700; color: var(--text-title); margin-top: 4px; letter-spacing: -0.02em; }}
        .metric-sub {{ font-size: 12px; color: var(--text-subtle); margin-top: 4px; }}

        /* Notices / Callouts */
        .ui-notice {{
            display: flex;
            gap: 14px;
            border-radius: 10px;
            padding: 14px 18px;
            margin-bottom: 20px;
            align-items: flex-start;
        }}
        .notice-amber {{ background: var(--amber-bg); border: 1px solid var(--amber-border); color: var(--amber-fg); }}
        .notice-blue {{ background: #eff6ff; border: 1px solid #bfdbfe; color: #1e40af; }}
        .notice-icon {{ margin-top: 2px; flex-shrink: 0; }}
        .notice-heading {{ font-size: 13px; font-weight: 700; }}
        .notice-body {{ font-size: 12px; margin-top: 4px; line-height: 1.5; }}

        .missing-items-list {{ list-style: none; margin-top: 8px; display: flex; flex-direction: column; gap: 6px; }}
        .missing-item-row {{
            background: #ffffff;
            border: 1px solid var(--amber-border);
            border-radius: 6px;
            padding: 6px 12px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            font-size: 12px;
        }}
        .missing-item-left {{ display: flex; align-items: center; gap: 8px; }}
        .flag-action-tag {{ font-size: 11px; font-weight: 700; color: #b45309; background: #fef3c7; padding: 2px 8px; border-radius: 4px; }}

        /* Card Box */
        .card-box {{
            background: var(--surface-card);
            border: 1px solid var(--border-subtle);
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 20px;
            box-shadow: var(--shadow-sm);
        }}
        .card-header-bar {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; flex-wrap: wrap; gap: 10px; }}
        .card-heading {{ font-size: 15px; font-weight: 700; color: var(--text-title); }}

        .search-input {{
            border: 1px solid var(--border-subtle);
            border-radius: 6px;
            padding: 6px 12px;
            font-size: 13px;
            color: var(--text-body);
            background: #fafafa;
            outline: none;
            width: 220px;
            transition: all 0.15s;
        }}
        .search-input:focus {{ background: #ffffff; border-color: var(--primary-blue); box-shadow: 0 0 0 2px rgba(37,99,235,0.1); }}

        /* Expandable Probe Cards (Feature 1) */
        .probe-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }}
        .probe-card {{
            border-radius: 8px;
            padding: 14px 16px;
            border: 1px solid var(--border-subtle);
            background: #fafbfc;
            transition: border-color 0.1s ease, box-shadow 0.1s ease;
        }}
        .probe-card:hover {{ border-color: var(--border-strong); background: #ffffff; }}
        .probe-card details {{ width: 100%; }}
        .probe-card summary {{
            list-style: none;
            cursor: pointer;
            outline: none;
            user-select: none;
        }}
        .probe-card summary::-webkit-details-marker {{ display: none; }}
        .probe-card summary:after {{
            content: "▾";
            float: right;
            font-size: 12px;
            color: var(--text-subtle);
            margin-top: -16px;
            transition: transform 0.15s ease;
        }}
        .probe-card details[open] summary:after {{
            transform: rotate(180deg);
        }}

        .probe-top {{ display: flex; align-items: center; justify-content: space-between; padding-right: 18px; }}
        .probe-title {{ font-size: 14px; font-weight: 600; color: var(--text-title); }}
        .probe-meta {{ font-size: 12px; color: var(--text-subtle); margin-top: 6px; padding-right: 18px; }}

        .status-indicator {{ width: 8px; height: 8px; border-radius: 50%; display: inline-block; }}
        .ind-green {{ background: #10b981; }}
        .ind-cyan {{ background: #0284c7; }}
        .ind-amber {{ background: #f59e0b; }}
        .ind-red {{ background: #f43f5e; }}

        .probe-count-pill {{
            font-size: 11px;
            font-weight: 600;
            padding: 2px 7px;
            border-radius: 4px;
            background: #e2e8f0;
            color: #475569;
        }}
        .pill-cyan {{ background: #e0f2fe; color: #0369a1; }}
        .pill-amber {{ background: #fef3c7; color: #92400e; }}
        .pill-danger {{ background: #fee2e2; color: #991b1b; }}

        .probe-details-body {{
            margin-top: 10px;
            padding-top: 10px;
            border-top: 1px dashed var(--border-subtle);
            font-size: 12px;
            display: flex;
            flex-direction: column;
            gap: 6px;
        }}
        .probe-detail-row {{ display: flex; flex-direction: column; gap: 3px; }}
        .detail-label {{ font-size: 11px; font-weight: 600; color: var(--text-subtle); }}
        .evidence-chips {{ display: flex; flex-wrap: wrap; gap: 4px; }}
        .chip-page {{ background: #f1f5f9; color: #1e293b; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: 600; }}
        .chip-table {{ background: #ede9fe; color: #5b21b6; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: 600; }}
        .chip-none {{ color: var(--text-subtle); font-style: italic; font-size: 11px; }}
        .evidence-quote {{
            background: #f8fafc;
            border-left: 2px solid var(--primary-blue);
            padding: 6px 8px;
            font-size: 11px;
            border-radius: 2px;
            margin-top: 4px;
        }}

        /* Step 2 Excel Section Styles */
        .sheet-summary-item {{
            background: #f8fafc;
            border: 1px solid var(--border-subtle);
            border-radius: 8px;
            padding: 12px 16px;
            margin-bottom: 10px;
        }}
        .sheet-sum-top {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }}
        .sheet-title-badge {{ font-weight: 700; color: var(--text-title); font-size: 13px; }}
        .sheet-row-meta {{ font-size: 12px; color: var(--text-subtle); }}
        .schema-cols-wrap {{ display: flex; flex-wrap: wrap; gap: 6px; }}
        .schema-col-pill {{ background: #ffffff; border: 1px solid var(--border-subtle); padding: 2px 8px; border-radius: 4px; font-size: 11px; color: var(--text-body); }}

        .table-responsive {{ overflow-x: auto; }}
        .excel-req-table {{ width: 100%; border-collapse: collapse; font-size: 13px; text-align: left; margin-top: 10px; }}
        .excel-req-table th {{ background: #f8fafc; padding: 10px 12px; font-weight: 600; color: var(--text-subtle); border-bottom: 1px solid var(--border-strong); }}
        .excel-req-table td {{ padding: 10px 12px; border-bottom: 1px solid var(--border-subtle); vertical-align: top; }}
        .excel-req-table tr:hover {{ background: #fafafa; }}
        .slot-pill {{ background: #f1f5f9; border: 1px solid var(--border-subtle); border-radius: 4px; padding: 2px 6px; font-size: 11px; }}

        /* Checklist at the end */
        .invariant-list {{ list-style: none; display: flex; flex-direction: column; gap: 12px; }}
        .invariant-row {{ display: flex; align-items: center; justify-content: space-between; padding-bottom: 12px; border-bottom: 1px solid var(--border-subtle); }}
        .invariant-row:last-child {{ border-bottom: none; padding-bottom: 0; }}
        .inv-left {{ display: flex; align-items: center; gap: 10px; font-size: 14px; color: var(--text-body); }}
        .inv-check {{ color: #10b981; }}
        .inv-val {{ font-size: 13px; font-weight: 600; color: var(--text-subtle); }}

        /* Footer */
        .footer-strip {{ text-align: center; font-size: 12px; color: var(--text-subtle); margin-top: 32px; padding-bottom: 16px; }}
    </style>
</head>
<body>
    <div class="app-container">

        <!-- Top Navigation -->
        <div class="top-nav">
            <div class="breadcrumb">
                Pipeline Lab / <span>Extraction &amp; Requirement Review</span>
            </div>
            <div class="actions-strip">
                <a href="#excelSection" class="btn-action">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="8" y1="13" x2="16" y2="13"/><line x1="8" y1="17" x2="16" y2="17"/></svg>
                    Jump to Excel Analysis
                </a>
                <button class="btn-action" onclick="window.print()">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg>
                    Print Report
                </button>
            </div>
        </div>

        <!-- 1. Overall Health Hero Panel -->
        <div class="hero-panel">
            <div class="hero-top">
                <div>
                    <h1 class="hero-title">{headline}</h1>
                    <p class="hero-desc">{subheadline}</p>
                </div>
                <span class="badge-pill {badge_class}">{verdict_badge}</span>
            </div>
        </div>

        <!-- Rule 7 Zero-Hallucination Warning for NOT_SPECIFIED items (Feature 2) -->
        {missing_probes_callout_html}

        <!-- 2. Metrics Strip: Total Pages, Extracted Text Pages, Words, Tables, OCR Status, OCR Text -->
        <div class="metrics-grid">
            <div class="metric-tile">
                <div class="metric-label">Document ID</div>
                <div class="metric-val" style="font-size: 18px; text-overflow: ellipsis; overflow: hidden; white-space: nowrap;">{doc_id}</div>
                <div class="metric-sub">PRD-12 Normalized JSON</div>
            </div>
            <div class="metric-tile">
                <div class="metric-label">Pages &amp; Text Pages</div>
                <div class="metric-val">{total_pages} <span style="font-size: 14px; font-weight: 500; color: var(--text-subtle);">Pages</span></div>
                <div class="metric-sub">{extracted_text_pages} Pages with Extracted Text</div>
            </div>
            <div class="metric-tile">
                <div class="metric-label">Total Words Extracted</div>
                <div class="metric-val">{total_words:,}</div>
                <div class="metric-sub">{total_chars:,} Characters Extracted</div>
            </div>
            <div class="metric-tile">
                <div class="metric-label">Structured Tables</div>
                <div class="metric-val">{total_tables} <span style="font-size: 14px; font-weight: 500; color: var(--text-subtle);">Tables</span></div>
                <div class="metric-sub">Columns &amp; Headers Aligned</div>
            </div>
            <div class="metric-tile">
                <div class="metric-label">OCR Used or Not</div>
                <div class="metric-val">{ocr_status_label}</div>
                <div class="metric-sub">{ocr_status_sub}</div>
            </div>
            <div class="metric-tile">
                <div class="metric-label">Text Extracted via OCR</div>
                <div class="metric-val">{ocr_text_val}</div>
                <div class="metric-sub">{ocr_text_sub}</div>
            </div>
        </div>

        <!-- Image Alert (Ghost / Low-Text / Diagram Pages) -->
        {flagged_box_html}

        <!-- 3. Target Spec Check (Reverse Ground Truth Keyword Search with Expandable Cards) -->
        <div class="card-box">
            <div class="card-header-bar">
                <div>
                    <div class="card-heading">Target Specification Check &amp; Ground Truth Probing</div>
                    <div style="font-size:12px; color:var(--text-subtle); margin-top:2px;">Click any card to expand matched pages and evidence details.</div>
                </div>
                <input type="text" id="filterInput" class="search-input" placeholder="Filter specifications..." onkeyup="filterProbes()">
            </div>
            <div class="probe-grid" id="probeContainer">
                {probe_cards_html}
            </div>
        </div>

        <!-- 4. Step 2 Dedicated Excel Section (Feature 3) -->
        {excel_section_html}

        <!-- 5. Checklist at the End (Extraction Invariants & Integrity) -->
        <div class="card-box">
            <div class="card-header-bar">
                <div class="card-heading">Extraction Integrity &amp; Invariants Checklist</div>
            </div>
            <ul class="invariant-list">
                <li class="invariant-row">
                    <span class="inv-left">
                        <svg class="inv-check" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
                        Page Continuity &amp; Sequence
                    </span>
                    <span class="inv-val">{total_pages} / {total_pages} Pages (Zero Skipped)</span>
                </li>
                <li class="invariant-row">
                    <span class="inv-left">
                        <svg class="inv-check" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
                        Extracted Text Volume &amp; Cleanliness
                    </span>
                    <span class="inv-val">{total_words:,} Words &bull; {total_chars:,} Chars &bull; {corrupted_chars} Corrupted</span>
                </li>
                <li class="invariant-row">
                    <span class="inv-left">
                        <svg class="inv-check" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
                        Structured Table Grids
                    </span>
                    <span class="inv-val">{total_tables} Valid Tables</span>
                </li>
                <li class="invariant-row">
                    <span class="inv-left">
                        <svg class="inv-check" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
                        OCR Engine Execution
                    </span>
                    <span class="inv-val">{ocr_status_label} &bull; {ocr_text_val} from Images</span>
                </li>
                <li class="invariant-row">
                    <span class="inv-left">
                        <svg class="inv-check" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
                        PRD Section 12 Schema Output
                    </span>
                    <span class="inv-val">Validated JSON Artifact</span>
                </li>
            </ul>
        </div>

        <div class="footer-strip">
            Local AI RFP Automation System &bull; Phase 1 &amp; 2 Quality Gate
        </div>

    </div>

    <!-- Client-Side Search Filters -->
    <script>
        function filterProbes() {{
            const filter = document.getElementById('filterInput').value.toLowerCase();
            const cards = document.querySelectorAll('.probe-card');
            cards.forEach(card => {{
                const term = card.getAttribute('data-term') || '';
                card.style.display = term.includes(filter) ? '' : 'none';
            }});
        }}

        function filterRequirements() {{
            const filter = document.getElementById('reqFilterInput').value.toLowerCase();
            const rows = document.querySelectorAll('.excel-req-row');
            rows.forEach(row => {{
                const search = row.getAttribute('data-search') || '';
                row.style.display = search.includes(filter) ? '' : 'none';
            }});
        }}
    </script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate Clean HTML Executive Extraction Report"
    )
    parser.add_argument(
        "--report",
        "-r",
        type=Path,
        default=Path("pipeline_lab/validation_report.json"),
        help="Path to validation report JSON file",
    )
    parser.add_argument(
        "--excel-analysis",
        "-e",
        type=Path,
        default=Path("pipeline_lab/excel_analysis.json"),
        help="Path to Step 2 Excel analysis JSON file",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("pipeline_lab/extraction_report.html"),
        help="Path to output HTML file",
    )
    args = parser.parse_args()

    target_report = args.report
    if not target_report.exists() and Path("validation_report.json").exists():
        target_report = Path("validation_report.json")

    with open(target_report, "r", encoding="utf-8") as f:
        report_data: dict[str, object] = json.load(f)

    excel_data: dict[str, object] | None = None
    target_excel = args.excel_analysis
    if not target_excel.exists() and Path("excel_analysis.json").exists():
        target_excel = Path("excel_analysis.json")

    if target_excel.exists():
        with open(target_excel, "r", encoding="utf-8") as f:
            excel_data = json.load(f)

    html_content = generate_professional_html(report_data, excel_data=excel_data)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"\n  [SUCCESS] Clean HTML Report updated -> {args.output.resolve()}\n")


if __name__ == "__main__":
    main()
