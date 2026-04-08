from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource

from .config import settings


def setup_tracing(app) -> None:
    resource = Resource.create({"service.name": settings.service_name})

    exporter = OTLPSpanExporter(endpoint=settings.otel_endpoint, insecure=True)

    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    # Автоматически инструментирует все FastAPI endpoints
    FastAPIInstrumentor.instrument_app(app)

    # Автоматически инструментирует все httpx вызовы к upstream
    HTTPXClientInstrumentor().instrument()