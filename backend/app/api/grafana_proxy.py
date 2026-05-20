"""Резервный прокси /grafana/* → Grafana (основной путь — nginx → host.docker.internal:3001)."""
from __future__ import annotations

import logging
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Request, Response
from fastapi.responses import RedirectResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["grafana-proxy"])

# Полный путь /grafana/... — как ожидает GF_SERVER_SERVE_FROM_SUB_PATH
GRAFANA_BASE = "http://grafana:3000"

HOP_BY_HOP = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
        "content-length",
        "content-encoding",
    }
)


def _upstream_url(request: Request) -> str:
    path = request.url.path
    if path == "/grafana":
        path = "/grafana/"
    url = f"{GRAFANA_BASE}{path}"
    if request.url.query:
        url = f"{url}?{request.url.query}"
    return url


def _forward_headers(request: Request) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in request.headers.items():
        lk = key.lower()
        if lk in HOP_BY_HOP or lk == "host":
            continue
        out[key] = value
    return out


def _rewrite_location(location: str, request: Request) -> str:
    if not location:
        return location
    parsed = urlparse(location)
    public = str(request.base_url).rstrip("/")
    if parsed.scheme and parsed.netloc:
        path = parsed.path or "/"
        if not path.startswith("/grafana"):
            path = f"/grafana{path}" if path.startswith("/") else f"/grafana/{path}"
        out = f"{public}{path}"
        if parsed.query:
            out += f"?{parsed.query}"
        return out
    if location.startswith("/grafana"):
        return f"{public}{location}"
    if location.startswith("/"):
        return f"{public}/grafana{location}"
    return location


def _response_headers(resp: httpx.Response, request: Request) -> list[tuple[str, str]]:
    headers: list[tuple[str, str]] = []
    for key, value in resp.headers.multi_items():
        lk = key.lower()
        if lk in HOP_BY_HOP:
            continue
        if lk == "location":
            value = _rewrite_location(value, request)
        headers.append((key, value))
    return headers


@router.get("/grafana", include_in_schema=False)
async def grafana_root_redirect():
    return RedirectResponse(url="/grafana/", status_code=308)


@router.api_route(
    "/grafana/",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
    include_in_schema=False,
)
@router.api_route(
    "/grafana/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
    include_in_schema=False,
)
async def grafana_proxy(request: Request, path: str = ""):
    url = _upstream_url(request)
    headers = _forward_headers(request)
    body = await request.body()

    try:
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=False) as client:
            resp = await client.request(request.method, url, headers=headers, content=body)
    except httpx.RequestError as exc:
        logger.warning("Grafana proxy failed: %s -> %s", url, exc)
        return Response(content=f"Grafana unavailable: {exc}", status_code=502, media_type="text/plain")
    except Exception:
        logger.exception("Grafana proxy error for %s", url)
        return Response(content="Grafana proxy error", status_code=502, media_type="text/plain")

    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=_response_headers(resp, request),
    )
