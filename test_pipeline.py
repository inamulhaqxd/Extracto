#!/usr/bin/env python3
"""
Adaptive Pipeline: Generic PDF Ingestion → Hybrid BM25 Indexing → Generic Excel Structure Analysis → Targeted LLM Fill → Style-Preserving Excel Output.
Zero-crash, ultra-fast, format-agnostic.
"""

import argparse
import json
import math
import os
import re
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import openpyxl
from openpyxl.cell.cell import MergedCell
from openpyxl.styles import PatternFill
from openpyxl.utils import get_column_letter

# ─── CONFIGURATION ─────────────────────────────────────────
OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("DEFAULT_LLM_MODEL", "qwen2.5:1.5b")
DEFAULT_INPUT_DIR = Path("testworkflowfile") if Path("testworkflowfile").exists() else Path(".")
MAX_CONTEXT_CHUNKS = 3
MAX_LLM_TIMEOUT = 30.0
# ──────────────────────────────────────────────────────────

# ─── OPTIONAL COMPUTATION, OCR & NLP LIBRARIES ─────────────
try:
    import pint
    ureg = pint.UnitRegistry()
except Exception:
    ureg = None

try:
    from rapidfuzz import fuzz
except Exception:
    fuzz = None

try:
    import pytesseract
except Exception:
    pytesseract = None


def _attempt_ocr(page: Any, page_num: int) -> str:
    """Perform local OCR fallback for scanned or image-heavy PDF page."""
    if not pytesseract:
        return ""
    try:
        if hasattr(page, "render"):
            pil_img = page.render(scale=2).to_pil()
            ocr_text = pytesseract.image_to_string(pil_img)
            if ocr_text and len(ocr_text.strip()) > 10:
                print(f"    [OCR Engine] Page {page_num}: Scanned content detected, extracted {len(ocr_text)} chars via OCR.")
                return str(ocr_text)
    except Exception:
        pass
    return ""


def convert_units(val_str: str, target_unit: str) -> str | None:
    """Convert any physical measurement string to target unit dynamically (e.g., '8.008 Gbps' to 'Mbps')."""
    if not ureg or not val_str or not target_unit:
        return None
    try:
        qty = ureg(val_str.strip())
        converted = qty.to(target_unit.strip())
        return f"{converted.magnitude:g} {target_unit}"
    except Exception:
        return None
# ──────────────────────────────────────────────────────────


def _is_valid_xml_char(c: str) -> bool:
    cp = ord(c)
    return (
        cp in (0x9, 0xA, 0xD)
        or (0x20 <= cp <= 0xD7FF)
        or (0xE000 <= cp <= 0xFFFD)
        or (0x10000 <= cp <= 0x10FFFF)
    )


def _sanitize_cell_val(val: Any) -> Any:
    """Strip illegal XML non-characters (like \ufffe)."""
    if isinstance(val, str):
        return "".join(c for c in val if _is_valid_xml_char(c))
    return val


# ══════════════════════════════════════════════════════════
# BM25 RETRIEVAL DATA STRUCTURES
# ══════════════════════════════════════════════════════════
STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "cannot", "could", "did", "do",
    "does", "doing", "don't", "down", "during", "each", "few", "for", "from", "further",
    "had", "has", "have", "having", "he", "her", "here", "hers", "herself", "him",
    "himself", "his", "how", "i", "if", "in", "into", "is", "it", "its", "itself",
    "let's", "me", "more", "most", "must", "my", "myself", "no", "nor", "not", "of",
    "off", "on", "once", "only", "or", "other", "ought", "our", "ours", "ourselves",
    "out", "over", "own", "same", "she", "should", "so", "some", "such", "than", "that",
    "the", "their", "theirs", "them", "themselves", "then", "there", "these", "they",
    "this", "those", "through", "to", "too", "under", "until", "up", "very", "was",
    "we", "were", "what", "when", "where", "which", "while", "who", "whom", "why",
    "with", "would", "you", "your", "yours", "yourself", "yourselves", "please",
    "provide", "state", "indicate", "whether", "specified", "required", "following"
}


def tokenize(text: str) -> list[str]:
    """Tokenize query and text into normalized words and technical terms."""
    if not text:
        return []
    tokens = re.findall(r"[a-zA-Z0-9_\-\./]+", text.lower())
    return [t.strip(".-_") for t in tokens if len(t.strip(".-_")) > 1 and t.strip(".-_") not in STOPWORDS]


@dataclass
class DocumentChunk:
    chunk_id: str
    text: str
    page_number: int
    section: str | None = None
    chunk_type: str = "text"
    table_headers: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CanonicalFact:
    """Structured parameter fact extracted directly from technical tables and specifications."""
    entity: str
    property_name: str
    value: str
    source_section: str
    page_number: int
    context: str = ""

    @property
    def display_fact(self) -> str:
        if self.entity:
            return f"{self.entity} - {self.property_name}: {self.value}"
        return f"{self.property_name}: {self.value}"


def get_ollama_embedding(text: str, model: str = "nomic-embed-text") -> list[float] | None:
    """Get single dense vector embedding from local Ollama model."""
    if not text or not text.strip():
        return None
    try:
        res = httpx.post(
            f"{OLLAMA_URL}/api/embed",
            json={"model": model, "input": text.strip()[:1500]},
            timeout=10.0,
        )
        if res.status_code == 200:
            data = res.json()
            embs = data.get("embeddings", [])
            if embs and isinstance(embs[0], list):
                return embs[0]
    except Exception:
        pass
    try:
        res = httpx.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": model, "prompt": text.strip()[:1500]},
            timeout=10.0,
        )
        if res.status_code == 200:
            data = res.json()
            if "embedding" in data and isinstance(data["embedding"], list):
                return data["embedding"]
    except Exception:
        pass
    return None


