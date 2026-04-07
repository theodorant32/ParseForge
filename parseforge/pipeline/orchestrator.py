from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, Field

from parseforge.layers import (
    decision_engine,
    enricher,
    input_layer,
    parser,
    validator,
)
from parseforge.layers.schema import DecisionResult, ParsedRequest, ValidationResult
from parseforge.pipeline.stage import StageResult, Timer
from parseforge.utils.errors import (
    DecisionError,
    InputError,
    ParseError,
    ParseForgeError,
    ValidationError,
)
from parseforge.utils.logger import get_logger, set_stage, set_trace_id

logger = get_logger(__name__)

MAX_RETRIES = 2


class PipelineResult(BaseModel):
    trace_id: str
    raw_input: str
    success: bool
    stages: list[StageResult] = Field(default_factory=list)
    parsed_request: dict[str, Any] | None = None
    validation_result: dict[str, Any] | None = None
    decision: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    total_duration_ms: float = 0.0

    model_config = {"arbitrary_types_allowed": True}


class PipelineOrchestrator:
    def __init__(self, skip_enrichment: bool = False, trace_id: str | None = None):
        self.skip_enrichment = skip_enrichment
        self.trace_id = set_trace_id(trace_id)

    def run(self, raw_input: str) -> PipelineResult:
        wall_start = time.perf_counter()
        stages: list[StageResult] = []

        logger.info("pipeline_start", trace_id=self.trace_id, skip_enrichment=self.skip_enrichment)

        cleaned_input: str | None = None
        parsed: ParsedRequest | None = None
        validated: ParsedRequest | None = None
        validation_result: ValidationResult | None = None
        enriched: ParsedRequest | None = None
        decision: DecisionResult | None = None

        stage, cleaned_input = self._run_stage(
            name="input",
            fn=lambda: input_layer.process(raw_input),
            input_summary={"raw_length": len(raw_input) if raw_input else 0},
            output_key="cleaned_length",
        )
        stages.append(stage)
        if stage.status == "failed":
            return self._finalize(raw_input, stages, None, None, None, stage.errors[0], wall_start)

        stage, parsed = self._run_stage(
            name="parser",
            fn=lambda: parser.process(cleaned_input),
            input_summary={"input": cleaned_input[:80] + "..." if len(cleaned_input) > 80 else cleaned_input},
            output_key="intent",
        )
        stages.append(stage)
        if stage.status == "failed":
            return self._finalize(raw_input, stages, None, None, None, stage.errors[0], wall_start)

        def _validate():
            req, vres = validator.process(parsed)
            return (req, vres)

        stage, val_tuple = self._run_stage(
            name="validator",
            fn=_validate,
            input_summary={"intent": parsed.intent, "team_size": parsed.team_size},
            output_key="status",
            retry_on=(ValidationError,),
        )
        stages.append(stage)
        if stage.status == "failed":
            return self._finalize(raw_input, stages, parsed, None, None, stage.errors[0], wall_start)

        validated, validation_result = val_tuple

        if self.skip_enrichment:
            enriched = validated
            stages.append(StageResult(
                stage="enricher",
                status="skipped",
                input_summary={},
                output_summary={"reason": "skip_enrichment=True"},
            ))
            logger.info("enricher_skipped")
        else:
            stage, enriched = self._run_stage(
                name="enricher",
                fn=lambda: enricher.process(validated),
                input_summary={"timeframe": validated.timeframe, "urgency": validated.urgency},
                output_key="urgency",
                fatal=False,
            )
            stages.append(stage)
            if enriched is None:
                enriched = validated

        stage, decision = self._run_stage(
            name="decision_engine",
            fn=lambda: decision_engine.process(enriched, validation_result),
            input_summary={
                "intent": enriched.intent,
                "topic": enriched.topic,
                "urgency": enriched.urgency,
                "team_size": enriched.team_size,
            },
            output_key="action",
        )
        stages.append(stage)
        if stage.status == "failed":
            return self._finalize(
                raw_input, stages, enriched, validation_result, None,
                stage.errors[0], wall_start,
            )

        logger.info("pipeline_complete", action=decision.action, priority=decision.priority, score=decision.score)
        return self._finalize(raw_input, stages, enriched, validation_result, decision, None, wall_start)

    def _run_stage(
        self,
        name: str,
        fn,
        input_summary: dict,
        output_key: str = "",
        fatal: bool = True,
        retry_on: tuple = (),
    ) -> tuple[StageResult, Any]:
        set_stage(name)
        logger.debug(f"{name}_stage_enter", **input_summary)

        last_error: Exception | None = None
        attempts = 1 if retry_on else MAX_RETRIES

        for attempt in range(1, attempts + 2):
            with Timer() as t:
                try:
                    result = fn()
                    output_summary = {}
                    if output_key and result is not None:
                        val = result
                        if isinstance(result, tuple):
                            val = result[0]
                        try:
                            output_summary[output_key] = getattr(val, output_key, str(val)[:80])
                        except Exception:
                            pass

                    stage_result = StageResult(
                        stage=name,
                        status="success",
                        input_summary=input_summary,
                        output_summary=output_summary,
                        duration_ms=t.elapsed_ms,
                    )
                    logger.debug(f"{name}_stage_exit", status="success", duration_ms=round(t.elapsed_ms, 2))
                    return stage_result, result

                except (InputError, ParseError, ValidationError, DecisionError) as exc:
                    last_error = exc
                    break

                except Exception as exc:
                    last_error = exc
                    if attempt < attempts + 1:
                        logger.warning(f"{name}_retry", attempt=attempt, error=str(exc))
                    else:
                        break

        error_msg = str(last_error) if last_error else "Unknown error"
        err_dict = (
            last_error.to_dict()
            if isinstance(last_error, ParseForgeError)
            else {"error_code": "UNKNOWN", "message": error_msg}
        )
        status = "failed" if fatal else "warning"

        stage_result = StageResult(
            stage=name,
            status=status,
            input_summary=input_summary,
            errors=[error_msg],
            duration_ms=t.elapsed_ms if "t" in dir() else 0.0,
        )
        logger.error(f"{name}_stage_failed", error=error_msg, fatal=fatal)
        return stage_result, None

    def _finalize(
        self,
        raw_input: str,
        stages: list[StageResult],
        parsed: ParsedRequest | None,
        validation: ValidationResult | None,
        decision: DecisionResult | None,
        error_msg: str | None,
        wall_start: float,
    ) -> PipelineResult:
        total_ms = (time.perf_counter() - wall_start) * 1000
        return PipelineResult(
            trace_id=self.trace_id,
            raw_input=raw_input,
            success=error_msg is None and decision is not None,
            stages=stages,
            parsed_request=parsed.to_dict() if parsed else None,
            validation_result=validation.model_dump() if validation else None,
            decision=decision.model_dump() if decision else None,
            error={"message": error_msg} if error_msg else None,
            total_duration_ms=round(total_ms, 2),
        )


def run(raw_input: str, skip_enrichment: bool = False, trace_id: str | None = None) -> PipelineResult:
    return PipelineOrchestrator(skip_enrichment=skip_enrichment, trace_id=trace_id).run(raw_input)
