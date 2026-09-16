#!/usr/bin/env python3
"""
Step 3: Evidence Retrieval & Candidate Matching.
Connects Step 1 (pdf_output.json) and Step 2 (excel_analysis.json) using Simple Hybrid Search.
Strict typing only — zero Any (Rule 4). 100% offline (Rule 10).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import TypedDict

try:
    from ai_rfp_excel.app.pipeline.step3_indexer import SourceType, build_document_chunks
    from ai_rfp_excel.app.pipeline.step3_search import batch_get_local_embeddings, simple_hybrid_search
except ModuleNotFoundError:
    from step3_indexer import SourceType, build_document_chunks  # type: ignore[no-redef]
    from step3_search import batch_get_local_embeddings, simple_hybrid_search  # type: ignore[no-redef]


class EvidenceSnippet(TypedDict):
    page_number: int
    source_type: SourceType
    snippet: str
    score: float
    table_id: str | None
    exact_matches: list[str]


class RequirementEvidence(TypedDict):
    requirement_id: str
    sheet_name: str
    row_number: int
    section: str | None
    requirement_text: str
    target_slots: dict[str, dict[str, str | int | bool | None]]
    candidate_snippets: list[EvidenceSnippet]
    deterministic_hits: list[str]
    top_page_numbers: list[int]


class Step3Output(TypedDict):
    document_id: str
    workbook_id: str
    total_requirements: int
    requirements_with_evidence: int
    items: list[RequirementEvidence]


def run_evidence_retrieval(
    pdf_output_path: Path,
    excel_analysis_path: Path,
    output_path: Path | None = None,
    top_k: int = 5,
    use_embeddings: bool = True,
) -> Step3Output:
    """Execute Step 3 Simple Hybrid evidence retrieval connecting PDF and Excel outputs."""
    with open(pdf_output_path, "r", encoding="utf-8") as f:
        pdf_data: dict[str, object] = json.load(f)

    with open(excel_analysis_path, "r", encoding="utf-8") as f:
        excel_data: dict[str, object] = json.load(f)

    doc_id = str(pdf_data.get("document_id", pdf_output_path.stem))
    wb_id = str(excel_data.get("workbook_id", excel_analysis_path.stem))

    # 1. Build structured document chunks (paragraphs, table rows, OCR)
    chunks = build_document_chunks(pdf_data)

    # 2. Pre-embed document chunks in batch if embeddings are enabled
    if use_embeddings and chunks:
        chunk_texts = [c["content"] for c in chunks]
        batch_get_local_embeddings(chunk_texts)

    # 2b. Pre-embed all requirement queries in batch upfront to eliminate per-query HTTP overhead
    sheets_raw = excel_data.get("sheets", [])
    if use_embeddings and isinstance(sheets_raw, list):
        all_queries: list[str] = []
        for s in sheets_raw:
            if isinstance(s, dict):
                reqs = s.get("requirements", [])
                if isinstance(reqs, list):
                    for r in reqs:
                        if isinstance(r, dict):
                            s_raw = r.get("section")
                            sec = str(s_raw).strip() if s_raw else None
                            txt = str(r.get("requirement_text", ""))
                            all_queries.append(f"{sec} {txt}" if sec else txt)
        if all_queries:
            batch_get_local_embeddings(all_queries)

    # 3. Match each Excel requirement against document chunks
    evidence_items: list[RequirementEvidence] = []
    if isinstance(sheets_raw, list):
        for s in sheets_raw:
            if not isinstance(s, dict):
                continue
            reqs_raw = s.get("requirements", [])
            if not isinstance(reqs_raw, list):
                continue

            for r in reqs_raw:
                if not isinstance(r, dict):
                    continue
                req_id = str(r.get("requirement_id", ""))
                sheet_name = str(r.get("sheet_name", ""))
                row_num = int(str(r.get("row_number", 0)))
                section_raw = r.get("section")
                section = (
                    str(section_raw).strip()
                    if section_raw is not None and str(section_raw).strip()
                    else None
                )
                req_text = str(r.get("requirement_text", ""))

                # Parse target slot coordinates
                slots_raw = r.get("target_slots", {})
                target_slots: dict[str, dict[str, str | int | bool | None]] = {}
                if isinstance(slots_raw, dict):
                    for st, s_val in slots_raw.items():
                        if isinstance(s_val, dict):
                            target_slots[st] = {
                                "slot_type": str(s_val.get("slot_type", "")),
                                "header_name": str(s_val.get("header_name", "")),
                                "column_letter": str(s_val.get("column_letter", "")),
                                "column_index": int(str(s_val.get("column_index", 0))),
                                "cell_coordinate": str(s_val.get("cell_coordinate", "")),
                                "current_value": (
                                    str(s_val.get("current_value"))
                                    if s_val.get("current_value") is not None
                                    else None
                                ),
                                "has_formula": bool(s_val.get("has_formula", False)),
                                "formula": (
                                    str(s_val.get("formula"))
                                    if s_val.get("formula") is not None
                                    else None
                                ),
                            }

                # Hybrid search query combining optional section title + requirement text
                query = f"{section} {req_text}" if section else req_text
                matches, exact_hits = simple_hybrid_search(
                    query=query,
                    chunks=chunks,
                    top_k=top_k,
                    use_embeddings=use_embeddings,
                )

                snippets: list[EvidenceSnippet] = [
                    {
                        "page_number": c["page_number"],
                        "source_type": c["source_type"],
                        "snippet": c["content"],
                        "score": round(score * 100.0, 2),
                        "table_id": c["table_id"],
                        "exact_matches": hits,
                    }
                    for c, score, hits in matches
                ]

                top_pages = sorted({s["page_number"] for s in snippets})
                evidence_items.append({
                    "requirement_id": req_id,
                    "sheet_name": sheet_name,
                    "row_number": row_num,
                    "section": section,
                    "requirement_text": req_text,
                    "target_slots": target_slots,
                    "candidate_snippets": snippets,
                    "deterministic_hits": exact_hits,
                    "top_page_numbers": top_pages,
                })

    reqs_with_evidence = sum(1 for item in evidence_items if len(item["candidate_snippets"]) > 0)
    result: Step3Output = {
        "document_id": doc_id,
        "workbook_id": wb_id,
        "total_requirements": len(evidence_items),
        "requirements_with_evidence": reqs_with_evidence,
        "items": evidence_items,
    }

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Step 3: Simple Hybrid Evidence Retrieval.")
    parser.add_argument(
        "--pdf-output",
        type=Path,
        default=Path("data/generated/pdf_output.json"),
        help="Path to Step 1 pdf_output.json",
    )
    parser.add_argument(
        "--excel-analysis",
        type=Path,
        default=Path("data/generated/excel_analysis.json"),
        help="Path to Step 2 excel_analysis.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/generated/candidate_evidence.json"),
        help="Path to save candidate_evidence.json artifact",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of candidate snippets to retain per requirement (default: 5)",
    )
    parser.add_argument(
        "--no-embeddings",
        action="store_true",
        help="Disable local embedding similarity and use keyword matching only",
    )
    args = parser.parse_args()

    print(f"Loading PDF output from {args.pdf_output}...")
    print(f"Loading Excel analysis from {args.excel_analysis}...")
    result = run_evidence_retrieval(
        pdf_output_path=args.pdf_output,
        excel_analysis_path=args.excel_analysis,
        output_path=args.output,
        top_k=args.top_k,
        use_embeddings=not args.no_embeddings,
    )

    print("\n" + "=" * 60)
    print(" STEP 3 'SIMPLE HYBRID' RETRIEVAL SUMMARY")
    print("=" * 60)
    print(f" Document ID:            {result['document_id']}")
    print(f" Workbook ID:            {result['workbook_id']}")
    print(f" Total Requirements:     {result['total_requirements']}")
    pct = (result["requirements_with_evidence"] / max(1, result["total_requirements"])) * 100.0
    print(f" Reqs with Evidence:     {result['requirements_with_evidence']} ({pct:.1f}%)")
    print(f" Output Artifact:        {args.output}")
    print("=" * 60)


if __name__ == "__main__":
    main()

