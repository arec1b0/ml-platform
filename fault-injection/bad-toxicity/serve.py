"""
Модель с инжектированным error rate ~15%.
Цель: нарушить условие error_rate < 1% и получить автоматический rollback.
"""
import os
import random
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Вероятность ошибки — настраивается через env
ERROR_RATE = float(os.environ.get("INJECT_ERROR_RATE", "0.15"))
_ready = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _ready
    # Намеренная задержка — имитирует реальную загрузку весов
    await asyncio.sleep(5)
    _ready = True
    yield
    _ready = False


import asyncio
app = FastAPI(lifespan=lifespan)


class PredictRequest(BaseModel):
    text: str
    threshold: float = 0.5


@app.get("/health/live")
def liveness():
    return {"status": "alive"}


@app.get("/health/ready")
def readiness():
    # Readiness проходит — pod выглядит здоровым
    # Это важно: rollback должен работать по метрикам, а не по probe
    if not _ready:
        raise HTTPException(status_code=503, detail="not ready")
    return {"status": "ready"}


@app.post("/predict")
def predict(req: PredictRequest):
    if not _ready:
        raise HTTPException(status_code=503, detail="not ready")

    # Инжектируем ошибку
    if random.random() < ERROR_RATE:
        raise HTTPException(
            status_code=500,
            detail="Internal model error (injected fault)",
        )

    # Остальные запросы — нормальные ответы
    return {
        "label": "toxic",
        "score": 0.85,
        "is_toxic": True,
        "latency_ms": 45.0,
    }