from prometheus_client import Counter, Histogram

FORECASTS_CREATED = Counter(
    "trend_forecasts_created_total",
    "Число сохранённых прогнозов",
    ["transport_type"],
)

SHIPMENTS_CREATED = Counter(
    "trend_shipments_created_total",
    "Число созданных поставок",
    ["transport_type"],
)

HTTP_REQUESTS = Counter(
    "trend_http_requests_total",
    "HTTP-запросы к API",
    ["method", "path", "status"],
)

HTTP_REQUEST_DURATION = Histogram(
    "trend_http_request_duration_seconds",
    "Длительность HTTP-запросов",
    ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)
