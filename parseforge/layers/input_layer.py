"""
parseforge/layers/input_layer.py

Input Layer — first line of defense.
Validates and normalizes raw user text before it hits the parser.
"""

from __future__ import annotations

from parseforge.utils.errors import InputError
from parseforge.utils.logger import get_logger, set_stage

logger = get_logger(__name__)

MIN_LENGTH = 3
MAX_LENGTH = 2000


def process(raw: str | None) -> str:
    """
    Validate and normalize raw user input.

    Args:
        raw: The raw text string from the user (may be None or empty).

    Returns:
        A clean, stripped string ready for parsing.

    Raises:
        InputError: If input is missing, too short, or too long.
    """
    set_stage("input")

    # --- Existence check ---
    if raw is None:
        logger.error("input_rejected", reason="Input is None")
        raise InputError("Input cannot be None. Please provide a text string.")

    # --- Strip and sanitize ---
    cleaned = _sanitize(raw)

    # --- Length checks ---
    if len(cleaned) < MIN_LENGTH:
        logger.warning(
            "input_rejected",
            reason="too_short",
            length=len(cleaned),
            min_length=MIN_LENGTH,
        )
        raise InputError(
            f"Input is too short (got {len(cleaned)} chars, minimum {MIN_LENGTH}). "
            "Please provide more detail."
        )

    if len(cleaned) > MAX_LENGTH:
        logger.warning(
            "input_truncated",
            reason="too_long",
            length=len(cleaned),
            max_length=MAX_LENGTH,
        )
        raise InputError(
            f"Input is too long (got {len(cleaned)} chars, maximum {MAX_LENGTH}). "
            "Please shorten your request."
        )

    logger.info("input_accepted", length=len(cleaned))
    return cleaned


def _sanitize(text: str) -> str:
    """
    Strip whitespace and remove non-printable control characters
    (except newlines and tabs which may be intentional).
    """
    # Remove null bytes and other control chars
    cleaned = "".join(
        ch for ch in text if ch == "\n" or ch == "\t" or ch.isprintable()
    )
    return cleaned.strip()
