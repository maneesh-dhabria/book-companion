"""Custom exception hierarchy for Book Companion."""


class BookCompanionError(Exception):
    """Base exception for all Book Companion errors."""


class ConfigError(BookCompanionError):
    """Configuration-related errors."""


class ParseError(BookCompanionError):
    """Book parsing errors."""


class SummarizationError(BookCompanionError):
    """LLM summarization errors."""


class EvalError(BookCompanionError):
    """Evaluation assertion errors."""


class SearchError(BookCompanionError):
    """Search-related errors."""


class EmbeddingError(BookCompanionError):
    """Embedding generation errors."""


class StorageError(BookCompanionError):
    """Database/storage errors."""
