"""Stable data contracts shared by backend layers."""

from .models import Citation, Chunk, Document, RAGResponse, RetrievalResult

__all__ = ["Citation", "Chunk", "Document", "RAGResponse", "RetrievalResult"]
