"""
Модель с инжектированной задержкой ~350ms p99.
Цель: нарушить условие p99 latency < 200ms.
"""
import asyncio
import os
import random
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Параметры latency distribution
P50_LATENCY_MS = float(os.environ.get("INJECT_P50_MS", "80"))
P99_LATENCY_MS = float(os.environ.get("INJECT_P99_MS", "350"))

_ready = False


def _sample_latency_ms() -> float:
    """
    Имитируем реалистичное latency распределение.
    99% запросов — P50, 1% — P99.
    """
    if random.random() < 0.01:
        return P99_LATENCY_MS + random.uniform(0, 50)
    return P50_LATENCY_MS + random.uniform(-20, 20)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _ready
    await asyncio.sleep(5)
    _ready = True
    yield
    _ready = False


app = FastAPI(lifespan=lifespan)


class PredictRequest(BaseModel):
    text: str
    threshold: float = 0.5


@app.get("/health/live")
def liveness():
    return {"status": "alive"}


@app.get("/health/ready")
def readiness():
    if not _ready:
        raise HTTPException(status_code=503, detail="not ready")
    return {"status": "ready"}


@app.post("/predict")
async def predict(req: PredictRequest):
    if not _ready:
        raise HTTPException(status_code=503, detail="not ready")

    latency_ms = _sample_latency_ms()
    await asyncio.sleep(latency_ms / 1000)

    return {
        "label": "non-toxic",
        "score": 0.12,
        "is_toxic": False,
        "latency_ms": round(latency_ms, 2),
    }