from __future__ import annotations

import re

from parseforge.layers.schema import (
    ParsedRequest,
    UrgencyEnum,
    ValidationResult,
    ValidationStatus,
)
from parseforge.utils.errors import ValidationError
from parseforge.utils.logger import get_logger, set_stage

logger = get_logger(__name__)

PAST_TIMEFRAME_PATTERNS = [
    re.compile(r"\byesterday\b", re.I),
    re.compile(r"\blast\s+(?:week|month|year)\b", re.I),
    re.compile(r"\bago\b", re.I),
    re.compile(r"\bprevious\b", re.I),
]


def process(request: ParsedRequest) -> tuple[ParsedRequest, ValidationResult]:
    set_stage("validator")
    logger.info("validation_start", intent=request.intent, team_size=request.team_size)

    errors: list[str] = []
    warnings: list[str] = []
    corrections: list[str] = []

    data = request.model_dump()

    if _is_past_timeframe(data["timeframe"]) or _is_past_timeframe(data["raw_input"]):
        msg = f"Timeframe '{data['timeframe']}' appears to be in the past. Please specify a future timeframe."
        errors.append(msg)
        result = ValidationResult(status=ValidationStatus.invalid, errors=errors)
        logger.warning("validation_failed", reason="past_timeframe", timeframe=data["timeframe"])
        raise ValidationError(msg)

    if data["team_size"] < 0:
        msg = f"team_size must be >= 0, got {data['team_size']}."
        errors.append(msg)
        result = ValidationResult(status=ValidationStatus.invalid, errors=errors)
        logger.warning("validation_failed", reason="negative_team_size")
        raise ValidationError(msg)

    if request.team_size == 100 and _original_team_size_was_over_100(request.raw_input):
        msg = "team_size was over 100 — clamped to 100."
        corrections.append(msg)
        warnings.append(msg)
        logger.warning("auto_correction", field="team_size", correction="clamped to 100")

    if data["intent"] == "unknown" and data["topic"] == "general":
        msg = "Could not determine the intent or topic. Please provide more detail about what you need."
        warnings.append(msg)
        result = ValidationResult(
            status=ValidationStatus.needs_clarification,
            warnings=warnings,
            corrections=corrections,
        )
        logger.info("validation_needs_clarification", reason="unknown_intent_and_topic")
        return ParsedRequest(**data), result

    if data["team_size"] == 0:
        msg = "team_size not specified — defaulting to 1."
        data["team_size"] = 1
        corrections.append(msg)
        warnings.append(msg)
        logger.info("auto_correction", field="team_size", correction="set to 1 (was unspecified)")

    if data["timeframe"] == "unspecified":
        warnings.append("No timeframe specified. Consider adding when you need this.")

    if errors:
        result = ValidationResult(
            status=ValidationStatus.invalid,
            errors=errors,
            warnings=warnings,
            corrections=corrections,
        )
        logger.warning("validation_failed", errors=errors)
        raise ValidationError(errors[0], details={"all_errors": errors})

    status = ValidationStatus.auto_corrected if corrections else ValidationStatus.valid
    result = ValidationResult(
        status=status,
        warnings=warnings,
        corrections=corrections,
    )
    logger.info("validation_complete", status=status, warnings_count=len(warnings), corrections_count=len(corrections))
    return ParsedRequest(**data), result


def _is_past_timeframe(text: str) -> bool:
    return any(p.search(text) for p in PAST_TIMEFRAME_PATTERNS)


def _original_team_size_was_over_100(raw: str) -> bool:
    match = re.search(r"\b(\d{3,})\b", raw)
    if match:
        try:
            return int(match.group(1)) > 100
        except ValueError:
            pass
    return False