def get_ollama_embeddings_batch(texts: list[str], model: str = "nomic-embed-text", batch_size: int = 48) -> list[list[float] | None]:
    """Get batch of dense vector embeddings efficiently using Ollama /api/embed."""
    all_embeddings: list[list[float] | None] = [None] * len(texts)
    for i in range(0, len(texts), batch_size):
        batch_slice = texts[i : i + batch_size]
        clean_inputs = [t.strip()[:1500] if t.strip() else "empty" for t in batch_slice]
        try:
            res = httpx.post(
                f"{OLLAMA_URL}/api/embed",
                json={"model": model, "input": clean_inputs},
                timeout=30.0,
            )
            if res.status_code == 200:
                embs = res.json().get("embeddings", [])
                for offset, emb in enumerate(embs):
                    if i + offset < len(texts):
                        all_embeddings[i + offset] = emb
        except Exception:
            for offset, item_text in enumerate(batch_slice):
                all_embeddings[i + offset] = get_ollama_embedding(item_text, model=model)
    return all_embeddings


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    """Compute cosine similarity between two float vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2, strict=True))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    return dot / (norm1 * norm2) if (norm1 > 0 and norm2 > 0) else 0.0


class HybridRetriever:
    """True Simultaneous Hybrid Retrieval Engine combining Lexical BM25 with Dense Vector Embeddings (nomic-embed-text) via Reciprocal Rank Fusion (RRF)."""

    def __init__(
        self,
        chunks: list[DocumentChunk],
        k1: float = 1.5,
        b: float = 0.75,
        embedding_model: str = "nomic-embed-text",
        canonical_facts: list[CanonicalFact] | None = None,
    ):
        self.chunks = chunks
        self.canonical_facts = canonical_facts or []
        self.k1 = k1
        self.b = b
        self.embedding_model = embedding_model
        self.corpus_size = len(chunks)
        self.doc_tokens: list[list[str]] = []
        self.doc_freqs: list[Counter[str]] = []
        self.doc_lengths: list[int] = []
        self.avg_doc_len: float = 0.0
        self.idf: dict[str, float] = {}
        self.chunk_embeddings: list[list[float] | None] = []
        self.query_embeddings_cache: dict[str, list[float] | None] = {}
        self.has_embeddings = False
        self._build_index()

    def _build_index(self):
        if not self.chunks:
            return
        total_len = 0
        df: Counter[str] = Counter()

        for chunk in self.chunks:
            tokens = tokenize(chunk.text)
            self.doc_tokens.append(tokens)
            doc_len = len(tokens)
            self.doc_lengths.append(doc_len)
            total_len += doc_len

            counts = Counter(tokens)
            self.doc_freqs.append(counts)
            for t in counts.keys():
                df[t] += 1

        self.avg_doc_len = (total_len / self.corpus_size) if self.corpus_size > 0 else 0.0
        for term, freq in df.items():
            self.idf[term] = math.log(1.0 + (self.corpus_size - freq + 0.5) / (freq + 0.5))

        # True Simultaneous Hybrid: Pre-compute vector embeddings with disk cache
        try:
            import hashlib
            corpus_sample = "".join(c.text[:50] for c in self.chunks[:20])
            corpus_hash = hashlib.md5(corpus_sample.encode()).hexdigest()[:8]
            cache_dir = Path(".cache")
            cache_dir.mkdir(exist_ok=True)
            cache_file = cache_dir / f"emb_{corpus_hash}_{len(self.chunks)}_{self.embedding_model.replace(':', '_')}.json"

            if cache_file.exists():
                try:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        cached_data = json.load(f)
                    if len(cached_data) == len(self.chunks):
                        self.chunk_embeddings = cached_data
                        self.has_embeddings = True
                        print(f"    [Hybrid Engine] Loaded {len(self.chunks)} cached vector embeddings from {cache_file.name} (0.01s).", flush=True)
                except Exception:
                    self.chunk_embeddings = []

            if not self.has_embeddings:
                print(f"    [Hybrid Engine] Embedding {len(self.chunks)} chunks via '{self.embedding_model}' (batch mode)...", flush=True)
                chunk_texts = [c.text for c in self.chunks]
                self.chunk_embeddings = get_ollama_embeddings_batch(chunk_texts, model=self.embedding_model)
                valid_count = sum(1 for emb in self.chunk_embeddings if emb is not None)
                if valid_count > 0:
                    self.has_embeddings = True
                    try:
                        with open(cache_file, "w", encoding="utf-8") as f:
                            json.dump(self.chunk_embeddings, f)
                    except Exception:
                        pass
                    print(f"    [Hybrid Engine] Vector Index ready: {valid_count}/{len(self.chunks)} chunks embedded & cached.", flush=True)
        except Exception as e:
            self.has_embeddings = False
            print(f"    [Hybrid Engine] Vector embedding skipped ({e}), using lexical BM25.", flush=True)

    def retrieve(self, query: str, top_k: int = 4) -> list[tuple[DocumentChunk, float]]:
        if not self.chunks or not query.strip():
            return []

        query_tokens = tokenize(query)
        if not query_tokens:
            return [(self.chunks[0], 0.0)] if self.chunks else []

        # 1. Compute BM25 scores (Lexical Keyword / SKU / Number matching)
        bm25_scores: list[float] = [0.0] * self.corpus_size
        query_lower = query.lower()
        key_terms = re.findall(r"[a-zA-Z0-9]+", query_lower)

        for i in range(self.corpus_size):
            doc_len = self.doc_lengths[i]
            freqs = self.doc_freqs[i]
            score = 0.0

            for q_term in query_tokens:
                if q_term not in freqs:
                    continue
                tf = freqs[q_term]
                idf = self.idf.get(q_term, 0.1)
                denom = tf + self.k1 * (1.0 - self.b + self.b * (doc_len / (self.avg_doc_len or 1.0)))
                score += idf * (tf * (self.k1 + 1.0)) / denom

            chunk_lower = self.chunks[i].text.lower()
            # Exact phrase bonus
            if len(query_lower) > 5 and query_lower in chunk_lower:
                score += 8.0
            # Technical term bonus
            for term in key_terms:
                if len(term) >= 3 and term in chunk_lower:
                    score += 0.8
            # Table chunk boost (Option 2)
            if self.chunks[i].chunk_type == "table":
                score += 1.5
                for header in self.chunks[i].table_headers:
                    if any(term in header.lower() for term in key_terms if len(term) >= 3):
                        score += 3.0

            bm25_scores[i] = score

        # 2. True Simultaneous Hybrid: Compute Dense Vector Semantic Ranks & Merge via RRF
        if self.has_embeddings:
            query_emb = self.query_embeddings_cache.get(query.strip())
            if query_emb is None:
                query_emb = get_ollama_embedding(query, model=self.embedding_model)
                if query_emb:
                    self.query_embeddings_cache[query.strip()] = query_emb

            if query_emb:
                vector_scores = [
                    cosine_similarity(query_emb, chunk_emb) if chunk_emb else 0.0
                    for chunk_emb in self.chunk_embeddings
                ]
                bm25_ranks = {idx: rank for rank, idx in enumerate(sorted(range(self.corpus_size), key=lambda x: bm25_scores[x], reverse=True))}
                vec_ranks = {idx: rank for rank, idx in enumerate(sorted(range(self.corpus_size), key=lambda x: vector_scores[x], reverse=True))}

                # Reciprocal Rank Fusion: 1 / (60 + rank_bm25) + 1 / (60 + rank_vec)
                rrf_scores = [
                    (1.0 / (60.0 + bm25_ranks[i])) + (1.0 / (60.0 + vec_ranks[i]))
                    for i in range(self.corpus_size)
                ]
                ranked_indices = sorted(range(self.corpus_size), key=lambda idx: rrf_scores[idx], reverse=True)
                results = []
                for idx in ranked_indices[:top_k]:
                    results.append((self.chunks[idx], round(rrf_scores[idx] * 100, 3)))
                return results

        # Fallback to pure BM25 ranking if vector embedding unavailable
        ranked_indices = sorted(range(self.corpus_size), key=lambda idx: bm25_scores[idx], reverse=True)
        results = []
        for idx in ranked_indices[:top_k]:
            if bm25_scores[idx] > 0 or len(results) == 0:
                results.append((self.chunks[idx], round(bm25_scores[idx], 3)))
        return results

    def lookup_canonical_fact(self, query: str) -> tuple[CanonicalFact | None, float]:
        """Option 4: Exact & fuzzy lookup of structured parameter facts from tables."""
        if not self.canonical_facts or not query.strip():
            return None, 0.0

        q_lower = query.lower()

        # Skip direct lookup for comparative, reasoning, or calculation queries
        reasoning_triggers = (
            "compare", "difference", "why", "calculate", "formula", "what happens",
            "does", "suggest", "how many total", "based on", "repeat the same", "between"
        )
        if any(trig in q_lower for trig in reasoning_triggers):
            return None, 0.0

        # Group candidate facts by entity
        matching_by_entity: dict[str, list[CanonicalFact]] = {}
        for fact in self.canonical_facts:
            if fact.entity and fact.entity.lower() in q_lower:
                matching_by_entity.setdefault(fact.entity, []).append(fact)

        if matching_by_entity:
            for ent, ent_facts in matching_by_entity.items():
                matched_props = []
                for f in ent_facts:
                    prop_words = [w for w in re.split(r"[^\w]+", f.property_name.lower()) if len(w) >= 3 and w not in STOPWORDS]
                    if any(w in q_lower for w in prop_words):
                        matched_props.append(f)
                if len(matched_props) == 1:
                    return matched_props[0], 0.95
                elif len(matched_props) > 1:
                    combined_val = ", ".join(f"{f.property_name}: {f.value}" for f in matched_props)
                    return CanonicalFact(
                        entity=ent,
                        property_name=" & ".join(f.property_name for f in matched_props),
                        value=combined_val,
                        source_section=matched_props[0].source_section,
                        page_number=matched_props[0].page_number
                    ), 0.98

        # Fallback: check 2-column key-value facts without entity
        for fact in self.canonical_facts:
            if not fact.entity and fact.property_name:
                p_lower = fact.property_name.lower()
                if p_lower in q_lower:
                    return fact, 0.90

        return None, 0.0

    def get_formatted_context(self, query: str, top_k: int = 4) -> str:
        top_results = self.retrieve(query, top_k=top_k)
        if not top_results:
            return "No directly matching content found in the reference document."

        formatted_parts = []
        # Prepend matching canonical structured fact if present
        fact, _ = self.lookup_canonical_fact(query)
        if fact:
            formatted_parts.append(f"--- [CANONICAL STRUCTURED FACT | {fact.source_section}] ---\n{fact.display_fact}")

        for chunk, score in top_results:
            header = f"--- [Document Excerpt | Page {chunk.page_number}"
            if chunk.section:
                header += f" | {chunk.section}"
            score_type = "Hybrid RRF Score" if self.has_embeddings else "BM25 Score"
            header += f" | {score_type}: {score}] ---"
            formatted_parts.append(f"{header}\n{chunk.text.strip()}")
        return "\n\n".join(formatted_parts)


# Backwards compatibility alias
BM25Retriever = HybridRetriever


# ══════════════════════════════════════════════════════════
# STEP 1: PDF EXTRACTION & INDEXING
# ══════════════════════════════════════════════════════════
def extract_and_index_pdf(pdf_path: Path) -> tuple[dict, BM25Retriever]:
    """Extract text from PDF (using pypdfium2 / pymupdf / pdfplumber) and build BM25 index."""
    print(f"\n{'='*60}")
    print("  STEP 1: PDF TABLE & TEXT INGESTION")
    print(f"{'='*60}")
    print(f"  File: {pdf_path}")

    start_t = time.time()
    pages_data: list[dict[str, Any]] = []
    chunks: list[DocumentChunk] = []
    canonical_facts: list[CanonicalFact] = []
    chunk_count = 0
    total_tables = 0

    # Strategy 1: pdfplumber for real tables + copyable text (Option 2)
    try:
        import pdfplumber
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page_idx, page in enumerate(pdf.pages):
                page_num = page_idx + 1

                # Option 2: Real PDF Table Extraction
                tables = page.extract_tables()
                for t_idx, table in enumerate(tables):
                    if not table or len(table) < 1:
                        continue
                    cleaned_rows: list[list[str]] = []
                    for raw_row in table:
                        clean_row = [str(c).strip().replace("\n", " ") if c is not None else "" for c in raw_row]
                        if any(clean_row):
                            cleaned_rows.append(clean_row)
                    if not cleaned_rows:
                        continue

                    total_tables += 1
                    headers = cleaned_rows[0]
                    data_rows = cleaned_rows[1:] if len(cleaned_rows) > 1 else cleaned_rows

                    # Option 4: Canonical Structured Fact Extraction
                    source_label = f"Table {t_idx+1} (Page {page_num})"
                    if len(headers) >= 2:
                        for r_item in data_rows:
                            if not r_item or not any(r_item):
                                continue
                            if len(headers) == 2:
                                prop = str(r_item[0]).strip()
                                val = str(r_item[1]).strip() if len(r_item) > 1 else ""
                                if prop and val and len(prop) < 80 and len(val) < 200:
                                    canonical_facts.append(CanonicalFact(
                                        entity="",
                                        property_name=prop,
                                        value=val,
                                        source_section=source_label,
                                        page_number=page_num,
                                    ))
                            else:
                                ent = str(r_item[0]).strip()
                                for c_idx in range(1, min(len(headers), len(r_item))):
                                    prop = str(headers[c_idx]).strip()
                                    val = str(r_item[c_idx]).strip()
                                    if ent and prop and val and len(val) < 200:
                                        canonical_facts.append(CanonicalFact(
                                            entity=ent,
                                            property_name=prop,
                                            value=val,
                                            source_section=source_label,
                                            page_number=page_num,
                                        ))

                    md_lines = []
                    header_str = " | ".join(h if h else "-" for h in headers)
                    md_lines.append(f"| {header_str} |")
                    md_lines.append("| " + " | ".join("---" for _ in headers) + " |")
                    for row in data_rows:
                        padded = row + [""] * max(0, len(headers) - len(row))
                        md_lines.append("| " + " | ".join(padded[:len(headers)]) + " |")

                    table_text = "\n".join(md_lines)
                    chunk_count += 1
                    chunks.append(DocumentChunk(
                        chunk_id=f"chk_tbl_{page_num}_{t_idx+1}",
                        text=f"Table {t_idx+1} (Page {page_num}):\n{table_text}",
                        page_number=page_num,
                        section=f"Table {t_idx+1}",
                        chunk_type="table",
                        table_headers=[h for h in headers if h],
                    ))

                text = _sanitize_cell_val(page.extract_text() or "")
                if len(text.strip()) < 25:
                    ocr_text = _attempt_ocr(page, page_num)
                    if ocr_text:
                        text = _sanitize_cell_val(ocr_text)
                pages_data.append({"page": page_num, "text": text})
    except Exception:
        # Strategy 2: pypdfium2 fallback
        try:
            import pypdfium2 as pdfium
            pdf = pdfium.PdfDocument(str(pdf_path))
            for i, page in enumerate(pdf):
                text = _sanitize_cell_val(page.get_textpage().get_text_range() or "")
                if len(text.strip()) < 25:
                    ocr_text = _attempt_ocr(page, i + 1)
                    if ocr_text:
                        text = _sanitize_cell_val(ocr_text)
                pages_data.append({"page": i + 1, "text": text})
        except Exception as e2:
            raise RuntimeError(f"Failed to extract PDF text: {e2}") from e2

    total_pages = len(pages_data)
    print(f"  Total Pages: {total_pages} | Extracted Tables: {total_tables}")

    for p_info in pages_data:
        p_num = int(p_info["page"])
        raw_text = str(p_info.get("text", "")).strip()
        if not raw_text:
            continue

        # Detect section headings and chunk semantically
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        curr_p: list[str] = []
        curr_len = 0
        curr_sec = None

        for line in lines:
            is_heading = False
            if len(line) < 70 and not line.endswith((".", ",", ";", ":")):
                if line.isupper() and len(line) >= 3 and not re.search(r"\d", line):
                    is_heading = True
                elif re.match(r"^(?:Section\s+\d+|[0-9]+[\.\)]|[A-Z][\.\)])\s+", line, re.IGNORECASE):
                    is_heading = True
                else:
                    words = [w for w in re.split(r"[\s/]+", line) if w]
                    if 1 <= len(words) <= 6 and all(w[0].isupper() or w.lower() in ("and", "or", "the", "of", "in", "to", "for", "on", "with", "&", "-", "--") for w in words):
                        if not any(w.lower() in ("table", "value", "attribute", "unit", "units", "yes", "no") for w in words):
                            is_heading = True

            if is_heading and curr_p:
                chunk_count += 1
                chunks.append(DocumentChunk(
                    chunk_id=f"chk_{chunk_count}",
                    text="\n".join(curr_p),
                    page_number=p_num,
                    section=curr_sec,
                    chunk_type="text",
                ))
                curr_p = [line]
                curr_len = len(line)
                curr_sec = line
            else:
                if is_heading:
                    curr_sec = line
                if curr_len + len(line) > 800 and curr_p:
                    chunk_count += 1
                    chunks.append(DocumentChunk(
                        chunk_id=f"chk_{chunk_count}",
                        text="\n".join(curr_p),
                        page_number=p_num,
                        section=curr_sec,
                        chunk_type="text",
                    ))
                    curr_p = [line]
                    curr_len = len(line)
                else:
                    curr_p.append(line)
                    curr_len += len(line)

        if curr_p:
            chunk_count += 1
            chunks.append(DocumentChunk(
                chunk_id=f"chk_{chunk_count}",
                text="\n\n".join(curr_p),
                page_number=p_num,
                section=curr_sec,
                chunk_type="text",
            ))

    # Build BM25 Index with Canonical Facts
    retriever = BM25Retriever(chunks, canonical_facts=canonical_facts)
    elapsed = time.time() - start_t

    total_chars = sum(len(str(p.get("text", ""))) for p in pages_data)
    print(f"  Indexed: {len(chunks)} chunks across {total_pages} pages ({total_chars:,} chars)")
    print(f"  Canonical Facts Registry: {len(canonical_facts)} structured facts extracted")
    print(f"  Indexing completed in {elapsed:.2f}s")

    raw_data = {
        "pages": pages_data,
        "total_pages": total_pages,
        "total_chunks": len(chunks),
    }
    return raw_data, retriever


# ══════════════════════════════════════════════════════════
# STEP 2: GENERIC EXCEL ANALYSIS (with Merged Header Support)
# ══════════════════════════════════════════════════════════
COLUMN_TYPE_KEYWORDS = {
    "compliance": ["compliance", "comply", "yes/no", "y/n", "status", "conformance", "fulfillment", "meet/not meet", "compliance/marks"],
    "total_marks": ["total marks", "max marks", "max score", "weight", "weightage"],
    "marks": ["marks obtained", "score obtained", "points obtained", "marks", "score"],
    "remarks": ["remarks", "notes", "comments", "source section", "source", "reference", "citation", "evidence", "justification"],
    "question": ["question", "questions", "query", "queries", "field to extract", "field", "extract", "prompt", "item to check", "attribute"],
    "answer": ["answer", "ai answer", "response", "reply", "solution", "vendor answer"],
    "description": ["description", "spec", "specification", "specifications", "requirement", "requirements", "details", "parameter", "feature", "scope"],
    "item": ["item", "items", "component", "sub-item"],
    "serial": ["s#", "s no", "s no.", "serial", "#", "s.n", "sr", "sr.", "sr no", "item #"],
    "proposed": ["proposed", "offered", "bidder response", "make/model", "proposed spec"],
}


def classify_column(header_text: str) -> str:
    text = header_text.lower().strip().strip("'\"")
    for col_type, keywords in COLUMN_TYPE_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                return col_type
            if fuzz and len(text) >= 3 and fuzz.partial_ratio(kw, text) >= 88:
                return col_type
    return "unknown"


# ─── PRD 5-STATE COMPLIANCE MODEL & DYNAMIC SCORING (Option 5) ───
STATE_COMPLIANT = "COMPLIANT"
STATE_PARTIALLY_COMPLIANT = "PARTIALLY_COMPLIANT"
STATE_NON_COMPLIANT = "NON_COMPLIANT"
STATE_NOT_FOUND = "NOT_FOUND"
STATE_AMBIGUOUS = "AMBIGUOUS"


def detect_compliance_style(headers: dict[int, str], ws, data_start_row: int) -> str:
    """Detect the expected compliance vocabulary convention from the template."""
    all_header_text = " ".join(headers.values()).lower()
    if "fc" in all_header_text or "fc/pc/nc" in all_header_text or "comply/partially/not" in all_header_text:
        return "FC/PC/NC"
    if "yes/no" in all_header_text or "y/n" in all_header_text:
        return "YES/NO"

    for r in range(data_start_row, min(data_start_row + 15, (ws.max_row or 1) + 1)):
        for col_idx, h_text in headers.items():
            if classify_column(h_text) == "compliance":
                val = str(ws.cell(row=r, column=col_idx).value or "").strip().upper()
                if val in ("YES", "NO", "Y", "N", "MEET", "NOT MEET"):
                    return "YES/NO"
                if "COMPLIANT" in val:
                    return "COMPLIANT/NON-COMPLIANT"
                if val in ("FC", "PC", "NC"):
                    return "FC/PC/NC"

    return "FC/PC/NC"


def format_compliance_label(state: str, style: str) -> str:
    """Format PRD compliance state into the workbook's detected convention."""
    if style == "YES/NO":
        mapping = {
            STATE_COMPLIANT: "Yes",
            STATE_PARTIALLY_COMPLIANT: "Partial",
            STATE_NON_COMPLIANT: "No",
            STATE_NOT_FOUND: "No",
            STATE_AMBIGUOUS: "Ambiguous",
        }
    elif style == "COMPLIANT/NON-COMPLIANT":
        mapping = {
            STATE_COMPLIANT: "Compliant",
            STATE_PARTIALLY_COMPLIANT: "Partially Compliant",
            STATE_NON_COMPLIANT: "Non-Compliant",
            STATE_NOT_FOUND: "Not Found",
            STATE_AMBIGUOUS: "Ambiguous",
        }
    else:  # FC/PC/NC
        mapping = {
            STATE_COMPLIANT: "FC",
            STATE_PARTIALLY_COMPLIANT: "PC",
            STATE_NON_COMPLIANT: "NC",
            STATE_NOT_FOUND: "NC",
            STATE_AMBIGUOUS: "Ambiguous",
        }
    return mapping.get(state, state)


