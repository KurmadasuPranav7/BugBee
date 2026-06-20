"""Retrieval layer for BugBee.

Wraps the existing ChromaDB vector store used to fetch relevant documentation
based on an error message.  The public function ``get_related_docs`` matches the
signature of the original ``retrieval.get_related_docs`` but is now a method of
the ``Retriever`` class for easier testing/mocking.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

from ..lazy import lazy_import

# Lazy imports for heavy dependencies
Chroma = lazy_import('langchain_chroma').Chroma
Document = lazy_import('langchain_core.documents').Document
HuggingFaceEmbeddings = lazy_import('langchain_huggingface').HuggingFaceEmbeddings

from bugbee.config.settings import settings

__all__ = ["Retriever", "get_related_docs"]


# Lazy singleton for Retriever to avoid repeated heavy initialisation.
_retriever: Retriever | None = None


def get_retriever() -> "Retriever":
    """Return a cached ``Retriever`` instance, creating it on first call.

    This function is used by ``get_related_docs`` and any external callers to
    ensure that the heavy ``Chroma`` connection and embedding model are only
   instantiated once per process.
    """
    global _retriever
    if _retriever is None:
        _retriever = Retriever()
    return _retriever


class Retriever:
    """ChromaDB retriever configured from the global settings.

    ``settings.chromadb_path`` determines where the persistent collection lives.
    ``settings.retrieval_k`` defines how many results to return.
    """

    def __init__(self) -> None:
        self.vector_store = Chroma(
            persist_directory=str(settings.chromadb_path),
            embedding_function=HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2"
            ),
            collection_name="framework_docs",
        )
        self.k = settings.retrieval_k

    def get_related_docs(self, query: str) -> Tuple[str, float, float]:
        """Return formatted docs, top score and average score for *query*.

        The return type mirrors the original implementation: ``(docs, top_score,
        avg_score)`` where *docs* is a formatted string of source and content.
        """
        results = self.vector_store.similarity_search_with_score(query, k=self.k)
        if not results:
            return "No Relevant documentation found", 0.0, 0.0

        docs: List[Document] = [doc for doc, _ in results]
        scores = [score for _, score in results]
        # Convert Chroma's distance (0..2) to a cosine‑like similarity.
        cosine_scores = [1.0 - (s / 2.0) for s in scores]
        top_score = cosine_scores[0]
        avg_score = sum(cosine_scores) / len(cosine_scores)

        formatted = ""
        for doc in docs:
            source = doc.metadata.get("source_file", "Unknown File")
            formatted += f"--- Source: {source} ---\n{doc.page_content}\n\n"
        return formatted, top_score, avg_score


# Convenience function used throughout the code base.
def get_related_docs(query: str) -> Tuple[str, float, float]:
    """Convenience wrapper that uses a lazy singleton ``Retriever``.

    This preserves the original public API while avoiding a new ``Retriever``
    instance on every call.
    """
    return get_retriever().get_related_docs(query)
