from prometheus_client import Counter, Histogram, Gauge

# Все метрики под одним namespace — проще писать PromQL
REQUEST_COUNT = Counter(
    "gateway_requests_total",
    "Total requests per model and status",
    ["model", "status_code"],
)

REQUEST_LATENCY = Histogram(
    "gateway_request_duration_seconds",
    "End-to-end latency per model",
    ["model"],
    # Buckets под SLO: p99 < 200ms
    buckets=[0.01, 0.025, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 1.0, 2.0],
)

UPSTREAM_LATENCY = Histogram(
    "gateway_upstream_duration_seconds",
    "Latency of upstream model service call",
    ["model"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 1.0],
)

ERROR_COUNT = Counter(
    "gateway_errors_total",
    "Errors by model and type",
    ["model", "error_type"],  # timeout | upstream_error | validation_error
)

UPSTREAM_HEALTH = Gauge(
    "gateway_upstream_healthy",
    "1 if upstream is healthy, 0 otherwise",
    ["model"],
)