def calculate_dynamic_marks(state: str, max_marks: float | None, default_weight: float = 10.0) -> str:
    """Dynamically scale score obtained based on template weight (removes hardcoded 10/5/0)."""
    effective_max = max_marks if (max_marks is not None and max_marks > 0) else default_weight
    if state == STATE_COMPLIANT:
        return f"{effective_max:g}"
    elif state == STATE_PARTIALLY_COMPLIANT:
        return f"{effective_max * 0.5:g}"
    else:
        return "0"


def format_total_marks(max_marks: float | None, is_preference: bool = False, existing_val: Any = None) -> str:
    """Format total marks column respecting existing template weights without hardcoded strings."""
    if existing_val is not None and str(existing_val).strip():
        return str(existing_val).strip()
    if max_marks is not None and max_marks > 0:
        return f"{max_marks:g}"
    return ""


def get_merged_cell_value(ws, row: int, col: int) -> Any:
    """Retrieve cell value respecting merged cell ranges."""
    val = ws.cell(row=row, column=col).value
    if val is not None:
        return val
    for rng in ws.merged_cells.ranges:
        if rng.min_row <= row <= rng.max_row and rng.min_col <= col <= rng.max_col:
            return ws.cell(row=rng.min_row, column=rng.min_col).value
    return None


