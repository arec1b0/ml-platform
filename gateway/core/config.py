from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    toxicity_url: str = "http://toxicity"
    ranker_url: str = "http://ranker"

    # Таймауты — явные, не дефолтные
    request_timeout_s: float = 5.0
    connect_timeout_s: float = 1.0

    # Retry policy
    max_retries: int = 2
    retry_on_status: list[int] = [502, 503, 504]

    # OTEL
    otel_endpoint: str = "http://otel-collector:4317"
    service_name: str = "ml-gateway"

    class Config:
        env_file = ".env"


settings = Settings()