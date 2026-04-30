"""Custom exception hierarchy for Book Companion."""


class BookCompanionError(Exception):
    """Base exception for all Book Companion errors."""


class ConfigError(BookCompanionError):
    """Configuration-related errors."""


class ParseError(BookCompanionError):
    """Book parsing errors."""


class SummarizationError(BookCompanionError):
    """LLM summarization errors.

    Subclasses carry a ``failure_type`` discriminator that maps 1:1 to the
    ``book_sections.last_failure_type`` column and SSE ``section_failed``
    ``error_type`` payload field.
    """

    failure_type: str = "unknown"

    def __init__(
        self,
        message: str = "",
        stderr_truncated: str = "",
        stderr_full: str = "",
    ):
        self.stderr_truncated = stderr_truncated or ""
        self.stderr_full = stderr_full or ""
        super().__init__(message or self.__class__.__name__)


class SubprocessNonZeroExitError(SummarizationError):
    """CLI subprocess returned a non-zero exit code."""

    failure_type = "cli_nonzero_exit"

    def __init__(
        self, returncode: int, stderr_truncated: str = "", stderr_full: str = ""
    ):
        self.returncode = returncode
        super().__init__(
            f"CLI exited with code {returncode}: {stderr_truncated or '<no output>'}",
            stderr_truncated=stderr_truncated,
            stderr_full=stderr_full,
        )


class SubprocessTimeoutError(SummarizationError):
    """CLI subprocess exceeded its timeout."""

    failure_type = "cli_timeout"

    def __init__(self, timeout_seconds: int, stderr_truncated: str = ""):
        self.timeout_seconds = timeout_seconds
        super().__init__(
            f"CLI timed out after {timeout_seconds}s",
            stderr_truncated=stderr_truncated,
        )


class SubprocessNotFoundError(SummarizationError):
    """CLI binary is not available on PATH."""

    failure_type = "cli_not_found"

    def __init__(self, binary: str):
        self.binary = binary
        super().__init__(f"CLI binary not found on PATH: {binary!r}")


class SchemaParseError(SummarizationError):
    """CLI response did not match the requested JSON schema."""

    failure_type = "schema_parse_failed"


class EmptySummaryError(SummarizationError):
    """LLM returned an empty or whitespace-only summary."""

    failure_type = "empty_output"


class EvalError(BookCompanionError):
    """Evaluation assertion errors."""


class SearchError(BookCompanionError):
    """Search-related errors."""


class EmbeddingError(BookCompanionError):
    """Embedding generation errors."""


class StorageError(BookCompanionError):
    """Database/storage errors."""


class PresetError(BookCompanionError):
    """Preset-related errors (not found, validation, protected)."""


class SectionEditError(BookCompanionError):
    """Section editing errors (merge, split, reorder, delete)."""


class SummaryError(BookCompanionError):
    """Summary-related errors (not found, set-default)."""