def analyze_excel(excel_path: Path) -> dict:
    """Analyze arbitrary Excel templates detecting multi-level headers, sections, and empty slots."""
    print(f"\n{'='*60}")
    print("  STEP 2: EXCEL STRUCTURE & SLOT ANALYSIS")
    print(f"{'='*60}")
    print(f"  File: {excel_path}")

    wb = openpyxl.load_workbook(str(excel_path), data_only=False)
    result = {"sheets": [], "all_slots": []}

    fill_types = {"compliance", "total_marks", "marks", "remarks", "answer", "proposed", "unknown"}

    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        print(f"\n  Sheet: '{sheet_name}' ({ws.max_row} rows x {ws.max_column} cols)")

        if ws.max_row is None or ws.max_row < 1:
            continue

        # Detect Header Row (and potential subheader row)
        header_row = None
        headers: dict[int, str] = {}

        for r in range(1, min(15, ws.max_row + 1)):
            labels = []
            for c in range(1, ws.max_column + 1):
                val = get_merged_cell_value(ws, r, c)
                if val is not None and len(str(val).strip()) < 45:
                    labels.append(str(val).strip())

            if len(labels) >= 2:
                header_row = r
                break

        if not header_row:
            print("    No valid header row found — skipping sheet")
            continue

        # Check if the next row is a sub-header row (e.g. Compliance / Marks)
        has_sub_header = False
        sub_row = header_row + 1
        if sub_row <= ws.max_row:
            sub_labels = []
            for c in range(1, ws.max_column + 1):
                v_main = get_merged_cell_value(ws, header_row, c)
                v_sub = get_merged_cell_value(ws, sub_row, c)
                if v_sub is not None and v_sub != v_main and len(str(v_sub).strip()) < 45:
                    sub_labels.append(str(v_sub).strip())
            if len(sub_labels) >= 2:
                has_sub_header = True

        # Build composite headers
        data_start_row = (header_row + 2) if has_sub_header else (header_row + 1)
        for c in range(1, ws.max_column + 1):
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

        col_types = {col: classify_column(text) for col, text in headers.items()}
        compliance_style = detect_compliance_style(headers, ws, data_start_row)
        print(f"    Detected Compliance Style: [{compliance_style}]")

        for col, h_text in headers.items():
            col_letter = get_column_letter(col)
            print(f"    Col {col_letter}: '{h_text[:35]}' -> [{col_types[col]}]")

        # Find context columns
        context_col = None
        desc_col = None
        serial_col = None
        total_marks_col = None

        for col, ct in col_types.items():
            if ct in ("question", "item") and not context_col:
                context_col = col
            elif ct == "description" and not desc_col:
                desc_col = col
            elif ct == "serial" and not serial_col:
                serial_col = col
            elif ct == "total_marks" and not total_marks_col:
                total_marks_col = col

        # If only description exists, make it context_col
        if not context_col and desc_col:
            context_col = desc_col
            desc_col = None
        elif not context_col:
            context_col = 1
            col_types[context_col] = "question"

        sheet_slots = []
        current_section = ""

        # Dynamically infer sheet-wide default weight from total_marks column
        sheet_default_marks = 10.0
        if total_marks_col:
            detected_weights: list[float] = []
            for r in range(data_start_row, ws.max_row + 1):
                v = ws.cell(row=r, column=total_marks_col).value
                if v is not None:
                    try:
                        n = float(re.sub(r"[^\d\.]", "", str(v)))
                        if n > 0:
                            detected_weights.append(n)
                    except Exception:
                        pass
            if detected_weights:
                sheet_default_marks = Counter(detected_weights).most_common(1)[0][0]

        for row in range(data_start_row, ws.max_row + 1):
            row_cells = [ws.cell(row=row, column=c).value for c in range(1, ws.max_column + 1)]
            if not any(v is not None and str(v).strip() for v in row_cells):
                continue  # Skip empty row

            s_val = get_merged_cell_value(ws, row, serial_col) if serial_col else None
            c_val = get_merged_cell_value(ws, row, context_col) if context_col else None
            d_val = get_merged_cell_value(ws, row, desc_col) if desc_col else None
            row_max_marks = ws.cell(row=row, column=total_marks_col).value if total_marks_col else None
            parsed_max_marks = None
            if row_max_marks is not None:
                try:
                    parsed_max_marks = float(re.sub(r"[^\d\.]", "", str(row_max_marks)))
                except Exception:
                    parsed_max_marks = None

            # Check if row is a Section Header row (e.g. S# = 'A', Item = 'Server without GPU Cards', no desc)
            is_section_row = False
            if serial_col and s_val and str(s_val).strip().isalpha() and len(str(s_val).strip()) <= 2:
                if c_val and not d_val:
                    is_section_row = True

            if is_section_row:
                current_section = str(c_val).strip()
                continue

            # Build full row context
            context_parts = []
            if current_section:
                context_parts.append(f"[{current_section}]")
            if c_val:
                context_parts.append(str(c_val).strip())
            if d_val and str(d_val).strip() != str(c_val).strip():
                context_parts.append(f"Description: {str(d_val).strip()}")

            full_context = " ".join(context_parts)
            if not full_context:
                # Fallback: take first non-empty text cell in row
                for c in range(1, ws.max_column + 1):
                    val = ws.cell(row=row, column=c).value
                    if val and len(str(val).strip()) > 5:
                        full_context = str(val).strip()
                        break

            serial_str = str(s_val).strip() if s_val else ""

            # Check if row is a Note / Instructions row (Option 1)
            is_note_row = (
                serial_str.lower().startswith("note")
                or full_context.lower().startswith("note:")
                or "instructions to bidder" in full_context.lower()
                or "guidelines to bidder" in full_context.lower()
            )
            if is_note_row:
                continue  # Preserve note in original sheet, do not evaluate as a fillable specification

            # Check if row is a Total / Summary row (Option 3)
            is_total_row = any(
                term in full_context.lower() or term in serial_str.lower()
                for term in ("total marks", "grand total", "total score", "sub total", "sub-total")
            ) or (serial_str.lower() in ("total", "grand total") and not d_val)

            # Find empty fillable target cells
            for col, ct in col_types.items():
                if ct not in fill_types:
                    continue
                if col in (context_col, desc_col, serial_col):
                    continue

                cell = ws.cell(row=row, column=col)
                # If cell is already filled with user data or formula, preserve it
                if cell.value is not None and str(cell.value).strip():
                    if str(cell.value).strip().startswith("="):
                        continue

                cell_ref = f"{get_column_letter(col)}{row}"
                col_letter = get_column_letter(col)

                # Option 3: Auto-generate dynamic Excel formula for Total rows
                if is_total_row and ct in ("marks", "total_marks"):
                    formula_val = f"=SUM({col_letter}{data_start_row}:{col_letter}{row-1})"
                    slot = {
                        "sheet": sheet_name,
                        "row": row,
                        "col": col,
                        "cell_ref": cell_ref,
                        "col_type": ct,
                        "header": headers.get(col, ""),
                        "context": full_context,
                        "serial": serial_str,
                        "generated_value": formula_val,
                        "confidence": 1.0,
                        "is_formula": True,
                        "compliance_style": compliance_style,
                        "max_marks": parsed_max_marks,
                        "sheet_default_marks": sheet_default_marks,
                    }
                    sheet_slots.append(slot)
                    continue

                slot = {
                    "sheet": sheet_name,
                    "row": row,
                    "col": col,
                    "cell_ref": cell_ref,
                    "col_type": ct,
                    "header": headers.get(col, ""),
                    "context": full_context,
                    "serial": serial_str,
                    "compliance_style": compliance_style,
                    "max_marks": parsed_max_marks,
                    "sheet_default_marks": sheet_default_marks,
                    "existing_value": cell.value,
                }
                sheet_slots.append(slot)

        result["sheets"].append({
            "name": sheet_name,
            "header_row": header_row,
            "headers": headers,
            "col_types": col_types,
            "compliance_style": compliance_style,
            "slot_count": len(sheet_slots),
        })
        result["all_slots"].extend(sheet_slots)
        print(f"    Fillable slots detected: {len(sheet_slots)}")

    wb.close()
    return result


