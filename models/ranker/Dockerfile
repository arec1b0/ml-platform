FROM python:3.11-slim AS builder

WORKDIR /build
RUN pip install uv --no-cache-dir

RUN uv pip install --system --no-cache-dir \
    fastapi uvicorn pydantic \
    lightgbm scikit-learn numpy \
    mlflow joblib \
    opentelemetry-sdk \
    opentelemetry-instrumentation-fastapi

FROM python:3.11-slim AS runtime
WORKDIR /app

COPY --from=builder /usr/local/lib/python3.11 /usr/local/lib/python3.11
COPY serve.py .

ENV PYTHONUNBUFFERED=1
EXPOSE 8080

CMD ["uvicorn", "serve:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "4"]