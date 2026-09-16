from pathlib import Path
from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue
from sentence_transformers import SentenceTransformer


# ============================================================
# PATHS / CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

QDRANT_PATH = BASE_DIR / "data" / "qdrant"

COLLECTION_NAME = "cardia_physiology"

EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

DEFAULT_TOP_K = 5


# ============================================================
# LAZY EMBEDDING MODEL
# ============================================================

_embedding_model = None


def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        print("Loading CARDIA embedding model...")
        _embedding_model = SentenceTransformer(
            EMBEDDING_MODEL_NAME
        )
        print("Embedding model loaded.")
    return _embedding_model


# ============================================================
# LOAD QDRANT DATABASE
# ============================================================

print("Opening CARDIA Qdrant database...")

_qdrant_client = QdrantClient(
    path=str(QDRANT_PATH)
)

print("Qdrant database opened.")


# ============================================================
# BUILD OPTIONAL METADATA FILTER
# ============================================================

def _build_filter(
    topic: Optional[str] = None,
    organ: Optional[str] = None,
):
    """
    Build a Qdrant metadata filter.

    If no topic or organ is supplied, no filter is used.

    Parameters
    ----------
    topic:
        Optional CARDIA topic such as:
        cardiac_output
        cardiac_conduction
        cardiac_valves
        hemodynamics

    organ:
        Optional CARDIA organ/system such as:
        heart
        cardiac_conduction_system
        cardiovascular_system
    """

    conditions = []

    if topic:
        conditions.append(
            FieldCondition(
                key="topic",
                match=MatchValue(value=topic),
            )
        )

    if organ:
        conditions.append(
            FieldCondition(
                key="organ",
                match=MatchValue(value=organ),
            )
        )

    if not conditions:
        return None

    return Filter(
        must=conditions
    )


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
    # Create question embedding
    # --------------------------------------------------------

    model = get_embedding_model()

    question_embedding = model.encode(
        question,
        normalize_embeddings=True,
    ).tolist()

    # --------------------------------------------------------
    # Build optional metadata filter
    # --------------------------------------------------------

    query_filter = _build_filter(
        topic=topic,
        organ=organ,
    )

    # --------------------------------------------------------
    # Search Qdrant
    # --------------------------------------------------------

    search_results = _qdrant_client.query_points(
        collection_name=COLLECTION_NAME,
        query=question_embedding,
        query_filter=query_filter,
        limit=top_k,
        with_payload=True,
    ).points

    # --------------------------------------------------------
    # Convert results into clean Python dictionaries
    # --------------------------------------------------------

    evidence = []

    for result in search_results:

        payload = result.payload or {}

        evidence.append(
            {
                # ------------------------------------------------
                # Identity
                # ------------------------------------------------
                "chunk_id": payload.get(
                    "chunk_id"
                ),

                "title": payload.get(
                    "title"
                ),

                "text": payload.get(
                    "text"
                ),

                "score": float(
                    result.score
                ),

                # ------------------------------------------------
                # Source provenance
                # ------------------------------------------------
                "source": payload.get(
                    "source"
                ),

                "source_title": payload.get(
                    "source_title"
                ),

                "source_type": payload.get(
                    "source_type"
                ),

                "authority_level": payload.get(
                    "authority_level"
                ),

                "author": payload.get(
                    "author"
                ),

                "chapter": payload.get(
                    "chapter"
                ),

                "page": payload.get(
                    "page"
                ),

                # ------------------------------------------------
                # Physiological metadata
                # ------------------------------------------------
                "topic": payload.get(
                    "topic"
                ),

                "organ": payload.get(
                    "organ"
                ),

                "mechanism": payload.get(
                    "mechanism",
                    []
                ),

                "equation": payload.get(
                    "equation",
                    []
                ),
            }
        )

    return evidence