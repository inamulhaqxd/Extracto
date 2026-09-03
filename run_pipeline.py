#!/usr/bin/env python3
"""Main Pipeline Runner for AI RFP PDF-to-Excel Automation.

Executes AI-native compliance matching, Excel analysis, and automated population.
Includes bounded concurrency to optimize speed while keeping CPU/GPU temperatures safe.
"""

import argparse
import asyncio
import re
import time
from pathlib import Path
from typing import Any

import pypdfium2

from ai_rfp_excel.app.excel.analyzer import ExcelAnalyzer
from ai_rfp_excel.app.excel.writer import ExcelWriter
from ai_rfp_excel.app.matching.engine import ComplianceEngine
from ai_rfp_excel.app.matching.models import ComplianceDecision, FactItem


def extract_pdf_facts(pdf_path: str) -> list[FactItem]:
    """Extract structured facts, specifications, and contextual passages from PDF pages."""
    pdf = pypdfium2.PdfDocument(pdf_path)
    facts: list[FactItem] = []

    for i, page in enumerate(pdf):
        page_num = i + 1
        text = page.get_textpage().get_text_range()
        if not text or not text.strip():
            continue

        # 1. Whole-page context fact
        facts.append(
            FactItem(
                field_name=f"Page {page_num} Overview",
                value=text.strip(),
                source_page=page_num,
                confidence=0.90,
                extraction_method="pdf_page_context",
            )
        )

        # 2. Extract structured key-value pairs and bullet lines
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        for line in lines:
            if ":" in line:
                parts = line.split(":", 1)
                field_name = parts[0].strip()
                val = parts[1].strip()
                if field_name and val and len(field_name) < 80:
                    facts.append(
                        FactItem(
                            field_name=field_name,
                            value=val,
                            source_page=page_num,
                            confidence=0.95,
                            extraction_method="pdf_key_value",
                        )
                    )
            elif len(line) >= 10:
                # Direct spec statement / bullet point
                facts.append(
                    FactItem(
                        field_name="Technical Spec",
                        value=line,
                        source_page=page_num,
                        confidence=0.90,
                        extraction_method="pdf_line_spec",
                    )
                )

        # 3. Extract multi-line paragraph blocks
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if len(p.strip()) > 30]
        for p in paragraphs:
            first_line = p.split("\n")[0].strip()
            heading = first_line[:50] if len(first_line) <= 50 else "Section Detail"
            facts.append(
                FactItem(
                    field_name=heading,
                    value=p,
                    source_page=page_num,
                    confidence=0.92,
                    extraction_method="pdf_section_block",
                )
            )

    return facts


async def run_main_pipeline(
    pdf_path: str,
    excel_path: str,
    output_dir: str = "testworkflowfile",
    create_summary: bool = True,
    model: str | None = None,
    concurrency: int = 2,
) -> str:
    start_time = time.time()
    print("=" * 60)
    print("  MAIN PRODUCTION PIPELINE: RFP PDF-TO-EXCEL AUTOMATION")
    print(f"  AI-Native Reasoning | Concurrency: {concurrency} Workers | Zero-Crash")
    print("=" * 60)
    print(f"\n  [INPUT PDF]   : {pdf_path}")
    print(f"  [INPUT EXCEL] : {excel_path}")
    print(f"  [MODEL]       : {model or 'Default'}")
    print(f"  [CONCURRENCY] : {concurrency} workers (thermal-safe)")
    print(f"  [SUMMARY TAB] : {'Enabled' if create_summary else 'Disabled'}")

    # Step 1: Ingestion
    print("\n" + "=" * 60)
    print("  STEP 1: PDF FACT EXTRACTION & PARSING")
    print("=" * 60)
    t0 = time.time()
    facts = extract_pdf_facts(pdf_path)
    print(f"  Successfully extracted {len(facts)} contextual fact items from PDF in {time.time() - t0:.2f}s")

    # Step 2: Excel Template Structure Analysis
    print("\n" + "=" * 60)
    print("  STEP 2: EXCEL TEMPLATE STRUCTURE ANALYSIS")
    print("=" * 60)
    analyzer = ExcelAnalyzer()
    analysis = analyzer.analyze_workbook(excel_path)
    total_reqs = analysis.total_requirements
    print(f"  Workbook analyzed: {len(analysis.sheets)} sheet(s), {total_reqs} requirement(s)")

    # Step 3: Layered Compliance Resolution with Bounded Concurrency
    print("\n" + "=" * 60)
    print(f"  STEP 3: AI COMPLIANCE RESOLUTION ({concurrency} Parallel Workers)")
    print("=" * 60)
    engine = ComplianceEngine()
    sem = asyncio.Semaphore(concurrency)
    completed_count = 0
    lock = asyncio.Lock()

    async def evaluate_single(req: Any) -> ComplianceDecision:
        nonlocal completed_count
        async with sem:
            decision = await engine.evaluate_requirement(
                requirement_text=req.requirement_text,
                facts=facts,
                requirement_id=req.requirement_id,
                model_name=model,
            )
            async with lock:
                completed_count += 1
                curr = completed_count

            req_display = str(req.requirement_text)[:40].encode("ascii", errors="replace").decode("ascii")
            val_display = str(decision.matched_value or "")[:40].encode("ascii", errors="replace").decode("ascii")
            print(f"  [{curr:>3}/{total_reqs}] [{decision.state.value:<13}] '{req_display}...' -> '{val_display}' ({decision.resolving_layer})")
            return decision

    # Gather tasks in sheet order
    all_reqs = [req for sheet in analysis.sheets for req in sheet.requirements]
    tasks = [evaluate_single(req) for req in all_reqs]
    decisions = list(await asyncio.gather(*tasks))

    print(f"\n  Completed {len(decisions)} compliance evaluations")

    # Step 4: Output Population
    print("\n" + "=" * 60)
    print("  STEP 4: WORKBOOK POPULATION & SUMMARY TAB")
    print("=" * 60)
    writer = ExcelWriter(output_dir=Path(output_dir))
    result = writer.populate_workbook(
        template_path=Path(excel_path),
        analysis=analysis,
        decisions=decisions,
        create_summary=create_summary,
    )

    elapsed = time.time() - start_time
    print(f"\n  [SUCCESS] Populated {result.total_populated_cells} cells in {elapsed:.2f}s ({elapsed/60:.1f}m)")
    print(f"  [OUTPUT FILE]: {result.output_file_path}\n")
    return result.output_file_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run main AI RFP PDF-to-Excel pipeline.")
    parser.add_argument("pdf", nargs="?", default="testworkflowfile/refernce.pdf", help="Path to input PDF file")
    parser.add_argument("excel", nargs="?", default="testworkflowfile/evaluation_round2_compute_specs.xlsx", help="Path to input Excel file")
    parser.add_argument("-o", "--output-dir", default="testworkflowfile/output", help="Output directory for generated Excel")
    parser.add_argument("-m", "--model", default=None, help="LLM Model to use (e.g. qwen2.5:3b)")
    parser.add_argument("-c", "--concurrency", type=int, default=2, help="Number of concurrent workers (default: 2)")
    parser.add_argument("--no-summary", action="store_true", help="Do not generate Compliance Summary dashboard tab")
    args = parser.parse_args()

    asyncio.run(
        run_main_pipeline(
            args.pdf,
            args.excel,
            args.output_dir,
            create_summary=not args.no_summary,
            model=args.model,
            concurrency=args.concurrency,
        )
    )


if __name__ == "__main__":
    main()
