FROM python:3.11-slim AS builder
WORKDIR /build

RUN pip install uv --no-cache-dir
COPY pyproject.toml .
RUN uv pip install --system --no-cache-dir \
    fastapi uvicorn pydantic pydantic-settings \
    httpx tenacity \
    prometheus-client \
    opentelemetry-sdk \
    opentelemetry-exporter-otlp-proto-grpc \
    opentelemetry-instrumentation-fastapi \
    opentelemetry-instrumentation-httpx

FROM python:3.11-slim AS runtime
WORKDIR /app

COPY --from=builder /usr/local/lib/python3.11 /usr/local/lib/python3.11
COPY . .

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]