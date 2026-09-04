#!/usr/bin/env python3
"""
Step 3 Indexer: Document Chunking & Table Formatting.
Transforms raw extracted PDF data (text, tables, OCR) into structured DocumentChunks.
Strict typing only — zero Any (Rule 4). 100% offline (Rule 10).
"""

from __future__ import annotations

import re
from typing import Literal, TypedDict

SourceType = Literal["text", "table", "ocr"]


class DocumentChunk(TypedDict):
    page_number: int
    source_type: SourceType
    content: str
    table_id: str | None
    tokens: list[str]


def tokenize(text: str) -> list[str]:
    """Tokenize string into lowercase alphanumeric tokens, preserving hyphens in identifiers."""
    tokens = re.findall(r"[A-Za-z0-9]+(?:[-_:][A-Za-z0-9]+)*", text.lower())
    return [t for t in tokens if len(t) > 1 or t.isdigit()]


def split_into_paragraphs(page_text: str) -> list[str]:
    """Split page text into granular paragraphs using double-newlines or section headers."""
    raw_blocks = [b.strip() for b in re.split(r"\n\s*\n", page_text) if b.strip()]
    refined_blocks: list[str] = []
    for block in raw_blocks:
        # Split blocks that contain numbered sections, section titles, or header labels on single newlines
        section_splits = re.split(
            r"(?:\n|^)(?=(?:(?:\d+\.)+\s+[A-Z]|Section\s+\d+|Article\s+\d+|[A-Z0-9_ -]{3,}:))",
            block,
        )
        sub_blocks = [s.strip() for s in section_splits if s.strip()]
        if len(sub_blocks) > 1:
            refined_blocks.extend(sub_blocks)
        else:
            refined_blocks.append(block)
    return refined_blocks


def build_document_chunks(pdf_data: dict[str, object]) -> list[DocumentChunk]:
    """Break extracted PDF data into structured, searchable chunks."""
    chunks: list[DocumentChunk] = []
    pages_raw = pdf_data.get("pages", [])
    if not isinstance(pages_raw, list):
        return chunks

    for page_item in pages_raw:
        if not isinstance(page_item, dict):
            continue
        page_num = int(str(page_item.get("page_number", 1)))

        # 1. Native Page Text (Split by granular paragraphs/sections)
        page_text = str(page_item.get("text", "")).strip()
        if page_text:
            paragraphs = split_into_paragraphs(page_text)
            for p_text in paragraphs:
                # Normalize visual line breaks within paragraph to preserve complete sentences
                clean_paragraph = " ".join(line.strip() for line in p_text.split("\n") if line.strip())
                if len(clean_paragraph) >= 10:
                    chunks.append({
                        "page_number": page_num,
                        "source_type": "text",
                        "content": clean_paragraph,
                        "table_id": None,
                        "tokens": tokenize(clean_paragraph),
                    })

        # 2. Extracted Tables (Each row converted into a self-contained structured sentence)
        tables_raw = page_item.get("tables", [])
        if isinstance(tables_raw, list):
            for tbl in tables_raw:
                if not isinstance(tbl, dict):
                    continue
                t_id = str(tbl.get("table_id", f"T{page_num:02d}"))
                headers_raw = tbl.get("headers", [])
                headers = [str(h) for h in headers_raw] if isinstance(headers_raw, list) else []
                rows_raw = tbl.get("rows", [])
                if isinstance(rows_raw, list):
                    for r_idx, row_item in enumerate(rows_raw):
                        if not isinstance(row_item, list):
                            continue
                        row_cells = [str(c).strip() for c in row_item]
                        if not any(row_cells):
                            continue
                        row_parts: list[str] = []
                        for h_idx, cell_val in enumerate(row_cells):
                            h_name = headers[h_idx] if h_idx < len(headers) else f"Col{h_idx+1}"
                            row_parts.append(f"{h_name}: {cell_val}")
                        row_str = f"Table {t_id} (Row {r_idx+1}) -> " + " | ".join(row_parts)
                        chunks.append({
                            "page_number": page_num,
                            "source_type": "table",
                            "content": row_str,
                            "table_id": t_id,
                            "tokens": tokenize(row_str),
                        })

        # 3. OCR Text (Chunked into paragraphs)
        ocr_lines_raw = page_item.get("ocr", [])
        if isinstance(ocr_lines_raw, list) and ocr_lines_raw:
            ocr_text = " ".join(str(ol).strip() for ol in ocr_lines_raw if str(ol).strip())
            if len(ocr_text) >= 10:
                chunks.append({
                    "page_number": page_num,
                    "source_type": "ocr",
                    "content": ocr_text,
                    "table_id": None,
                    "tokens": tokenize(ocr_text),
                })

    return chunks
