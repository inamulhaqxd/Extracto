#!/usr/bin/env python3
"""
Step 3 Search: Simple Hybrid Retrieval (Exact Codes + Local AI Embeddings).
Combines keyword/code precision with semantic similarity via local Ollama.
Strict typing only — zero Any (Rule 4). 100% offline (Rule 10).
"""

from __future__ import annotations

import math
import os
import re

import httpx

try:
    from pipeline_lab.step3_indexer import DocumentChunk, tokenize
except ModuleNotFoundError:
    from step3_indexer import DocumentChunk, tokenize  # type: ignore[no-redef]

OLLAMA_BASE_URL: str = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
DEFAULT_EMBED_MODEL: str = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")

# In-memory vector cache for zero redundant embedding calls
EMBEDDING_CACHE: dict[str, list[float]] = {}

STOPWORDS: set[str] = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "can't", "cannot", "could",
    "did", "do", "does", "doing", "down", "during", "each", "few", "for", "from",
    "further", "had", "has", "have", "having", "he", "her", "here", "him", "his",
    "how", "i", "if", "in", "into", "is", "isn't", "it", "its", "itself", "me",
    "more", "most", "my", "myself", "no", "nor", "not", "of", "off", "on", "once",
    "only", "or", "other", "our", "ours", "out", "over", "own", "same", "she",
    "should", "so", "some", "such", "than", "that", "the", "their", "theirs", "them",
    "then", "there", "these", "they", "this", "those", "through", "to", "too",
    "under", "until", "up", "very", "was", "we", "were", "what", "when", "where",
    "which", "while", "who", "whom", "why", "with", "would", "you", "your",
    # Question filler verbs
    "state", "indicate", "specify", "give", "list", "describe", "compare", "calculate", "check", "confirm",
}


# Case-insensitive patterns (identifiers, IP addresses, BGP tags, units)
CI_PATTERNS: list[str] = [
    r"\b(?:as-?\d+)\b",                                                  # ASNs
    r"\b\d{1,3}(?:\.\d{1,3}){3}(?:/\d{1,2})?\b",                        # IPv4 with optional CIDR
    r"(?<![0-9a-zA-Z:])(?:[0-9a-fA-F]{1,4}:){1,7}:?(?:[0-9a-fA-F]{1,4}:){0,6}[0-9a-fA-F]{1,4}(?:/\d{1,3})?\b",
    r"\b\d{1,5}:\d{1,5}\b",                                              # BGP tags
    r"(?:\b\d+(?:,\d+)*(?:\.\d+)?\s*(?:gbps|mbps|kbps|gb|tb|pb|ms|us|ns|ghz|mhz|percent|vlan|w|kw|ru)\b|\b\d+(?:,\d+)*(?:\.\d+)?\s*%)",
    r"\b[A-Za-z0-9]+(?:-[A-Za-z0-9]+)+\b",                              # Hyphenated IDs (EDGE-1, RM-UPA-IN, local-preference)
]

# Case-sensitive patterns (Proper nouns and acronyms only — prevents lowercase English words from matching)
CS_PATTERNS: list[str] = [
    r"\b[A-Z][a-z0-9]+[A-Z][a-zA-Z0-9]*\b",                             # PascalCase (UpstreamA, CustomerZ)
    r"(?<![A-Za-z0-9-])[A-Z]{2,}(?![A-Za-z0-9-])",                       # Acronyms (DSCP, BGP, QOS, SLA)
]


def extract_technical_codes(text: str) -> list[str]:
    """Extract distinct technical identifiers (e.g. AS-7018, UpstreamA, 64500:100, IP addresses)."""
    phrases: list[str] = []
    for pat in CI_PATTERNS:
        for m in re.findall(pat, text, flags=re.IGNORECASE):
            clean_m = m.strip()
            if clean_m.lower() not in STOPWORDS and len(clean_m) >= 2:
                if clean_m.lower() not in [p.lower() for p in phrases]:
                    phrases.append(clean_m)
    for pat in CS_PATTERNS:
        for m in re.findall(pat, text):
            clean_m = m.strip()
            if clean_m.lower() not in STOPWORDS and len(clean_m) >= 2:
                if clean_m.lower() not in [p.lower() for p in phrases]:
                    phrases.append(clean_m)
    return phrases


def matches_code(code: str, content: str) -> bool:
    """Check if a technical code appears in content with proper word boundaries."""
    left_b = r"\b" if re.match(r"^\w", code) else r"(?<!\w)"
    right_b = r"\b" if re.search(r"\w$", code) else r"(?!\w)"
    pattern = left_b + re.escape(code) + right_b
    return bool(re.search(pattern, content, flags=re.IGNORECASE))