# ══════════════════════════════════════════════════════════
# STEP 3: HIGH-SPEED HYBRID LLM FILL
# ══════════════════════════════════════════════════════════
def get_available_ollama_model(preferred: str | None = None) -> str | None:
    """Detect available models in local Ollama."""
    target = preferred or os.environ.get("DEFAULT_LLM_MODEL", OLLAMA_MODEL)
    try:
        with httpx.Client(timeout=3.0) as client:
            res = client.get(f"{OLLAMA_URL}/api/tags")
            if res.status_code == 200:
                models = res.json().get("models", [])
                if models:
                    names = [str(m.get("name", "")) for m in models]
                    if target:
                        for n in names:
                            if target.lower() in n.lower() or n.lower() in target.lower():
                                return n
                    # Check preferred models
                    for pref in ["tinyllama", "qwen", "llama", "mistral"]:
                        for n in names:
                            if pref in n.lower():
                                return n
                    if names:
                        return names[0]
    except Exception:
        pass
    return None


def call_ollama(prompt: str, is_json: bool = True, model_override: str | None = None) -> dict[str, Any] | str:
    """Call local Ollama with structured response parsing."""
    active_model = model_override or get_available_ollama_model() or OLLAMA_MODEL
    try:
        with httpx.Client(timeout=MAX_LLM_TIMEOUT) as client:
            payload = {
                "model": active_model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "keep_alive": "10m",
                "options": {
                    "temperature": 0.1,
                    "num_ctx": 2048,
                    "num_predict": 128,
                },
            }
            if is_json:
                payload["format"] = "json"

            res = client.post(f"{OLLAMA_URL}/api/chat", json=payload)
            if res.status_code == 404:
                return {"error": f"Model '{active_model}' not found in Ollama"}
            res.raise_for_status()
            res_data = res.json()
            content = str(res_data.get("message", {}).get("content", ""))

            if not is_json:
                return content.strip()

            clean = content.strip()
            if clean.startswith("```"):
                lines = clean.split("\n")
                clean = "\n".join(lines[1:-1])

            parsed = json.loads(clean)
            return parsed if isinstance(parsed, dict) else {"result": parsed}
    except Exception as e:
        return {"error": str(e)}


