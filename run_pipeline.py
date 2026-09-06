#!/usr/bin/env python3
"""Main Pipeline Runner for AI RFP PDF-to-Excel Automation.

Executes the PRD-compliant 5-step pipeline:
1. PDF text & table extraction + OCR fallback
2. Dynamic Excel workbook analysis & slot classification
3. Hybrid BM25 & local embedding evidence retrieval
4. Layered compliance resolution & spec extraction (100% offline)
5. In-place Excel population with formula preservation & Rule 7 yellow audit highlight
"""

import argparse
import asyncio
import sys
from pathlib import Path

from ai_rfp_excel.app.pipeline.orchestrator import PipelineOrchestrator, PipelineResult


async def run_main_pipeline(
    pdf_path: str,
    excel_path: str,
    output_dir: str = "testworkflowfile/output",
    model: str | None = None,
    concurrency: int = 2,
) -> PipelineResult:
    print("=" * 60)
    print("  MAIN PRODUCTION PIPELINE: RFP PDF-TO-EXCEL AUTOMATION")
    print(f"  AI-Native Reasoning | Concurrency: {concurrency} Workers | 100% Local")
    print("=" * 60)
    print(f"\n  [INPUT PDF]   : {pdf_path}")
    print(f"  [INPUT EXCEL] : {excel_path}")
    print(f"  [MODEL]       : {model or 'Default (qwen2.5:1.5b)'}")
    print(f"  [CONCURRENCY] : {concurrency} workers")
    print(f"  [OUTPUT DIR]  : {output_dir}")

    async def cli_progress(pct: float, message: str) -> None:
        print(f"  [{pct:5.1f}%] {message}")

    orchestrator = PipelineOrchestrator(progress_callback=cli_progress)
    result = await orchestrator.run(
        pdf_path=pdf_path,
        excel_path=excel_path,
        output_dir=output_dir,
        model_name=model,
        concurrency=concurrency,
    )

    print("\n" + "=" * 60)
    print("  PIPELINE EXECUTION SUMMARY")
    print("=" * 60)
    print(f"  Total Requirements: {result.total_requirements}")
    print(f"  Compliant:          {result.compliant_count}")
    print(f"  Partially Compliant:{result.partially_compliant_count}")
    print(f"  Non-Compliant:      {result.non_compliant_count}")
    print(f"  Not Found:          {result.not_found_count}")
    print(f"  Ambiguous:          {result.ambiguous_count}")
    print(f"  Needs Review:       {result.needs_review_count} (highlighted yellow)")
    print(f"  Elapsed Time:       {result.elapsed_seconds:.2f}s ({result.elapsed_seconds / 60:.1f}m)")
    print(f"  Generated File:     {result.output_excel_path}")
    print("=" * 60)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run main AI RFP PDF-to-Excel pipeline.")
    parser.add_argument("pdf", nargs="?", default="testworkflowfile/refernce.pdf", help="Path to input PDF file")
    parser.add_argument("excel", nargs="?", default="testworkflowfile/evaluation_round2_compute_specs.xlsx", help="Path to input Excel file")
    parser.add_argument("-o", "--output-dir", default="testworkflowfile/output", help="Output directory for generated Excel")
    parser.add_argument("-m", "--model", default=None, help="LLM Model to use (e.g. qwen2.5:1.5b)")
    parser.add_argument("-c", "--concurrency", type=int, default=2, help="Number of concurrent workers (default: 2)")
    args = parser.parse_args()

    pdf_p = Path(args.pdf)
    excel_p = Path(args.excel)

    if not pdf_p.exists():
        # Fallback to test files if default not found
        sample_pdfs = list(Path("testworkflowfile").glob("*.pdf"))
        if sample_pdfs:
            pdf_p = sample_pdfs[0]
            print(f"Using found PDF: {pdf_p}")
        else:
            print(f"Error: PDF file {args.pdf} not found.", file=sys.stderr)
            sys.exit(1)

    if not excel_p.exists():
        sample_excels = list(Path("testworkflowfile").glob("*.xlsx"))
        if sample_excels:
            excel_p = sample_excels[0]
            print(f"Using found Excel: {excel_p}")
        else:
            print(f"Error: Excel file {args.excel} not found.", file=sys.stderr)
            sys.exit(1)

    asyncio.run(
        run_main_pipeline(
            pdf_path=str(pdf_p),
            excel_path=str(excel_p),
            output_dir=args.output_dir,
            model=args.model,
            concurrency=args.concurrency,
        )
    )


if __name__ == "__main__":
    main()