def batch_get_local_embeddings(
    texts: list[str],
    model_name: str = DEFAULT_EMBED_MODEL,
    batch_size: int = 40,
    timeout: float = 20.0,
) -> list[list[float] | None]:
    """Fetch text embeddings in batch from local Ollama /api/embed (100% offline)."""
    results: list[list[float] | None] = [None] * len(texts)
    to_fetch_indices: list[int] = []
    to_fetch_texts: list[str] = []

    for i, t in enumerate(texts):
        clean_t = t.strip()[:1500]
        if not clean_t:
            results[i] = None
        elif clean_t in EMBEDDING_CACHE:
            results[i] = EMBEDDING_CACHE[clean_t]
        else:
            to_fetch_indices.append(i)
            to_fetch_texts.append(clean_t)

    if not to_fetch_texts:
        return results

    try:
        with httpx.Client(timeout=timeout) as client:
            for b_start in range(0, len(to_fetch_texts), batch_size):
                b_texts = to_fetch_texts[b_start : b_start + batch_size]
                b_indices = to_fetch_indices[b_start : b_start + batch_size]
                res = client.post(
                    f"{OLLAMA_BASE_URL}/api/embed",
                    json={"model": model_name, "input": b_texts},
                )
                if res.status_code == 200:
                    data: dict[str, object] = res.json()
                    embs_raw = data.get("embeddings")
                    if isinstance(embs_raw, list):
                        for idx_in_batch, emb in enumerate(embs_raw):
                            if isinstance(emb, list) and emb and isinstance(emb[0], (int, float)):
                                float_vec = [float(x) for x in emb]
                                original_text = b_texts[idx_in_batch]
                                EMBEDDING_CACHE[original_text] = float_vec
                                results[b_indices[idx_in_batch]] = float_vec
    except Exception:
        pass

    return results


def get_local_embedding(text: str, model_name: str = DEFAULT_EMBED_MODEL) -> list[float] | None:
    """Fetch single text embedding from cache or Ollama."""
    res = batch_get_local_embeddings([text], model_name=model_name)
    return res[0] if res else None


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    """Calculate cosine similarity between two numeric vectors."""
    if len(v1) != len(v2) or not v1:
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2, strict=True))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    val = dot / (norm1 * norm2)
    return round(max(0.0, min(1.0, val)), 6)


def simple_hybrid_search(
    query: str,
    chunks: list[DocumentChunk],
    top_k: int = 3,
    use_embeddings: bool = True,
) -> tuple[list[tuple[DocumentChunk, float, list[str]]], list[str]]:
    """
    Simple Hybrid Search:
    - Exact technical codes (IPs, ASNs, BGP tags, models)
    - Keyword token overlap (filtered against stopwords)
    - Semantic similarity via local Ollama embeddings
    """
    query_tokens = [t for t in tokenize(query) if t not in STOPWORDS]
    query_codes = extract_technical_codes(query)
    all_exact_hits: set[str] = set()

    if not query_tokens and not query_codes:
        return [], []

    query_embedding: list[float] | None = None
    if use_embeddings:
        query_embedding = get_local_embedding(query)

    scored_candidates: list[tuple[float, DocumentChunk, list[str]]] = []
    for chunk in chunks:
        # 1. Exact technical code matches (using word boundaries to eliminate false substring hits)
        chunk_hits = [c for c in query_codes if matches_code(c, chunk["content"])]
        for h in chunk_hits:
            all_exact_hits.add(h)

        # 2. Token overlap score
        token_overlap = sum(1 for t in query_tokens if t in chunk["tokens"])

        # Keyword component: weighted exact codes + general query token overlap
        keyword_score = (len(chunk_hits) * 3.0) + (token_overlap * 1.0)

        # 3. Semantic similarity via local embeddings
        semantic_score = 0.0
        if query_embedding is not None:
            chunk_emb = get_local_embedding(chunk["content"])
            if chunk_emb is not None:
                semantic_score = cosine_similarity(query_embedding, chunk_emb)

        # Combined hybrid score (0 to 1.0 normalized range)
        if query_embedding is not None and keyword_score > 0:
            hybrid_score = (0.5 * min(1.0, keyword_score / max(1.0, len(query_tokens)))) + (0.5 * semantic_score)
        elif query_embedding is not None:
            # Pure semantic match without keywords - requires high similarity to satisfy Rule 7 Zero-Hallucination
            if semantic_score >= 0.70:
                hybrid_score = semantic_score * 0.7
            else:
                hybrid_score = 0.0
        else:
            hybrid_score = min(1.0, keyword_score / max(1.0, len(query_tokens)))

        # Anti-hallucination threshold (Rule 7 Zero-Hallucination):
        # Must have at least one exact technical code, strong token overlap, or high-confidence semantic similarity.
        has_anchor = len(chunk_hits) > 0 or token_overlap > 0
        if (has_anchor and (len(chunk_hits) > 0 or hybrid_score >= 0.20 or keyword_score >= 2.0)) or hybrid_score >= 0.49:
            scored_candidates.append((hybrid_score, chunk, chunk_hits))

    # Sort descending by hybrid score
    scored_candidates.sort(key=lambda x: x[0], reverse=True)

    # Pick top_k non-redundant chunks
    selected: list[tuple[DocumentChunk, float, list[str]]] = []
    seen_pages: set[int] = set()

    for score, chunk, hits in scored_candidates:
        # Avoid duplicate chunks from the same page if we have alternative pages
        if chunk["page_number"] in seen_pages and len(selected) < top_k and len(scored_candidates) > len(selected):
            # Check if text is redundant
            if any(chunk["content"] in s[0]["content"] or s[0]["content"] in chunk["content"] for s in selected):
                continue

        selected.append((chunk, score, hits))
        seen_pages.add(chunk["page_number"])
        if len(selected) >= top_k:
            break

    return selected, sorted(all_exact_hits)