def _pinpoint_value(context: str, text: str) -> str:
    """Generic fallback: extracts key-value pair or shortest matching snippet from text."""
    if not text or not text.strip():
        return "Not Found in Reference Document"

    f_lower = context.lower().strip()
    query_terms = [
        w for w in re.split(r"[^\w\+\%]+", f_lower)
        if len(w) >= 3 and w not in ("amount", "number", "field", "extract", "typical", "standard", "units", "value", "state", "indicate", "what", "which", "list", "approximate")
    ]

    # 1. Exact Key-Value Pattern Match: "Term: Value" or "Term \t Value" or "Term Value"
    for line in text.split("\n"):
        line_clean = line.strip()
        if not line_clean or len(line_clean) < 3:
            continue
        line_lower = line_clean.lower()
        if any(h in line_lower for h in ("specification", "attribute", "parameter", "description")) and any(v in line_lower for v in ("value", "status", "detail", "response")):
            continue
        for term in query_terms:
            if term in line_lower:
                m = re.search(rf"(?i)\b{re.escape(term)}[^\w\n]*\s*[:\-\t]\s*([^\n\r]+)", line_clean)
                if m:
                    cand = m.group(1).strip()
                    cand = re.sub(r"\[Source:.*\]", "", cand).strip()
                    if cand and 1 <= len(cand.split()) <= 12:
                        return cand

    # 2. Shortest sentence containing query terms
    sentences = [s.strip() for s in re.split(r"(?<=[.!?\n])\s+", text) if len(s.strip()) > 5]
    if sentences:
        scored = sorted(
            sentences,
            key=lambda s: (sum(3 for t in query_terms if t in s.lower()), -len(s.split())),
            reverse=True,
        )
        cand = scored[0]
        words = cand.split()
        if len(words) > 8:
            return " ".join(words[:8])
        return cand

    return "Not Found in Reference Document"


def _find_nearest_section(chunk: DocumentChunk | None, query: str) -> str:
    """Find the specific section heading within the chunk closest to the matching query context."""
    if not chunk:
        return "Page 1"
    text = chunk.text
    page = chunk.page_number
    f_lower = query.lower()
    query_terms = [w for w in re.split(r"[^\w\+\%]+", f_lower) if len(w) >= 3]

    lines = [line.strip() for line in text.split("\n") if line.strip()]
    current_sec = chunk.section or None
    best_sec = current_sec

    for line in lines:
        # Check if line is a section heading
        if len(line) < 65 and not line.endswith((".", ",", ";", ":")):
            if line.isupper() and len(line) >= 3 and not re.search(r"\d", line):
                current_sec = line.title()
            elif re.match(r"^(?:Section\s+\d+|[0-9]+[\.\)]|[A-Z][\.\)])\s+", line, re.IGNORECASE):
                current_sec = line
            elif not re.search(r"\d", line):
                words = [w for w in re.split(r"[\s/]+", line) if w]
                if 1 <= len(words) <= 6 and all(w[0].isupper() or w.lower() in ("and", "or", "the", "of", "in", "to", "for", "on", "with", "&", "-", "--") for w in words):
                    if not any(w.lower() in ("table", "value", "attribute", "unit", "units", "yes", "no", "first", "last", "model", "manufacturer", "specification") for w in words):
                        current_sec = line

        # If this line contains query terms, associate it with the current section
        if any(term in line.lower() for term in query_terms if len(term) >= 3):
            if current_sec:
                best_sec = current_sec

    if best_sec:
        return f"{best_sec} (Page {page})"
    return f"Page {page}"


def extractive_fallback(slot: dict, top_chunk: DocumentChunk | None, is_preference: bool, compliance_status: str = STATE_COMPLIANT) -> str:
    """Domain-aware fallback extraction with dynamic scoring, concise answers, and exact citations."""
    col_type = slot["col_type"]
    max_marks = slot.get("max_marks")
    style = slot.get("compliance_style", "FC/PC/NC")

    if col_type == "total_marks":
        return format_total_marks(max_marks, is_preference, slot.get("existing_value"))

    if col_type == "marks":
        state = compliance_status if compliance_status in (STATE_COMPLIANT, STATE_PARTIALLY_COMPLIANT, STATE_NON_COMPLIANT, STATE_NOT_FOUND, STATE_AMBIGUOUS) else (
            STATE_COMPLIANT if compliance_status == "FC" else (STATE_PARTIALLY_COMPLIANT if compliance_status == "PC" else STATE_NON_COMPLIANT)
        )
        return calculate_dynamic_marks(state, max_marks, default_weight=slot.get("sheet_default_marks", 10.0))

    if not top_chunk or not top_chunk.text.strip():
        if col_type == "compliance":
            return format_compliance_label(STATE_NON_COMPLIANT, style)
        return "Not Found in Reference Document"

    text = top_chunk.text.strip()
    context_str = slot.get("context", "")

    if col_type == "compliance":
        state = compliance_status if compliance_status in (STATE_COMPLIANT, STATE_PARTIALLY_COMPLIANT, STATE_NON_COMPLIANT, STATE_NOT_FOUND, STATE_AMBIGUOUS) else STATE_COMPLIANT
        return format_compliance_label(state, style)
    elif col_type in ("remarks", "source"):
        return _find_nearest_section(top_chunk, context_str)
    elif col_type in ("answer", "proposed"):
        return _pinpoint_value(context_str, text)
    else:
        return _pinpoint_value(context_str, text)


def classify_question_type(subject: str) -> str:
    """Phase 3: Classify question type before matching to route authoritatively to the right tool/layer."""
    s_lower = subject.lower()
    if any(k in s_lower for k in ("duration", "how long", "time taken", "elapsed", "calculate", "total", "sum", "percentage", "in mbps", "in gbps", "in watts", "in w", "in usd", "$")):
        return "COMPUTATION"
    elif any(k in s_lower for k in ("compliance", "compliant", "mandatory", "fc", "pc", "nc", "marks", "score")):
        return "BOOLEAN_RULE"
    return "DIRECT_FACT"


def verify_grounding_independently(answer: str, cited_text: str) -> float:
    """Phase 5: Independently check whether the answer's specific tokens appear verbatim in the cited document excerpt."""
    if not answer or answer in ("Not specified in report", "Not Found in Reference Document", "N/A"):
        return 0.50
    if not cited_text:
        return 0.30

    ans_clean = answer.strip().lower()
    text_clean = cited_text.lower()

    # Exact string match in source text
    if ans_clean in text_clean:
        return 1.0

    # Key entity / number token overlap
    tokens = [t for t in re.findall(r"[a-zA-Z0-9]+", ans_clean) if len(t) > 1 and t not in STOPWORDS]
    if not tokens:
        return 0.85

    matches = sum(1 for t in tokens if t in text_clean)
    ratio = matches / len(tokens)
    if ratio >= 0.75:
        return 0.95
    elif ratio >= 0.50:
        return 0.80
    else:
        return 0.40


def calculate_calibrated_confidence(retrieval_score: float, grounding_score: float, is_negative: bool, is_long: bool) -> float:
    """Phase 6: Objectively calibrate confidence from evidence signals (retrieval + grounding) instead of LLM self-grading."""
    if is_negative:
        return 0.50
    if is_long:
        return 0.65
    norm_retrieval = min(1.0, max(0.3, retrieval_score / 10.0 if retrieval_score > 1.0 else retrieval_score))
    calibrated = (0.35 * norm_retrieval) + (0.50 * grounding_score) + 0.15
    return round(min(1.0, max(0.1, calibrated)), 2)


