from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, Field


class StageResult(BaseModel):
    stage: str
    status: str
    input_summary: dict[str, Any] = Field(default_factory=dict)
    output_summary: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    duration_ms: float = 0.0

    model_config = {"arbitrary_types_allowed": True}


class Timer:
    def __init__(self):
        self._start: float = 0.0
        self.elapsed_ms: float = 0.0

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *_):
        self.elapsed_ms = (time.perf_counter() - self._start) * 1000
