class ParseForgeError(Exception):
    code: str = "PARSEFORGE_ERROR"

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict:
        return {"error_code": self.code, "message": self.message, "details": self.details}


class InputError(ParseForgeError):
    code = "INPUT_ERROR"


class ParseError(ParseForgeError):
    code = "PARSE_ERROR"


class SchemaError(ParseForgeError):
    code = "SCHEMA_ERROR"


class ValidationError(ParseForgeError):
    code = "VALIDATION_ERROR"


class EnrichmentError(ParseForgeError):
    code = "ENRICHMENT_ERROR"


class DecisionError(ParseForgeError):
    code = "DECISION_ERROR"


class PipelineError(ParseForgeError):
    code = "PIPELINE_ERROR"