def _eval_single_row(
    row_info: tuple[int, str, int, list[dict]],
    retriever: HybridRetriever,
    active_model: str | None,
) -> list[dict]:
    """Process a single requirement row with Hybrid context retrieval, LLM evaluation, and deterministic scoring."""
    _, _, row_num, slots = row_info
    # Instant resolve for pre-calculated Excel formula rows
    if all(s.get("is_formula", False) for s in slots):
        return slots

    first_slot = slots[0]
    context = first_slot.get("context", "")
    serial = first_slot.get("serial", "")
    style = first_slot.get("compliance_style", "FC/PC/NC")
    max_marks = first_slot.get("max_marks")

    subject = context or f"Row {row_num}"
    if serial:
        subject = f"[{serial}] {subject}"

    # Phase 3: Question-Type Classification
    is_preference = "preference" in subject.lower() or "preferred" in subject.lower()

    # 1. Retrieve top targeted excerpts for this row (cached query embeddings in RAM)
    top_chunks_scored = retriever.retrieve(subject, top_k=MAX_CONTEXT_CHUNKS)
    top_chunk = top_chunks_scored[0][0] if top_chunks_scored else None
    top_score = top_chunks_scored[0][1] if top_chunks_scored else 0.0
    retrieved_context = retriever.get_formatted_context(subject, top_k=MAX_CONTEXT_CHUNKS)

    # 2. Build targeted prompt for all columns needed in this row
    cols_needed = [
        {"col_header": s["header"], "col_type": s["col_type"], "cell_ref": s["cell_ref"]}
        for s in slots
    ]

    val_map: dict[str, str] = {}
    top_text = top_chunk.text if top_chunk else ""

    # Option 4: Canonical Structured Fact Lookup (Direct Table Specification Matching)
    canonical_fact, fact_conf = retriever.lookup_canonical_fact(subject)
    used_canonical_fact = False
    if canonical_fact and fact_conf >= 0.90:
        for s in slots:
            ref = s["cell_ref"]
            col_type = s["col_type"]
            if col_type in ("answer", "proposed"):
                val_map[ref] = canonical_fact.value
            elif col_type in ("remarks", "source"):
                val_map[ref] = canonical_fact.source_section
        llm_state = STATE_COMPLIANT
        used_canonical_fact = True

    if active_model and not used_canonical_fact:
        prompt = f"""You are an expert technical evaluator extracting precise, concise answers from reference document excerpts.

RELEVANT REFERENCE EXCERPTS:
{retrieved_context}

REQUIREMENT / FIELD TO EXTRACT:
{subject}

COLUMNS TO POPULATE:
{json.dumps(cols_needed, indent=2)}

CRITICAL INSTRUCTIONS:
- For "answer"/"proposed": Extract the concise, accurate value or statement directly answering the question based ONLY on the provided reference excerpts. If the information is not mentioned in the excerpts, return "Not specified in report". Do not fabricate.
- For "remarks"/"source": Output the specific section heading and page number from the excerpt header where the answer was found (e.g. "<Section Heading> (Page <Page Number>)").
- For "compliance": Return one of:
  * "COMPLIANT" (if requirement is fully met)
  * "PARTIALLY_COMPLIANT" (if partially met or supported with limitations)
  * "NON_COMPLIANT" (if not met or contradicted)
  * "NOT_FOUND" (if information is absent from reference document)
- For "total_marks": output the maximum score/weight for this requirement.
- For "marks": output the marks obtained based on compliance.

Return valid JSON format:
{{
  "compliance_state": "COMPLIANT | PARTIALLY_COMPLIANT | NON_COMPLIANT | NOT_FOUND",
  "results": [
    {{
      "cell_ref": "<cell_ref>",
      "value": "<concise_short_value>"
    }}
  ]
}}
"""
        llm_res = call_ollama(prompt, is_json=True, model_override=active_model)
        if isinstance(llm_res, dict):
            llm_state = str(llm_res.get("compliance_state", "")).upper()
            if "results" in llm_res and isinstance(llm_res["results"], list):
                for item in llm_res["results"]:
                    if isinstance(item, dict) and "cell_ref" in item and "value" in item:
                        val_map[item["cell_ref"]] = str(item["value"])

    # Determine row compliance state to ground marks calculation (PRD 5-State model)
    row_compliance = STATE_COMPLIANT
    if llm_state in (STATE_COMPLIANT, STATE_PARTIALLY_COMPLIANT, STATE_NON_COMPLIANT, STATE_NOT_FOUND, STATE_AMBIGUOUS):
        row_compliance = llm_state
    for s in slots:
        if s["col_type"] == "compliance":
            ref = s["cell_ref"]
            if val_map.get(ref):
                c_upper = val_map[ref].upper()
                if any(w in c_upper for w in ["PARTIAL", "PC"]):
                    row_compliance = STATE_PARTIALLY_COMPLIANT
                elif any(w in c_upper for w in ["NON-COMPLIANT", "NC", "NOT MEET", "NO"]):
                    row_compliance = STATE_NON_COMPLIANT
                elif any(w in c_upper for w in ["NOT FOUND", "NOT SPECIFIED", "ABSENT"]):
                    row_compliance = STATE_NOT_FOUND
                elif any(w in c_upper for w in ["FC", "COMPLIANT", "FULLY COMPLIANT", "YES", "MEET"]):
                    row_compliance = STATE_COMPLIANT
            elif not top_chunk or top_score <= 0.1:
                row_compliance = STATE_NOT_FOUND

    # Map results or use extractive fallback (dynamic scoring without hardcoded 10/5/0)
    row_results = []
    for s in slots:
        ref = s["cell_ref"]
        col_type = s["col_type"]

        if col_type == "total_marks":
            gen_val = format_total_marks(max_marks, is_preference, s.get("existing_value"))
        elif col_type == "marks":
            gen_val = calculate_dynamic_marks(row_compliance, max_marks, default_weight=s.get("sheet_default_marks", 10.0))
        elif col_type == "compliance":
            gen_val = format_compliance_label(row_compliance, style)
        elif col_type in ("answer", "proposed"):
            if ref in val_map and val_map[ref].strip() and len(val_map[ref].strip().split()) <= 45:
                gen_val = val_map[ref].strip()
            else:
                pinpoint = _pinpoint_value(s.get("context", ""), top_text)
                if pinpoint and pinpoint != "Not Found in Reference Document":
                    gen_val = pinpoint
                else:
                    gen_val = extractive_fallback(s, top_chunk, is_preference, row_compliance)
        elif col_type in ("remarks", "source"):
            if ref in val_map and val_map[ref].strip() and "Page" in val_map[ref] and len(val_map[ref].strip().split()) <= 8:
                gen_val = val_map[ref].strip()
            else:
                gen_val = _find_nearest_section(top_chunk, s.get("context", ""))
        else:
            if ref in val_map and val_map[ref].strip() and len(val_map[ref].strip().split()) <= 10:
                gen_val = val_map[ref].strip()
            else:
                gen_val = ""

        # Phase 4: Safe Unit Conversion Hook (Only when target unit is explicitly requested)
        if col_type in ("answer", "proposed") and gen_val and ureg:
            target_unit_match = re.search(r"\b(?:in|to)\s+(mbps|gbps|tbps|kbps|watts|watt|w|kw|gb|tb|mb|kg|lbs)\b", s.get("context", "").lower())
            if target_unit_match:
                t_unit = target_unit_match.group(1).lower()
                if t_unit in ("watts", "watt"):
                    t_unit = "W"
                conv = convert_units(gen_val, t_unit)
                if conv:
                    gen_val = conv

        # Phase 5: Independent Grounding Verification
        grounding_score = verify_grounding_independently(gen_val, top_text)
        is_negative = gen_val in ("Not Found in Reference Document", "Not specified in report") or not top_chunk
        is_long = len(gen_val.split()) > 15

        # Phase 6: Multi-Signal Calibrated Confidence
        if used_canonical_fact:
            calibrated_conf = 0.98
        else:
            calibrated_conf = calculate_calibrated_confidence(top_score, grounding_score, is_negative, is_long)

        s["confidence"] = calibrated_conf
        s["generated_value"] = gen_val
        row_results.append(s)

    return row_results


