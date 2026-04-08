import time
import logging

import httpx
from fastapi import APIRouter, HTTPException
from opentelemetry import trace
from pydantic import BaseModel

from core.http_client import ranker_client
from core.metrics import REQUEST_COUNT, REQUEST_LATENCY, UPSTREAM_LATENCY, ERROR_COUNT

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/ranker", tags=["ranker"])
tracer = trace.get_tracer(__name__)

MODEL = "ranker"


class RankerRequest(BaseModel):
    texts: list[str]


class RankerResponse(BaseModel):
    scores: list[float]
    ranked_indices: list[int]
    upstream_latency_ms: float


@router.post("/rank", response_model=RankerResponse)
async def rank(req: RankerRequest):
    if not req.texts:
        ERROR_COUNT.labels(model=MODEL, error_type="validation_error").inc()
        raise HTTPException(status_code=422, detail="texts cannot be empty")

    t0 = time.perf_counter()

    with tracer.start_as_current_span("ranker.rank") as span:
        span.set_attribute("batch.size", len(req.texts))

        upstream_t0 = time.perf_counter()
        try:
            resp = await ranker_client.post(
                "/predict",
                json=req.model_dump(),
            )
            resp.raise_for_status()

        except httpx.TimeoutException:
            ERROR_COUNT.labels(model=MODEL, error_type="timeout").inc()
            REQUEST_COUNT.labels(model=MODEL, status_code="504").inc()
            span.set_attribute("error", True)
            raise HTTPException(status_code=504, detail="Ranker service timeout")

        except httpx.HTTPStatusError as e:
            ERROR_COUNT.labels(model=MODEL, error_type="upstream_error").inc()
            REQUEST_COUNT.labels(model=MODEL, status_code=str(e.response.status_code)).inc()
            span.set_attribute("error", True)
            raise HTTPException(
                status_code=502,
                detail=f"Upstream error: {e.response.status_code}",
            )

        upstream_latency = time.perf_counter() - upstream_t0
        UPSTREAM_LATENCY.labels(model=MODEL).observe(upstream_latency)

        data = resp.json()
        total_latency = time.perf_counter() - t0

        REQUEST_COUNT.labels(model=MODEL, status_code="200").inc()
        REQUEST_LATENCY.labels(model=MODEL).observe(total_latency)

        return RankerResponse(
            scores=data["scores"],
            ranked_indices=data["ranked_indices"],
            upstream_latency_ms=round(upstream_latency * 1000, 2),
        )