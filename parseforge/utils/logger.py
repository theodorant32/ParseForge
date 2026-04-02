"""
parseforge/utils/logger.py

Structured JSON logger built on structlog.
Every log entry automatically includes:
  - trace_id   (set once per pipeline run, propagated everywhere)
  - stage      (set when a stage begins)
  - timestamp  (ISO 8601)
  - level

Usage:
    from parseforge.utils.logger import get_logger, set_trace_id, set_stage

    logger = get_logger(__name__)
    set_trace_id("abc123")
    set_stage("parser")
    logger.info("parsing_complete", extracted_fields=3)
"""

import logging
import sys
import uuid
from contextvars import ContextVar
from pathlib import Path

import structlog

# ---------------------------------------------------------------------------
# Context variables — these are thread/async-safe and auto-injected into logs
# ---------------------------------------------------------------------------
_trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")
_stage_var: ContextVar[str] = ContextVar("stage", default="")


def set_trace_id(trace_id: str | None = None) -> str:
    """Set (or generate) a trace ID for the current pipeline run."""
    tid = trace_id or uuid.uuid4().hex[:12]
    _trace_id_var.set(tid)
    return tid


def get_trace_id() -> str:
    return _trace_id_var.get()


def set_stage(stage: str) -> None:
    _stage_var.set(stage)


# ---------------------------------------------------------------------------
# Log file path
# ---------------------------------------------------------------------------
LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "pipeline.jsonl"


# ---------------------------------------------------------------------------
# Context injector processor
# ---------------------------------------------------------------------------
def _inject_context(logger, method_name, event_dict):  # noqa: ARG001
    event_dict.setdefault("trace_id", _trace_id_var.get() or "—")
    event_dict.setdefault("stage", _stage_var.get() or "—")
    return event_dict


# ---------------------------------------------------------------------------
# Configure structlog (called once at import time)
# ---------------------------------------------------------------------------
def _configure() -> None:
    shared_processors = [
        _inject_context,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.ExceptionRenderer(),
    ]

    structlog.configure(
        processors=shared_processors
        + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # --- Console handler (pretty in dev) ---
    console_formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.dev.ConsoleRenderer(colors=True),
        ],
        foreign_pre_chain=shared_processors,
    )
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)

    # --- File handler (JSONL) ---
    json_formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
        foreign_pre_chain=shared_processors,
    )
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(json_formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(console_handler)
    root.addHandler(file_handler)
    root.setLevel(logging.DEBUG)

    # Silence noisy third-party loggers
    for noisy in ("uvicorn.access", "uvicorn.error", "fastapi"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


_configure()


def get_logger(name: str = "parseforge") -> structlog.stdlib.BoundLogger:
    """Return a named structured logger."""
    return structlog.get_logger(name)
