"""
parseforge/persistence/store.py

Persistence Layer — saves PipelineResults to JSONL files.

Files:
  data/results.jsonl   — full PipelineResult per request
  data/decisions.jsonl — lightweight decision records only

Usage:
    from parseforge.persistence.store import RequestStore
    store = RequestStore()
    store.save(pipeline_result)
    all_results = store.load_all()
    decisions   = store.load_decisions()
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from parseforge.utils.logger import get_logger

logger = get_logger(__name__)

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


class RequestStore:
    def __init__(self, data_dir: Path | None = None):
        self.data_dir = data_dir or DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._results_file = self.data_dir / "results.jsonl"
        self._decisions_file = self.data_dir / "decisions.jsonl"

    # -----------------------------------------------------------------------
    # Write
    # -----------------------------------------------------------------------
    def save(self, pipeline_result: Any) -> None:
        """Persist a full PipelineResult (accepts dict or PipelineResult model)."""
        data = (
            pipeline_result.model_dump()
            if hasattr(pipeline_result, "model_dump")
            else dict(pipeline_result)
        )
        self._append(self._results_file, data)

        # Also write a lean decision record
        if data.get("decision"):
            decision_record = {
                "trace_id": data.get("trace_id"),
                "timestamp": (data.get("parsed_request") or {}).get("timestamp"),
                "raw_input": data.get("raw_input", "")[:120],
                "decision": data["decision"],
                "success": data.get("success"),
            }
            self._append(self._decisions_file, decision_record)

        logger.info(
            "result_persisted",
            trace_id=data.get("trace_id"),
            success=data.get("success"),
        )

    # -----------------------------------------------------------------------
    # Read
    # -----------------------------------------------------------------------
    def load_all(self) -> list[dict]:
        """Return all stored PipelineResults as a list of dicts."""
        return self._read(self._results_file)

    def load_decisions(self) -> list[dict]:
        """Return lightweight decision records only."""
        return self._read(self._decisions_file)

    def count(self) -> int:
        return len(self.load_all())

    # -----------------------------------------------------------------------
    # Internals
    # -----------------------------------------------------------------------
    @staticmethod
    def _append(path: Path, data: dict) -> None:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(data, default=str) + "\n")

    @staticmethod
    def _read(path: Path) -> list[dict]:
        if not path.exists():
            return []
        results = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        results.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return results
