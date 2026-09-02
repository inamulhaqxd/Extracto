import math
import re
from collections import Counter
from typing import Any

from ai_rfp_excel.app.document.chunker import DocumentChunk

# Common stopwords to exclude from scoring
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
    """Tokenize text into alphanumeric words and technical spec tokens (e.g. '8x', 'h100', 'pcie5')."""
    if not text:
        return []
    tokens = re.findall(r"[a-zA-Z0-9_\-\./]+", text.lower())
    return [t.strip(".-_") for t in tokens if len(t.strip(".-_")) > 1 and t.strip(".-_") not in STOPWORDS]


class BM25Retriever:
    """Fast, in-memory BM25 retrieval engine with technical spec phrase boosting."""

    def __init__(
        self,
        chunks: list[DocumentChunk],
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        self.chunks = chunks
        self.k1 = k1
        self.b = b
        self.corpus_size = len(chunks)
        self.doc_tokens: list[list[str]] = []
        self.doc_freqs: list[Counter[str]] = []
        self.doc_lengths: list[int] = []
        self.avg_doc_len: float = 0.0
        self.idf: dict[str, float] = {}

        self._build_index()

    def _build_index(self) -> None:
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
            # Standard Lucene/BM25 IDF formula with smoothing
            self.idf[term] = math.log(1.0 + (self.corpus_size - freq + 0.5) / (freq + 0.5))

    def retrieve(self, query: str, top_k: int = 4) -> list[tuple[DocumentChunk, float]]:
        """Retrieve the top-K relevant chunks for a given query string."""
        if not self.chunks or not query.strip():
            return []

        query_tokens = tokenize(query)
        if not query_tokens:
            # Fallback to returning the first chunk
            return [(self.chunks[0], 0.0)] if self.chunks else []

        scores: list[float] = [0.0] * self.corpus_size
        query_lower = query.lower()

        # Extract technical keywords (numbers, model names, acronyms) for boosting
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

            # Exact substring / phrase bonus
            chunk_text_lower = self.chunks[i].text.lower()
            if len(query_lower) > 5 and query_lower in chunk_text_lower:
                score += 5.0

            # Technical model / spec match bonus
            for term in key_terms:
                if len(term) >= 3 and term in chunk_text_lower:
                    score += 0.5

            scores[i] = score

        # Sort by score descending
        ranked_indices = sorted(range(self.corpus_size), key=lambda idx: scores[idx], reverse=True)

        results: list[tuple[DocumentChunk, float]] = []
        for idx in ranked_indices[:top_k]:
            if scores[idx] > 0 or len(results) == 0:
                results.append((self.chunks[idx], round(scores[idx], 3)))

        return results

    def get_formatted_context(self, query: str, top_k: int = 4) -> str:
        """Retrieve and format top-K chunks as clean, structured context for prompts."""
        top_results = self.retrieve(query, top_k=top_k)
        if not top_results:
            return "No directly matching content found in the reference document."

        formatted_parts: list[str] = []
        for chunk, score in top_results:
            header = f"--- [Excerpt from Page {chunk.page_number}"
            if chunk.section:
                header += f" | Section: {chunk.section}"
            header += f" | Relevance Score: {score}] ---"
            formatted_parts.append(f"{header}\n{chunk.text.strip()}")

        return "\n\n".join(formatted_parts)
