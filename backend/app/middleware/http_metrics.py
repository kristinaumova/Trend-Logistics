import re
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.services.metrics_registry import HTTP_REQUEST_DURATION, HTTP_REQUESTS

_ID_SEGMENT = re.compile(r"/\d+")
_METRIC_SKIP_PREFIXES = ("/grafana",)


def _metric_path(path: str) -> str:
    for prefix in _METRIC_SKIP_PREFIXES:
        if path.startswith(prefix):
            return prefix
    if path.startswith("/api/v1"):
        path = path[7:] or "/"
    elif path.startswith("/api/"):
        path = path[4:] or "/"
    path = _ID_SEGMENT.sub("/{id}", path)
    return path or "/"


class HttpMetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path == "/metrics":
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start

        path = _metric_path(request.url.path)
        status = str(response.status_code)
        method = request.method

        HTTP_REQUESTS.labels(method=method, path=path, status=status).inc()
        HTTP_REQUEST_DURATION.labels(method=method, path=path).observe(duration)

        return response
