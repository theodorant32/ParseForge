from __future__ import annotations

from parseforge.utils.errors import InputError
from parseforge.utils.logger import get_logger, set_stage

logger = get_logger(__name__)

MIN_LENGTH = 3
MAX_LENGTH = 2000


def process(raw: str | None) -> str:
    set_stage("input")

    if raw is None:
        logger.error("input_rejected", reason="Input is None")
        raise InputError("Input cannot be None. Please provide a text string.")

    cleaned = _sanitize(raw)

    if len(cleaned) < MIN_LENGTH:
        logger.warning("input_rejected", reason="too_short", length=len(cleaned), min_length=MIN_LENGTH)
        raise InputError(f"Input is too short (got {len(cleaned)} chars, minimum {MIN_LENGTH}). Please provide more detail.")

    if len(cleaned) > MAX_LENGTH:
        logger.warning("input_truncated", reason="too_long", length=len(cleaned), max_length=MAX_LENGTH)
        raise InputError(f"Input is too long (got {len(cleaned)} chars, maximum {MAX_LENGTH}). Please shorten your request.")

    logger.info("input_accepted", length=len(cleaned))
    return cleaned


def _sanitize(text: str) -> str:
    cleaned = "".join(ch for ch in text if ch == "\n" or ch == "\t" or ch.isprintable())
    return cleaned.strip()
