import os
import time
import logging
from contextlib import asynccontextmanager

import mlflow
import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from transformers import pipeline

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Глобальное состояние — загружается один раз при старте
_model = None
_model_ready = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _model, _model_ready
    logger.info("Loading toxicity model from MLflow...")
    
    mlflow_uri = os.environ["MLFLOW_TRACKING_URI"]
    model_name = os.environ.get("MODEL_NAME", "toxicity-classifier")
    model_stage = os.environ.get("MODEL_STAGE", "Production")

    mlflow.set_tracking_uri(mlflow_uri)
    
    try:
        model_uri = f"models:/{model_name}/{model_stage}"
        # MLflow загружает трансформер-пайплайн
        _model = mlflow.transformers.load_model(model_uri)
        _model_ready = True
        logger.info(f"Model loaded: {model_uri}")
    except Exception as e:
        # Fallback: грузим напрямую с HuggingFace (для первого деплоя)
        logger.warning(f"MLflow load failed ({e}), loading from HuggingFace")
        _model = pipeline(
            "text-classification",
            model="unitary/toxic-bert",
            device=-1,  # CPU; поменяй на 0 для GPU
        )
        _model_ready = True
        logger.info("Model loaded from HuggingFace")

    yield
    _model_ready = False


app = FastAPI(lifespan=lifespan)


class PredictRequest(BaseModel):
    text: str
    threshold: float = 0.5


class PredictResponse(BaseModel):
    label: str
    score: float
    is_toxic: bool
    latency_ms: float


@app.get("/health/live")
def liveness():
    return {"status": "alive"}


@app.get("/health/ready")
def readiness():
    """Prometheus / Argo Rollouts проверяет этот endpoint."""
    if not _model_ready:
        raise HTTPException(status_code=503, detail="Model not loaded")
    return {"status": "ready"}


@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    if not _model_ready:
        raise HTTPException(status_code=503, detail="Model not ready")

    t0 = time.perf_counter()
    result = _model(req.text)[0]
    latency_ms = (time.perf_counter() - t0) * 1000

    return PredictResponse(
        label=result["label"],
        score=result["score"],
        is_toxic=result["label"] == "toxic" and result["score"] >= req.threshold,
        latency_ms=round(latency_ms, 2),
    )