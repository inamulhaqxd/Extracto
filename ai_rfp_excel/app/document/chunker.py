import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DocumentChunk:
    """Represents a discrete semantic chunk of a document with citation metadata."""

    chunk_id: str
    text: str
    page_number: int
    section: str | None = None
    chunk_type: str = "text"  # "text", "table", "ocr", "spec"
    metadata: dict[str, Any] = field(default_factory=dict)


def clean_text(text: str) -> str:
    """Clean whitespace and unwanted control characters."""
    if not text:
        return ""
    # Normalize unicode whitespace and multiple newlines
    cleaned = re.sub(r"[ \t]+", " ", text)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def chunk_document(
    pages_text: list[dict[str, Any]],
    tables: list[dict[str, Any]] | None = None,
    ocr_blocks: list[dict[str, Any]] | None = None,
    max_chunk_chars: int = 800,
    overlap_chars: int = 150,
) -> list[DocumentChunk]:
    """
    Split document pages, tables, and OCR into semantic chunks tagged by page number.

    pages_text: list of dicts with keys 'page' (int) and 'text' (str)
    tables: list of dicts with keys 'page' (int) and 'rows' (list of list of str)
    ocr_blocks: list of dicts with keys 'page' (int) and 'text' (str)
    """
    chunks: list[DocumentChunk] = []
    chunk_idx = 0

    # 1. Process Native Page Text
    for page_info in pages_text:
        page_num = page_info.get("page", 1)
        raw_text = page_info.get("text", "")
        if not raw_text or not raw_text.strip():
            continue

        cleaned = clean_text(raw_text)
        # Split into logical paragraphs or double-newline blocks
        paragraphs = [p.strip() for p in cleaned.split("\n\n") if p.strip()]

        current_block: list[str] = []
        current_len = 0
        current_section = None

        for p in paragraphs:
            # Check if paragraph looks like a section heading (short, capitalised or starts with numbering)
            if len(p) < 80 and ("\n" not in p) and (p.isupper() or re.match(r"^(\d+[\.\)]|[A-Z][\.\)])\s+", p)):
                current_section = p

            p_len = len(p)
            if current_len + p_len > max_chunk_chars and current_block:
                chunk_idx += 1
                chunks.append(
                    DocumentChunk(
                        chunk_id=f"chunk_{chunk_idx}_p{page_num}",
                        text="\n\n".join(current_block),
                        page_number=page_num,
                        section=current_section,
                        chunk_type="text",
                        metadata={"page": page_num},
                    )
                )
                # Keep last paragraph for overlap if it's small
                if current_block and len(current_block[-1]) <= overlap_chars:
                    current_block = [current_block[-1], p]
                    current_len = len(current_block[0]) + p_len
                else:
                    current_block = [p]
                    current_len = p_len
            else:
                current_block.append(p)
                current_len += p_len

        if current_block:
            chunk_idx += 1
            chunks.append(
                DocumentChunk(
                    chunk_id=f"chunk_{chunk_idx}_p{page_num}",
                    text="\n\n".join(current_block),
                    page_number=page_num,
                    section=current_section,
                    chunk_type="text",
                    metadata={"page": page_num},
                )
            )

    # 2. Process Tables (structured representation)
    if tables:
        for t_idx, table_info in enumerate(tables):
            page_num = table_info.get("page", 1)
            rows = table_info.get("rows", [])
            if not rows or len(rows) < 2:
                continue

            # Format table as clean pipe-separated lines
            header = " | ".join(rows[0])
            table_lines = [f"Table (Page {page_num}):", f"Header: {header}"]
            for row in rows[1:]:
                row_str = " | ".join(str(c).strip() for c in row if str(c).strip())
                if row_str:
                    table_lines.append(f"- {row_str}")

            chunk_idx += 1
            chunks.append(
                DocumentChunk(
                    chunk_id=f"chunk_{chunk_idx}_table_p{page_num}_{t_idx}",
                    text="\n".join(table_lines),
                    page_number=page_num,
                    section=f"Table {t_idx+1}",
                    chunk_type="table",
                    metadata={"page": page_num, "table_index": t_idx},
                )
            )

    # 3. Process OCR blocks
    if ocr_blocks:
        for o_idx, ocr_info in enumerate(ocr_blocks):
            page_num = ocr_info.get("page", 1)
            ocr_text = clean_text(ocr_info.get("text", ""))
            if len(ocr_text) < 10:
                continue

            chunk_idx += 1
            chunks.append(
                DocumentChunk(
                    chunk_id=f"chunk_{chunk_idx}_ocr_p{page_num}_{o_idx}",
                    text=f"[OCR Content Page {page_num}]:\n{ocr_text}",
                    page_number=page_num,
                    section="OCR",
                    chunk_type="ocr",
                    metadata={"page": page_num, "ocr_index": o_idx},
                )
            )

    return chunks
