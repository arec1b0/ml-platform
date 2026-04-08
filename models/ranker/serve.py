import os
import time
import logging
from contextlib import asynccontextmanager

import mlflow
import lightgbm as lgb
import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sklearn.feature_extraction.text import TfidfVectorizer
import joblib

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

_model = None
_vectorizer = None
_model_ready = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _model, _vectorizer, _model_ready

    mlflow_uri = os.environ["MLFLOW_TRACKING_URI"]
    model_name = os.environ.get("MODEL_NAME", "comment-ranker")
    model_stage = os.environ.get("MODEL_STAGE", "Production")

    mlflow.set_tracking_uri(mlflow_uri)

    try:
        model_uri = f"models:/{model_name}/{model_stage}"
        loaded = mlflow.lightgbm.load_model(model_uri)
        _model = loaded["model"]
        _vectorizer = loaded["vectorizer"]
        _model_ready = True
        logger.info(f"Ranker loaded: {model_uri}")
    except Exception as e:
        logger.warning(f"MLflow load failed ({e}), using stub model")
        # Стаб для первого деплоя — реальный ranker тренируется отдельно
        _model = None
        _vectorizer = None
        _model_ready = True

    yield
    _model_ready = False


app = FastAPI(lifespan=lifespan)


class RankRequest(BaseModel):
    texts: list[str]


class RankResponse(BaseModel):
    scores: list[float]
    ranked_indices: list[int]
    latency_ms: float


@app.get("/health/live")
def liveness():
    return {"status": "alive"}


@app.get("/health/ready")
def readiness():
    if not _model_ready:
        raise HTTPException(status_code=503, detail="Model not loaded")
    return {"status": "ready"}


@app.post("/predict", response_model=RankResponse)
def predict(req: RankRequest):
    if not _model_ready:
        raise HTTPException(status_code=503, detail="Model not ready")

    t0 = time.perf_counter()

    if _model is None:
        # Стаб: возвращаем random scores (только для dev)
        scores = np.random.rand(len(req.texts)).tolist()
    else:
        X = _vectorizer.transform(req.texts)
        scores = _model.predict(X).tolist()

    latency_ms = (time.perf_counter() - t0) * 1000
    ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)

    return RankResponse(
        scores=scores,
        ranked_indices=ranked_indices,
        latency_ms=round(latency_ms, 2),
    )