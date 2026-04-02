"""
parseforge/layers/enricher.py

Enrichment Layer — enhances a validated ParsedRequest with:
  1. Inferred urgency from timeframe / keywords
  2. Inferred team_size from topic language
  3. Normalized timeframe aliases  ("ASAP" → consistent label)
  4. Metadata: request_id (UUID), timestamp (ISO 8601), pipeline_version

Errors here are NON-FATAL — logged as warnings, raw data passes through.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from parseforge.layers.schema import ParsedRequest, UrgencyEnum
from parseforge.utils.errors import EnrichmentError
from parseforge.utils.logger import get_logger, set_stage

logger = get_logger(__name__)

PIPELINE_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Timeframe → urgency mapping
# ---------------------------------------------------------------------------
HIGH_URGENCY_TIMEFRAMES = {"asap", "today", "tonight", "right now", "immediately"}
MEDIUM_URGENCY_TIMEFRAMES = {"tomorrow", "this weekend", "this week", "next week", "in 1 days", "in 2 days", "in 3 days"}
LOW_URGENCY_TIMEFRAMES = {"next month", "this month", "eventually", "flexible"}

# ---------------------------------------------------------------------------
# Topic keywords that imply team_size
# ---------------------------------------------------------------------------
SOLO_KEYWORDS = {"solo", "alone", "myself", "just me", "on my own", "by myself"}
PARTNER_KEYWORDS = {"partner", "co-founder", "pair", "duo", "buddy"}


def process(request: ParsedRequest) -> ParsedRequest:
    """
    Enrich a validated ParsedRequest.

    Returns:
        Enriched ParsedRequest (never raises — falls back to input on error).
    """
    set_stage("enricher")
    logger.info("enrichment_start", topic=request.topic, urgency=request.urgency)

    data = request.model_dump()
    enrichments_applied: list[str] = []

    try:
        # 1. Add metadata
        data["request_id"] = str(uuid.uuid4())
        data["timestamp"] = datetime.now(tz=timezone.utc).isoformat()
        data["pipeline_version"] = PIPELINE_VERSION
        enrichments_applied.append("metadata")

        # 2. Infer / upgrade urgency from timeframe
        new_urgency = _infer_urgency(data["timeframe"], data["raw_input"], existing_urgency=data["urgency"])
        if new_urgency != data["urgency"]:
            logger.info(
                "urgency_inferred",
                old=data["urgency"],
                new=new_urgency,
                trigger="timeframe",
            )
            data["urgency"] = new_urgency
            enrichments_applied.append("urgency_inferred")

        # 3. Infer team_size from raw input if still at default (1)
        inferred_size = _infer_team_size(data["raw_input"])
        if inferred_size is not None and data["team_size"] == 1:
            logger.info(
                "team_size_inferred",
                old=data["team_size"],
                new=inferred_size,
            )
            data["team_size"] = inferred_size
            enrichments_applied.append("team_size_inferred")

        # 4. Normalize timeframe labels
        data["timeframe"] = _normalize_timeframe(data["timeframe"])
        enrichments_applied.append("timeframe_normalized")

    except Exception as exc:
        # Non-fatal — log and continue with whatever we have
        logger.warning(
            "enrichment_partial_failure",
            error=str(exc),
            applied=enrichments_applied,
        )

    logger.info(
        "enrichment_complete",
        enrichments=enrichments_applied,
        request_id=data.get("request_id", "—"),
        urgency=data["urgency"],
    )

    return ParsedRequest(**data)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _infer_urgency(timeframe: str, raw: str, existing_urgency: str = UrgencyEnum.medium) -> str:
    """Infer urgency from timeframe label and raw text. Falls back to existing_urgency."""
    tf_lower = timeframe.lower()
    raw_lower = raw.lower()

    # High urgency signals
    if tf_lower in HIGH_URGENCY_TIMEFRAMES:
        return UrgencyEnum.high
    if any(w in raw_lower for w in ["asap", "urgent", "right now", "immediately", "emergency"]):
        return UrgencyEnum.high

    # Low urgency signals
    if tf_lower in LOW_URGENCY_TIMEFRAMES:
        return UrgencyEnum.low
    if any(w in raw_lower for w in ["no rush", "whenever", "eventually", "flexible", "someday"]):
        return UrgencyEnum.low

    # Medium urgency
    if tf_lower in MEDIUM_URGENCY_TIMEFRAMES:
        return UrgencyEnum.medium

    # No signal — preserve whatever the parser already decided
    return existing_urgency


def _infer_team_size(raw: str) -> int | None:
    """Infer team_size from solo/partner keywords in raw text."""
    raw_lower = raw.lower()
    if any(w in raw_lower for w in SOLO_KEYWORDS):
        return 1
    if any(w in raw_lower for w in PARTNER_KEYWORDS):
        return 2
    return None


def _normalize_timeframe(timeframe: str) -> str:
    """Normalize common timeframe aliases to canonical labels."""
    aliases: dict[str, str] = {
        "asap": "ASAP",
        "right now": "ASAP",
        "immediately": "ASAP",
        "this weekend": "this weekend",
        "weekend": "this weekend",
        "tonight": "today (tonight)",
        "today": "today",
        "tomorrow": "tomorrow",
        "next week": "next week",
        "next month": "next month",
        "this month": "this month",
        "this week": "this week",
        "unspecified": "unspecified",
    }
    return aliases.get(timeframe.lower(), timeframe)
