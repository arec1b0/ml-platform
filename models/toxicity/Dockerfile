FROM python:3.11-slim AS builder

WORKDIR /build
RUN pip install uv --no-cache-dir

COPY pyproject.toml .
RUN uv pip install --system --no-cache-dir \
    fastapi uvicorn pydantic \
    transformers torch mlflow \
    opentelemetry-sdk \
    opentelemetry-instrumentation-fastapi

# Pre-download weights в слой (кэш между сборками)
RUN python -c "from transformers import pipeline; pipeline('text-classification', model='unitary/toxic-bert')"

FROM python:3.11-slim AS runtime
WORKDIR /app

COPY --from=builder /usr/local/lib/python3.11 /usr/local/lib/python3.11
COPY --from=builder /root/.cache/huggingface /root/.cache/huggingface
COPY serve.py .

ENV PYTHONUNBUFFERED=1
EXPOSE 8080

CMD ["uvicorn", "serve:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2"]