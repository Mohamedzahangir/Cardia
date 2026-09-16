"""
CARDIA TF-IDF Retriever.

Lightweight deterministic retrieval using sklearn TfidfVectorizer
and cosine similarity over the curated CARDIA physiology chunks.

Replaces the previous SentenceTransformer + Qdrant implementation
to eliminate the heavy PyTorch/model memory footprint on Render's
512 MiB free tier.
"""

from pathlib import Path
from typing import Optional

import json
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


# ============================================================
# PATHS / CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

CHUNKS_PATH = BASE_DIR / "data" / "chunks" / "cardia_chunks.json"

DEFAULT_TOP_K = 5


# ============================================================
# LAZY INDEX
# ============================================================
# The TF-IDF index is built once on first use and cached.

_chunks: list[dict] = []
_vectorizer: TfidfVectorizer | None = None
_tfidf_matrix = None


def _build_search_text(chunk: dict) -> str:
    """
    Combine searchable fields from a chunk into a single
    document string for TF-IDF indexing.
    """

    parts = []

    title = chunk.get("title", "")
    if title:
        parts.append(str(title))

    text = chunk.get("text", "")
    if text:
        parts.append(str(text))

    topic = chunk.get("topic", "")
    if topic:
        parts.append(str(topic).replace("_", " "))

    organ = chunk.get("organ", "")
    if organ:
        parts.append(str(organ).replace("_", " "))

    mechanisms = chunk.get("mechanism", [])
    if mechanisms:
        parts.append(" ".join(str(m) for m in mechanisms).replace("_", " "))

    equations = chunk.get("equation", [])
    if equations:
        parts.append(" ".join(str(e) for e in equations))

    source_title = chunk.get("source_title", "")
    if source_title:
        parts.append(str(source_title))

    author = chunk.get("author", "")
    if author:
        parts.append(str(author))

    return " ".join(parts)


def _ensure_index():
    """
    Build the TF-IDF index on first call. Subsequent calls are no-ops.
    """

    global _chunks, _vectorizer, _tfidf_matrix

    if _vectorizer is not None:
        return

    with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
        _chunks = json.load(f)

    documents = [_build_search_text(c) for c in _chunks]

    _vectorizer = TfidfVectorizer(
        lowercase=True,
        stop_words="english",
        ngram_range=(1, 2),
        max_features=10000,
    )

    _tfidf_matrix = _vectorizer.fit_transform(documents)


# ============================================================
# RETRIEVAL FUNCTION
# ============================================================

def retrieve(
    question: str,
    top_k: int = DEFAULT_TOP_K,
    topic: Optional[str] = None,
    organ: Optional[str] = None,
):
    """
    Retrieve the most relevant physiological evidence.

    Uses TF-IDF cosine similarity over curated CARDIA chunks.

    Parameters
    ----------
    question:
        User's natural-language question.

    top_k:
        Number of evidence chunks to retrieve.

    topic:
        Optional metadata filter.

    organ:
        Optional metadata filter.

    Returns
    -------
    list[dict]
        Structured retrieved evidence including:

        - chunk identity
        - title and text
        - similarity score
        - source provenance
        - topic
        - organ
        - mechanism
        - equations
        - chapter
        - authority level
        - source type
        - author
        - page
    """

    if not question or not question.strip():
        raise ValueError(
            "Question cannot be empty."
        )

    if top_k < 1:
        raise ValueError(
            "top_k must be at least 1."
        )

    # --------------------------------------------------------
    # Ensure index is built
    # --------------------------------------------------------

    _ensure_index()

    # --------------------------------------------------------
    # Transform query into TF-IDF vector
    # --------------------------------------------------------

    query_vec = _vectorizer.transform([question])

    # --------------------------------------------------------
    # Compute cosine similarity against all chunks
    # --------------------------------------------------------

    similarities = cosine_similarity(
        query_vec, _tfidf_matrix
    ).flatten()

    # --------------------------------------------------------
    # Apply metadata filters
    # --------------------------------------------------------

    filtered_indices = list(range(len(_chunks)))

    if topic is not None:
        filtered_indices = [
            i for i in filtered_indices
            if _chunks[i].get("topic") == topic
        ]

    if organ is not None:
        filtered_indices = [
            i for i in filtered_indices
            if _chunks[i].get("organ") == organ
        ]

    # --------------------------------------------------------
    # Sort filtered chunks by similarity descending
    # --------------------------------------------------------

    scored = [
        (i, similarities[i])
        for i in filtered_indices
    ]

    scored.sort(key=lambda x: x[1], reverse=True)

    top_results = scored[:top_k]

    # --------------------------------------------------------
    # Convert results into clean Python dictionaries
    # --------------------------------------------------------

    evidence = []

    for idx, score in top_results:
        chunk = _chunks[idx]

        evidence.append(
            {
                "chunk_id": chunk.get("chunk_id"),
                "title": chunk.get("title"),
                "text": chunk.get("text"),
                "score": float(round(score, 6)),
                "source": chunk.get("source"),
                "source_title": chunk.get("source_title"),
                "source_type": chunk.get("source_type"),
                "authority_level": chunk.get("authority_level"),
                "author": chunk.get("author"),
                "chapter": chunk.get("chapter"),
                "page": chunk.get("page"),
                "topic": chunk.get("topic"),
                "organ": chunk.get("organ"),
                "mechanism": chunk.get("mechanism", []),
                "equation": chunk.get("equation", []),
            }
        )

    return evidence
