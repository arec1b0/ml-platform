import time
import logging

import httpx
from fastapi import APIRouter, HTTPException
from opentelemetry import trace
from pydantic import BaseModel

from core.http_client import toxicity_client
from core.metrics import REQUEST_COUNT, REQUEST_LATENCY, UPSTREAM_LATENCY, ERROR_COUNT

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/toxicity", tags=["toxicity"])
tracer = trace.get_tracer(__name__)

MODEL = "toxicity"


class ToxicityRequest(BaseModel):
    text: str
    threshold: float = 0.5


class ToxicityResponse(BaseModel):
    label: str
    score: float
    is_toxic: bool
    upstream_latency_ms: float


@router.post("/predict", response_model=ToxicityResponse)
async def predict(req: ToxicityRequest):
    t0 = time.perf_counter()

    with tracer.start_as_current_span("toxicity.predict") as span:
        span.set_attribute("text.length", len(req.text))
        span.set_attribute("threshold", req.threshold)

        upstream_t0 = time.perf_counter()
        try:
            resp = await toxicity_client.post(
                "/predict",
                json=req.model_dump(),
            )
            resp.raise_for_status()

        except httpx.TimeoutException:
            ERROR_COUNT.labels(model=MODEL, error_type="timeout").inc()
            REQUEST_COUNT.labels(model=MODEL, status_code="504").inc()
            span.set_attribute("error", True)
            raise HTTPException(status_code=504, detail="Toxicity service timeout")

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

        span.set_attribute("result.is_toxic", data["is_toxic"])
        span.set_attribute("result.score", data["score"])

        return ToxicityResponse(
            label=data["label"],
            score=data["score"],
            is_toxic=data["is_toxic"],
            upstream_latency_ms=round(upstream_latency * 1000, 2),
        )