"""
parseforge/layers/schema.py

Pydantic v2 schema — the canonical data model that flows through every stage.
All fields have sensible defaults so partial parses are still usable.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class IntentEnum(str, Enum):
    task = "task"
    gig = "gig"
    help = "help"
    project = "project"
    scheduling = "scheduling"
    chitchat = "chitchat"
    unknown = "unknown"


class UrgencyEnum(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


# ---------------------------------------------------------------------------
# Core parsed-request schema
# ---------------------------------------------------------------------------
class ParsedRequest(BaseModel):
    """Structured representation of a user's raw text input."""

    # --- Core fields ---
    intent: IntentEnum = Field(
        default=IntentEnum.unknown,
        description="High-level intent of the request.",
    )
    team_size: int = Field(
        default=1,
        description="Number of people requested (0 means unspecified, <0 is invalid).",
    )
    topic: str = Field(
        default="general",
        description="Subject area of the request.",
    )
    timeframe: str = Field(
        default="unspecified",
        description="When the request is needed (natural language).",
    )
    urgency: UrgencyEnum = Field(
        default=UrgencyEnum.medium,
        description="Urgency level inferred from text or enrichment.",
    )

    # --- Source preservation ---
    raw_input: str = Field(
        default="",
        description="Original unmodified input text.",
    )

    # --- Parser metadata ---
    parse_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence score from the parser (0.0–1.0).",
    )
    parse_method: str = Field(
        default="rule_based",
        description="Which parser produced this result (rule_based | llm | fallback).",
    )

    # --- Enrichment metadata (added by enricher) ---
    request_id: str = Field(default="", description="UUID assigned by enricher.")
    timestamp: str = Field(default="", description="ISO 8601 timestamp of processing.")
    pipeline_version: str = Field(default="1.0.0", description="Pipeline version.")

    model_config = {"use_enum_values": True}

    # ---------------------------------------------------------------------------
    # Validators
    # ---------------------------------------------------------------------------
    @field_validator("topic", mode="before")
    @classmethod
    def normalize_topic(cls, v: Any) -> str:
        if not v or str(v).strip() == "":
            return "general"
        return str(v).strip().lower()

    @field_validator("timeframe", mode="before")
    @classmethod
    def normalize_timeframe(cls, v: Any) -> str:
        if not v or str(v).strip() == "":
            return "unspecified"
        # Preserve casing — enricher will normalize canonical labels
        return str(v).strip()

    @field_validator("team_size", mode="before")
    @classmethod
    def coerce_team_size(cls, v: Any) -> int:
        try:
            return int(v)  # allow negatives — validator will reject them
        except (TypeError, ValueError):
            return 0

    @model_validator(mode="after")
    def clamp_team_size(self) -> "ParsedRequest":
        if self.team_size > 100:
            self.team_size = 100
        return self

    def to_dict(self) -> dict:
        return self.model_dump()


# ---------------------------------------------------------------------------
# Validation result schema
# ---------------------------------------------------------------------------
class ValidationStatus(str, Enum):
    valid = "valid"
    invalid = "invalid"
    needs_clarification = "needs_clarification"
    auto_corrected = "auto_corrected"


class ValidationResult(BaseModel):
    status: ValidationStatus
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    corrections: list[str] = Field(default_factory=list)

    model_config = {"use_enum_values": True}


# ---------------------------------------------------------------------------
# Decision result schema
# ---------------------------------------------------------------------------
class ActionEnum(str, Enum):
    match = "match"
    queue = "queue"
    clarify = "clarify"
    reject = "reject"


class PriorityEnum(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class DecisionResult(BaseModel):
    action: ActionEnum
    priority: PriorityEnum
    score: int = Field(ge=0, le=100)
    reason: str = ""

    model_config = {"use_enum_values": True}
