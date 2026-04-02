"""
parseforge/utils/errors.py

Custom exception hierarchy for ParseForge.
Every error carries a human-readable message and a machine-readable code
so the pipeline can decide whether to retry, skip, or reject a request.
"""


class ParseForgeError(Exception):
    """Base class for all ParseForge errors."""

    code: str = "PARSEFORGE_ERROR"

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict:
        return {
            "error_code": self.code,
            "message": self.message,
            "details": self.details,
        }


class InputError(ParseForgeError):
    """Raised when raw user input is missing, empty, or malformed."""

    code = "INPUT_ERROR"


class ParseError(ParseForgeError):
    """Raised when the parser cannot extract any meaningful fields."""

    code = "PARSE_ERROR"


class SchemaError(ParseForgeError):
    """Raised when data cannot be coerced to the required schema."""

    code = "SCHEMA_ERROR"


class ValidationError(ParseForgeError):
    """Raised when business-logic validation fails and cannot be auto-corrected."""

    code = "VALIDATION_ERROR"


class EnrichmentError(ParseForgeError):
    """Non-fatal: raised when enrichment fails; pipeline continues with raw data."""

    code = "ENRICHMENT_ERROR"


class DecisionError(ParseForgeError):
    """Raised when the decision engine cannot produce a valid action."""

    code = "DECISION_ERROR"


class PipelineError(ParseForgeError):
    """Raised by the orchestrator for top-level pipeline failures."""

    code = "PIPELINE_ERROR"
