#!/usr/bin/env python3
"""
Main Pipeline Runner for AI RFP PDF-to-Excel Automation
Executes the full layered compliance matching, Excel analysis, and automated population.
"""

import argparse
import asyncio
import sys
import time
from pathlib import Path
from typing import Any

import openpyxl
import pypdfium2

from ai_rfp_excel.app.excel.analyzer import ExcelAnalyzer
from ai_rfp_excel.app.excel.writer import ExcelWriter
from ai_rfp_excel.app.matching.engine import ComplianceEngine
from ai_rfp_excel.app.matching.models import ComplianceDecision, FactItem


def extract_pdf_facts(pdf_path: str) -> list[FactItem]:
    """Extract structured facts and key-value specs from PDF pages."""
    pdf = pypdfium2.PdfDocument(pdf_path)
    facts: list[FactItem] = []
    
    for i, page in enumerate(pdf):
        text = page.get_textpage().get_text_range()
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        
        for line in lines:
            if ":" in line:
                parts = line.split(":", 1)
                field_name = parts[0].strip()
                val = parts[1].strip()
                if field_name and val:
                    facts.append(
                        FactItem(
                            field_name=field_name,
                            value=val,
                            source_page=i + 1,
                            confidence=0.95,
                        )
                    )
            elif len(line.split()) >= 2:
                words = line.split()
                for num_label_words in (1, 2, 3):
                    if len(words) > num_label_words and not line.lower().startswith("section"):
                        lbl = " ".join(words[:num_label_words])
                        val = " ".join(words[num_label_words:])
                        facts.append(
                            FactItem(
                                field_name=lbl,
                                value=val,
                                source_page=i + 1,
                                confidence=0.90,
                            )
                        )
                facts.append(
                    FactItem(
                        field_name=line[:40],
                        value=line,
                        source_page=i + 1,
                        confidence=0.80,
                    )
                )

    return facts


async def run_main_pipeline(
    pdf_path: str,
    excel_path: str,
    output_dir: str = "testworkflowfile",
    create_summary: bool = True,
    model: str | None = None,
) -> str:
    start_time = time.time()
    print("=" * 60)
    print("  MAIN PRODUCTION PIPELINE: RFP PDF-TO-EXCEL AUTOMATION")
    print("  Layered Matching | Structure Analysis | Zero-Crash Ingestion")
    print("=" * 60)
    print(f"\n  [INPUT PDF]   : {pdf_path}")
    print(f"  [INPUT EXCEL] : {excel_path}")
    print(f"  [MODEL]       : {model or 'Default'}")
    print(f"  [SUMMARY TAB] : {'Enabled' if create_summary else 'Disabled'}")

    # Step 1: Ingestion
    print("\n" + "=" * 60)
    print("  STEP 1: PDF FACT EXTRACTION & PARSING")
    print("=" * 60)
    t0 = time.time()
    facts = extract_pdf_facts(pdf_path)
    print(f"  Successfully extracted {len(facts)} fact items from PDF in {time.time() - t0:.2f}s")

    # Step 2: Excel Template Structure Analysis
    print("\n" + "=" * 60)
    print("  STEP 2: EXCEL TEMPLATE STRUCTURE ANALYSIS")
    print("=" * 60)
    analyzer = ExcelAnalyzer()
    analysis = analyzer.analyze_workbook(excel_path)
    print(f"  Workbook analyzed: {len(analysis.sheets)} sheet(s), {analysis.total_requirements} requirement(s)")

    # Step 3: Layered Compliance Resolution
    print("\n" + "=" * 60)
    print("  STEP 3: 5-LAYER COMPLIANCE RESOLUTION")
    print("=" * 60)
    engine = ComplianceEngine()
    decisions: list[ComplianceDecision] = []

    for sheet in analysis.sheets:
        print(f"  Processing Sheet '{sheet.sheet_name}' ({len(sheet.requirements)} requirements)...")
        for req in sheet.requirements:
            decision = await engine.evaluate_requirement(
                requirement_text=req.requirement_text,
                facts=facts,
                requirement_id=req.requirement_id,
                model_name=model,
            )
            print(f"    - [{decision.state.value}] '{req.requirement_text[:45]}...' -> '{decision.matched_value}' ({decision.resolving_layer})")
            decisions.append(decision)

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
    print(f"\n  [SUCCESS] Populated {result.total_populated_cells} cells in {elapsed:.2f}s")
    print(f"  [OUTPUT FILE]: {result.output_file_path}\n")
    return result.output_file_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run main AI RFP PDF-to-Excel pipeline.")
    parser.add_argument("pdf", nargs="?", default="testworkflowfile/vendor_datasheet_rx2000.pdf", help="Path to input PDF file")
    parser.add_argument("excel", nargs="?", default="testworkflowfile/asset_inventory_extraction.xlsx", help="Path to input Excel file")
    parser.add_argument("-o", "--output-dir", default="testworkflowfile", help="Output directory for generated Excel")
    parser.add_argument("-m", "--model", default="tinyllama", help="LLM Model to use (default: tinyllama)")
    parser.add_argument("--no-summary", action="store_true", help="Do not generate Compliance Summary dashboard tab")
    args = parser.parse_args()

    asyncio.run(run_main_pipeline(args.pdf, args.excel, args.output_dir, create_summary=not args.no_summary, model=args.model))


if __name__ == "__main__":
    main()
