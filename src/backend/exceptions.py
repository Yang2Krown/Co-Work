"""Domain exceptions shared by backend modules."""


class BackendError(Exception):
    """Base class for expected backend errors."""


class ConfigurationError(BackendError):
    """Raised when backend configuration is missing or invalid."""


class DocumentLoadError(BackendError):
    """Raised when a document cannot be loaded."""


class UnsupportedFileTypeError(DocumentLoadError):
    """Raised when no loader supports a document's file type."""


class EmbeddingError(BackendError):
    """Raised when embedding generation fails."""


class VectorStoreError(BackendError):
    """Raised when a vector store operation fails."""


class RetrievalError(BackendError):
    """Raised when retrieval fails."""


class RerankerError(RetrievalError):
    """Raised when reranking fails."""


class LLMServiceError(BackendError):
    """Raised when an LLM service call fails."""
