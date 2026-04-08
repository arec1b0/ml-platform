import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .config import settings


def _build_client(base_url: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=base_url,
        timeout=httpx.Timeout(
            connect=settings.connect_timeout_s,
            read=settings.request_timeout_s,
            write=settings.request_timeout_s,
            pool=1.0,
        ),
    )


# Клиенты создаются один раз при старте
toxicity_client: httpx.AsyncClient = None
ranker_client: httpx.AsyncClient = None


async def init_clients() -> None:
    global toxicity_client, ranker_client
    toxicity_client = _build_client(settings.toxicity_url)
    ranker_client = _build_client(settings.ranker_url)


async def close_clients() -> None:
    if toxicity_client:
        await toxicity_client.aclose()
    if ranker_client:
        await ranker_client.aclose()