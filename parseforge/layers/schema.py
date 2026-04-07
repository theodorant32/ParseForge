from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


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


class ParsedRequest(BaseModel):
    intent: IntentEnum = Field(default=IntentEnum.unknown)
    team_size: int = Field(default=1)
    topic: str = Field(default="general")
    timeframe: str = Field(default="unspecified")
    urgency: UrgencyEnum = Field(default=UrgencyEnum.medium)
    raw_input: str = Field(default="")
    parse_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    parse_method: str = Field(default="rule_based")
    request_id: str = Field(default="")
    timestamp: str = Field(default="")
    pipeline_version: str = Field(default="1.0.0")

    model_config = {"use_enum_values": True}

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
        return str(v).strip()

    @field_validator("team_size", mode="before")
    @classmethod
    def coerce_team_size(cls, v: Any) -> int:
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0

    @model_validator(mode="after")
    def clamp_team_size(self) -> "ParsedRequest":
        if self.team_size > 100:
            self.team_size = 100
        return self

    def to_dict(self) -> dict:
        return self.model_dump()


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
