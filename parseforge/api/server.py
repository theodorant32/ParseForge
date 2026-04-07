from __future__ import annotations

import asyncio
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from parseforge.persistence.store import RequestStore
from parseforge.pipeline.orchestrator import run
from parseforge.utils.logger import get_logger

logger = get_logger(__name__)

app = FastAPI(
    title="ParseForge API",
    description="End-to-end pipeline: unstructured text → structured decision.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

store = RequestStore()


class RunRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Raw user input text.")
    skip_enrichment: bool = Field(False, description="Skip the enrichment stage.")
    trace_id: str | None = Field(None, description="Optional custom trace ID.")


class BatchRunRequest(BaseModel):
    inputs: list[str] = Field(..., min_items=1, max_items=50)
    skip_enrichment: bool = False


@app.get("/health", tags=["Meta"])
async def health() -> dict[str, str]:
    return {"status": "ok", "version": "1.0.0"}


@app.post("/pipeline/run", tags=["Pipeline"])
async def pipeline_run(body: RunRequest) -> dict[str, Any]:
    logger.info("api_run_request", input_length=len(body.text))
    result = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: run(body.text, skip_enrichment=body.skip_enrichment, trace_id=body.trace_id),
    )
    store.save(result)
    return result.model_dump()


@app.post("/pipeline/batch", tags=["Pipeline"])
async def pipeline_batch(body: BatchRunRequest) -> dict[str, Any]:
    logger.info("api_batch_request", count=len(body.inputs))

    loop = asyncio.get_event_loop()
    tasks = [
        loop.run_in_executor(None, lambda t=text: run(t, skip_enrichment=body.skip_enrichment))
        for text in body.inputs
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    processed = []
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            processed.append({"error": str(r), "input_index": i})
        else:
            store.save(r)
            processed.append(r.model_dump())

    success_count = sum(1 for r in processed if isinstance(r, dict) and r.get("success"))
    return {
        "total": len(body.inputs),
        "success": success_count,
        "failed": len(body.inputs) - success_count,
        "results": processed,
    }


@app.get("/pipeline/history", tags=["Pipeline"])
async def pipeline_history(limit: int = Query(20, ge=1, le=200)) -> dict[str, Any]:
    all_results = store.load_decisions()
    recent = all_results[-limit:][::-1]
    return {"count": len(recent), "results": recent}