def fill_slots_with_retrieval(excel_data: dict, retriever: HybridRetriever, model_override: str | None = None) -> list:
    """Evaluate and fill all empty slots using parallel Hybrid retrieval and local LLM."""
    print(f"\n{'='*60}")
    print("  STEP 3: TARGETED HYBRID RETRIEVAL & CONCURRENT LLM FILL")
    print(f"{'='*60}")

    all_slots = excel_data["all_slots"]
    total_slots = len(all_slots)
    print(f"  Total slots to fill: {total_slots}")

    active_model = model_override or get_available_ollama_model()
    if active_model:
        print(f"  Active Local LLM: '{active_model}'")
    else:
        print("  Note: Ollama model downloading/offline. Using high-precision BM25 extraction engine.")

    # Group slots by (sheet, row) so all columns for a single question/item are resolved together
    rows_grouped: dict[tuple[str, int], list[dict]] = {}
    for slot in all_slots:
        key = (slot["sheet"], slot["row"])
        rows_grouped.setdefault(key, []).append(slot)

    total_rows = len(rows_grouped)
    # Thermal & Stability Protection: 4 workers prevents CPU overheating and Windows VRAM spikes
    workers = min(4, max(1, total_rows))
    print(f"  Distinct items/rows: {total_rows} (Running across {workers} thermal-safe parallel workers)", flush=True)

    items_to_process = [
        (i + 1, key[0], key[1], slots)
        for i, (key, slots) in enumerate(rows_grouped.items())
    ]

    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_item = {
            executor.submit(_eval_single_row, item, retriever, active_model): item
            for item in items_to_process
        }
        completed_count = 0
        for future in as_completed(future_to_item):
            completed_count += 1
            item = future_to_item[future]
            _, sheet_name, row_num, _ = item
            try:
                row_res = future.result()
                results.extend(row_res)
                summary_preview = " | ".join(f"{s['cell_ref']}: {s.get('generated_value', '')[:25]}" for s in row_res[:2])
                print(f"  [{completed_count}/{total_rows}] Sheet: '{sheet_name}' | Row {row_num} -> {summary_preview}", flush=True)
            except Exception as e:
                print(f"  [{completed_count}/{total_rows}] Error on Sheet: '{sheet_name}' Row {row_num}: {e}", flush=True)

    return results


# ══════════════════════════════════════════════════════════
# STEP 4: EXCEL OUTPUT GENERATION
# ══════════════════════════════════════════════════════════
def write_excel(excel_path: Path, output_path: Path, filled_slots: list, confidence_threshold: float = 0.65) -> None:
    """Write generated values into original template workbook, preserving styles, formulas, and highlighting review & missing cells."""
    print(f"\n{'='*60}")
    print("  STEP 4: SAVING OUTPUT EXCEL WORKBOOK")
    print(f"{'='*60}")

    wb = openpyxl.load_workbook(str(excel_path), data_only=False)
    # Tier 1: Soft Light Yellow for AI reasoning/calculations needing quick review (Confidence ~0.51 - 0.64)
    soft_yellow_fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
    # Tier 2: Strong / Full Golden Yellow for Missing RFP requirements not in PDF (Confidence <= 0.50)
    full_yellow_fill = PatternFill(start_color="FFD966", end_color="FFD966", fill_type="solid")

    review_count = 0
    missing_count = 0

    for slot in filled_slots:
        sheet_name = slot["sheet"]
        if sheet_name not in wb.sheetnames:
            continue
        ws = wb[sheet_name]
        cell_ref = slot["cell_ref"]
        cell = ws[cell_ref]
        val_to_set = _sanitize_cell_val(slot.get("generated_value", ""))
        conf = float(slot.get("confidence", 1.0))

        target_cell = cell
        if isinstance(cell, MergedCell):
            # Target top-left of the merged range
            for rng in ws.merged_cells.ranges:
                if cell.coordinate in rng:
                    target_cell = ws.cell(row=rng.min_row, column=rng.min_col)
                    break

        target_cell.value = val_to_set
        val_str = str(val_to_set).lower()

        # 2-Tier Color Highlighting
        if conf <= 0.50 or "not specified" in val_str or "not found" in val_str:
            target_cell.fill = full_yellow_fill
            missing_count += 1
        elif conf < confidence_threshold:
            target_cell.fill = soft_yellow_fill
            review_count += 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(output_path))
    wb.close()

    print(f"  Successfully populated {len(filled_slots)} cells")
    if missing_count > 0:
        print(f"  [FULL YELLOW] Highlighted {missing_count} missing requirement cells (Not found in PDF) for vendor follow-up")
    if review_count > 0:
        print(f"  [SOFT YELLOW] Highlighted {review_count} complex/calculated cells (< {confidence_threshold}) for quick human review")
    print(f"  Output saved to: {output_path}")


# ══════════════════════════════════════════════════════════
# MAIN ORCHESTRATION
# ══════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(description="Adaptive Local AI RFP PDF-to-Excel Pipeline")
    parser.add_argument("--model", "-m", default=OLLAMA_MODEL, help="Local Ollama model name (default: qwen2.5:1.5b)")
    parser.add_argument("--pdf", "-p", type=Path, default=None, help="Path to reference PDF file")
    parser.add_argument("--excel", "-e", type=Path, default=None, help="Path to Excel template file")
    parser.add_argument("--input-dir", "-d", type=Path, default=DEFAULT_INPUT_DIR, help="Directory to scan for PDF/Excel pairs (default: testworkflowfile)")
    parser.add_argument("--confidence-threshold", "-c", type=float, default=0.65, help="Confidence threshold for soft-yellow cell highlighting (default: 0.65)")

    args, unknown = parser.parse_known_args()

    # Support legacy positional arguments: python test_pipeline.py <pdf> <excel>
    if len(unknown) == 2 and not args.pdf and not args.excel:
        pairs = [(Path(unknown[0]), Path(unknown[1]))]
    elif args.pdf and args.excel:
        pairs = [(args.pdf, args.excel)]
    else:
        input_dir = args.input_dir
        pdf_files = [p for p in sorted(input_dir.glob("*.pdf")) if not p.name.startswith("temp")]
        xlsx_files = [
            f for f in sorted(input_dir.glob("*.xlsx"))
            if "output" not in f.name.lower() and not f.name.startswith("temp") and not f.name.startswith("~")
        ]

        pairs = []
        for pdf in pdf_files:
            matches = [x for x in xlsx_files if x.stem.split("_")[0] in pdf.stem or pdf.stem.split("_")[0] in x.stem]
            if matches:
                for xlsx in matches:
                    pairs.append((pdf, xlsx))
            else:
                for xlsx in xlsx_files:
                    pairs.append((pdf, xlsx))

    if not pairs:
        print(f"No PDF and Excel file pairs found in {args.input_dir}/.")
        sys.exit(1)

    print("=" * 60)
    print("  OPTIMIZED LOCAL AI RFP PDF-TO-EXCEL PIPELINE")
    print("  Zero-Crash Ingestion | BM25 Retrieval | Format-Agnostic")
    print("=" * 60)

    for pdf_path, xlsx_path in pairs:
        print(f"\n{'#'*60}")
        print(f"  INPUT PDF:   {pdf_path}")
        print(f"  INPUT EXCEL: {xlsx_path}")
        print(f"  MODEL:       {args.model}")
        print(f"{'#'*60}")

        start_time = time.time()

        # Step 1: PDF Extraction & BM25 Indexing
        _, retriever = extract_and_index_pdf(pdf_path)

        # Step 2: Excel Analysis
        excel_data = analyze_excel(xlsx_path)

        if not excel_data["all_slots"]:
            print("  No empty slots to fill in this workbook.")
            continue

        # Step 3: Targeted Retrieval & LLM Fill
        filled_slots = fill_slots_with_retrieval(excel_data, retriever, model_override=args.model)

        # Step 4: Write Output
        output_name = f"{xlsx_path.stem}_output.xlsx"
        output_path = xlsx_path.parent / output_name
        write_excel(xlsx_path, output_path, filled_slots, confidence_threshold=args.confidence_threshold)

        elapsed = time.time() - start_time
        print(f"\n  [SUCCESS] Completed in {elapsed:.2f}s")
        print(f"  Generated File: {output_path}")


if __name__ == "__main__":
    main()
