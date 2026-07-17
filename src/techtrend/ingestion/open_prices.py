"""Open Prices connector (https://prices.openfoodfacts.org).

A real, keyless public API of crowdsourced product prices. This connector
demonstrates the incremental-REST pattern used for any SaaS source:

* cursor pagination with bounded page count,
* retry with exponential backoff on transient failures,
* watermark-based delta extraction (``created`` >= last watermark),
* graceful *offline mode* falling back to a bundled fixture so the demo
  pipeline runs with zero network access or credentials.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

import httpx
import polars as pl

from techtrend.common.logging import get_logger
from techtrend.config.settings import get_settings
from techtrend.ingestion.base import LandingManifest, get_watermark, land_raw, set_watermark

log = get_logger(__name__)

SOURCE = "open_prices"
RETRYABLE = {429, 500, 502, 503, 504}

_COLUMNS = {
    "id": pl.Int64,
    "product_code": pl.Utf8,
    "product_name": pl.Utf8,
    "category_tag": pl.Utf8,
    "price": pl.Float64,
    "currency": pl.Utf8,
    "date": pl.Utf8,
    "location_osm_display_name": pl.Utf8,
    "created": pl.Utf8,
}


def _fetch_page(client: httpx.Client, url: str, params: dict, attempts: int = 4) -> dict:
    delay = 1.0
    for attempt in range(1, attempts + 1):
        try:
            resp = client.get(url, params=params, timeout=30)
            if resp.status_code in RETRYABLE:
                raise httpx.HTTPStatusError("retryable", request=resp.request, response=resp)
            resp.raise_for_status()
            return resp.json()
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            if attempt == attempts:
                raise
            log.warning("fetch_retry", url=url, attempt=attempt, error=str(exc))
            time.sleep(delay)
            delay *= 2
    raise RuntimeError("unreachable")


def _normalise(items: list[dict]) -> pl.DataFrame:
    rows = []
    for it in items:
        product = it.get("product") or {}
        rows.append(
            {
                "id": it.get("id"),
                "product_code": it.get("product_code"),
                "product_name": product.get("product_name"),
                "category_tag": it.get("category_tag"),
                "price": it.get("price"),
                "currency": it.get("currency"),
                "date": it.get("date"),
                "location_osm_display_name": it.get("location_osm_display_name"),
                "created": it.get("created"),
            }
        )
    return pl.DataFrame(rows, schema=_COLUMNS) if rows else pl.DataFrame(schema=_COLUMNS)


def extract(load_date: str | None = None) -> LandingManifest | None:
    """Pull price deltas since the stored watermark and land them raw."""
    settings = get_settings()
    load_date = load_date or datetime.now(UTC).strftime("%Y-%m-%d")

    if settings.ingestion_offline:
        return _extract_offline(load_date)

    watermark = get_watermark(SOURCE)
    params: dict = {"size": settings.open_prices_page_size, "order_by": "created"}
    if watermark:
        params["created__gte"] = watermark

    frames: list[pl.DataFrame] = []
    with httpx.Client(base_url=settings.open_prices_base_url) as client:
        for page in range(1, settings.open_prices_max_pages + 1):
            payload = _fetch_page(client, "/prices", {**params, "page": page})
            items = payload.get("items", [])
            if not items:
                break
            frames.append(_normalise(items))
            if page >= payload.get("pages", page):
                break

    if not frames:
        log.info("no_deltas", source=SOURCE, watermark=watermark)
        return None

    df = pl.concat(frames)
    manifest = land_raw(
        df,
        source=SOURCE,
        dataset="prices",
        load_date=load_date,
        params={"watermark": watermark or "", "mode": "incremental"},
    )
    new_watermark = df.select(pl.col("created").max()).item()
    if new_watermark:
        set_watermark(SOURCE, str(new_watermark))
    return manifest


def _extract_offline(load_date: str) -> LandingManifest:
    """Deterministic fixture landing for the keyless demo path and CI."""
    fixture = pl.DataFrame(
        {
            "id": [1, 2, 3],
            "product_code": ["3017620422003", "5449000000996", "7622210449283"],
            "product_name": ["Nutella 400g", "Coca-Cola 1.5L", "Milka Alpine Milk"],
            "category_tag": ["en:spreads", "en:sodas", "en:chocolates"],
            "price": [4.29, 2.15, 1.99],
            "currency": ["EUR", "EUR", "EUR"],
            "date": [load_date] * 3,
            "location_osm_display_name": ["Carrefour, Paris"] * 3,
            "created": [f"{load_date}T00:00:00Z"] * 3,
        },
        schema=_COLUMNS,
    )
    return land_raw(
        fixture,
        source=SOURCE,
        dataset="prices",
        load_date=load_date,
        params={"mode": "offline_fixture"},
    )
