"""TechTrend Enterprise Data Platform -- serving API.

FastAPI application exposing the warehouse marts and ML scores with full
OpenAPI documentation, Prometheus metrics, and the executive dashboard.
"""

from __future__ import annotations

import time
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.routers import analytics, products
from techtrend import __version__
from techtrend.common.logging import configure_logging, get_logger
from techtrend.config.settings import get_settings

configure_logging()
log = get_logger("api")
settings = get_settings()

app = FastAPI(
    title=settings.api_title,
    version=__version__,
    description=(
        "Price intelligence, demand forecasting, and market analytics over the "
        "TechTrend lakehouse. All data served from the dimensional warehouse; "
        "ML scores from the model registry pipeline."
    ),
    openapi_tags=[
        {"name": "products", "description": "Catalog with pagination, filtering, search"},
        {"name": "analytics", "description": "Executive KPIs, insights, deals, anomalies, DQ"},
        {"name": "system", "description": "Health and observability"},
    ],
)

# ---------------------------------------------------------- observability ---
_REQUESTS: dict[tuple[str, int], int] = {}
_LATENCY: list[float] = []


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start
    key = (request.url.path, response.status_code)
    _REQUESTS[key] = _REQUESTS.get(key, 0) + 1
    _LATENCY.append(elapsed)
    if len(_LATENCY) > 10_000:
        del _LATENCY[: len(_LATENCY) // 2]
    response.headers["x-response-time-ms"] = f"{elapsed * 1000:.1f}"
    return response


@app.get("/metrics", tags=["system"], include_in_schema=False)
def metrics() -> Response:
    """Prometheus exposition format (scraped by the monitoring stack)."""
    lines = [
        "# HELP techtrend_http_requests_total Total HTTP requests",
        "# TYPE techtrend_http_requests_total counter",
    ]
    for (path, status), count in sorted(_REQUESTS.items()):
        lines.append(f'techtrend_http_requests_total{{path="{path}",status="{status}"}} {count}')
    if _LATENCY:
        ordered = sorted(_LATENCY)
        for q, label in ((0.5, "p50"), (0.95, "p95"), (0.99, "p99")):
            idx = min(int(q * len(ordered)), len(ordered) - 1)
            lines += [
                f'techtrend_http_latency_seconds{{quantile="{label}"}} {ordered[idx]:.6f}',
            ]
    return Response("\n".join(lines) + "\n", media_type="text/plain")


@app.get("/health", tags=["system"])
def health() -> dict:
    from api.repositories import warehouse

    try:
        warehouse.scalar("SELECT 1")
        return {"status": "ok", "version": __version__, "warehouse": settings.warehouse_backend}
    except Exception as exc:  # surfaced, never swallowed
        log.error("healthcheck_failed", error=str(exc))
        return {"status": "degraded", "detail": str(exc)}


# ------------------------------------------------------------------ routes --
app.include_router(products.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", include_in_schema=False)
def dashboard() -> FileResponse:
    return FileResponse(static_dir / "index.html")
