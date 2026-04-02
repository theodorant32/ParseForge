"""
parseforge/layers/decision_engine.py

Decision Engine — the core intelligence layer.

Scoring system (0-100 points):
  +30  known intent (not "unknown")
  +20  specific topic (not "general")
  +20  valid team_size (>= 1)
  +15  timeframe specified
  +10  high urgency bonus
  + 5  clean validation (no warnings)

Decision table:
  score >= 70  →  match   (route to user matching)
  score 50–69  →  queue   (place in pending queue)
  score 30–49  →  clarify (request more info)
  score  < 30  →  reject  (insufficient data)

Priority mapping:
  high urgency + score >= 70  →  critical
  high urgency                →  high
  medium urgency              →  medium
  low urgency                 →  low
"""

from __future__ import annotations

from parseforge.layers.schema import (
    ActionEnum,
    DecisionResult,
    ParsedRequest,
    PriorityEnum,
    ValidationResult,
)
from parseforge.utils.errors import DecisionError
from parseforge.utils.logger import get_logger, set_stage

logger = get_logger(__name__)


def process(
    request: ParsedRequest,
    validation: ValidationResult,
) -> DecisionResult:
    """
    Score a validated, enriched request and return a decision.

    Args:
        request:    Fully enriched ParsedRequest.
        validation: Result from the validation layer (for warning count).

    Returns:
        DecisionResult with action, priority, score, and reason.

    Raises:
        DecisionError: If scoring logic itself fails (should never happen in practice).
    """
    set_stage("decision_engine")
    logger.info("decision_start", intent=request.intent, topic=request.topic)

    try:
        score, breakdown = _score(request, validation)
        action = _decide_action(score)
        priority = _decide_priority(request, score)
        reason = _build_reason(action, score, breakdown, request)

        result = DecisionResult(
            action=action,
            priority=priority,
            score=score,
            reason=reason,
        )

        logger.info(
            "decision_complete",
            action=action,
            priority=priority,
            score=score,
            reason=reason,
        )
        return result

    except Exception as exc:
        logger.error("decision_engine_failed", error=str(exc))
        raise DecisionError(f"Decision engine encountered an unexpected error: {exc}") from exc


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _score(request: ParsedRequest, validation: ValidationResult) -> tuple[int, dict]:
    """Compute score and return it alongside a human-readable breakdown."""
    breakdown: dict[str, int] = {}

    # Intercept conversational chatter completely
    if request.intent == "chitchat":
        return 30, {"chitchat_detected": 30}

    # +30: known intent
    if request.intent != "unknown":
        breakdown["known_intent"] = 30

    # +20: specific topic
    if request.topic not in ("general", ""):
        breakdown["specific_topic"] = 20

    # +20: valid team size
    if request.team_size >= 1:
        breakdown["valid_team_size"] = 20

    # +15: timeframe specified
    if request.timeframe not in ("unspecified", ""):
        breakdown["timeframe_specified"] = 15

    # +10: high urgency bonus
    if request.urgency == "high":
        breakdown["high_urgency_bonus"] = 10

    # +5: clean validation
    if not validation.warnings:
        breakdown["clean_validation"] = 5

    total = sum(breakdown.values())
    return min(total, 100), breakdown


def _decide_action(score: int) -> str:
    if score >= 70:
        return ActionEnum.match
    if score >= 50:
        return ActionEnum.queue
    if score >= 30:
        return ActionEnum.clarify
    return ActionEnum.reject


def _decide_priority(request: ParsedRequest, score: int) -> str:
    urgency = request.urgency
    if urgency == "high" and score >= 70:
        return PriorityEnum.critical
    if urgency == "high":
        return PriorityEnum.high
    if urgency == "medium":
        return PriorityEnum.medium
    return PriorityEnum.low


def _build_reason(
    action: str,
    score: int,
    breakdown: dict,
    request: ParsedRequest,
) -> str:
    earned = ", ".join(f"{k}(+{v})" for k, v in breakdown.items())
    base = f"Score {score}/100 [{earned}]."

    if "chitchat_detected" in breakdown:
        return "Score 30/100 [chitchat_detected(+30)]. Hi there! I am ParseForge. What kind of project or gig do you need help with?"

    tips: dict[str, str] = {
        ActionEnum.match: f"Request is well-defined — routing to match engine for '{request.topic}'.",
        ActionEnum.queue: "Request has enough data to queue but not immediately actionable.",
        ActionEnum.clarify: (
            "Request lacks enough detail. "
            "Consider specifying: "
            + ", ".join(
                f for f, v in [
                    ("intent", request.intent == "unknown"),
                    ("topic", request.topic == "general"),
                    ("timeframe", request.timeframe == "unspecified"),
                    ("team_size", request.team_size == 0),
                ]
                if v
            )
            or "more context"
        ),
        ActionEnum.reject: (
            "Insufficient information to process this request. "
            "Please provide intent, topic, timeframe, and team size."
        ),
    }

    return f"{base} {tips.get(action, '')}"
