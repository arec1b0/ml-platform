import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from prometheus_client import make_asgi_app

from core.config import settings
from core.tracing import setup_tracing
from core.http_client import init_clients, close_clients
from core.metrics import UPSTREAM_HEALTH
from routers import toxicity, ranker, monitoring

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_clients()
    logger.info("HTTP clients initialized")

    # Начальная проверка upstream health
    await _check_upstream_health()

    yield

    await close_clients()
    logger.info("HTTP clients closed")


app = FastAPI(
    title="ML Platform Gateway",
    version="1.0.0",
    lifespan=lifespan,
)

setup_tracing(app)

# Prometheus metrics endpoint — отдельный ASGI app на /metrics
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

app.include_router(toxicity.router)
app.include_router(ranker.router)
app.include_router(monitoring.router)


async def _check_upstream_health():
    from core.http_client import toxicity_client, ranker_client
    import httpx

    for name, client in [("toxicity", toxicity_client), ("ranker", ranker_client)]:
        try:
            resp = await client.get("/health/ready", timeout=2.0)
            healthy = resp.status_code == 200
        except (httpx.RequestError, Exception):
            healthy = False

        UPSTREAM_HEALTH.labels(model=name).set(1 if healthy else 0)
        logger.info(f"Upstream {name}: {'healthy' if healthy else 'UNHEALTHY'}")


@app.get("/health/live")
def liveness():
    return {"status": "alive"}


@app.get("/health/ready")
async def readiness():
    """
    Gateway готов, если хотя бы один upstream отвечает.
    Жёсткий require-all сломает деплой при rolling update upstream.
    """
    from core.http_client import toxicity_client, ranker_client
    import httpx

    results = {}
    for name, client in [("toxicity", toxicity_client), ("ranker", ranker_client)]:
        try:
            resp = await client.get("/health/ready", timeout=1.0)
            results[name] = resp.status_code == 200
            UPSTREAM_HEALTH.labels(model=name).set(1 if results[name] else 0)
        except (httpx.RequestError, Exception):
            results[name] = False
            UPSTREAM_HEALTH.labels(model=name).set(0)

    if not any(results.values()):
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail=f"All upstreams unhealthy: {results}")

    return {"status": "ready", "upstreams": results}