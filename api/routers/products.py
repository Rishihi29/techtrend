"""Product catalog endpoints: pagination, filtering, sorting, search."""

from __future__ import annotations

import math
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from api.repositories import warehouse
from api.schemas.models import (
    ForecastPoint,
    Page,
    PricePoint,
    ProductSummary,
    Recommendation,
)
from techtrend.config.settings import get_settings

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=Page[ProductSummary])
def list_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1),
    category: str | None = None,
    brand: str | None = None,
    search: str | None = Query(None, min_length=1, max_length=100),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    min_rating: float | None = Query(None, ge=0, le=5),
    sort_by: Literal[
        "avg_price",
        "avg_rating",
        "avg_discount",
        "price_volatility",
        "total_reviews",
        "product_name",
    ] = "avg_price",
    order: Literal["asc", "desc"] = "asc",
):
    page_size = min(page_size, get_settings().api_page_size_max)
    rows, total = warehouse.list_products(
        page=page,
        page_size=page_size,
        category=category,
        brand=brand,
        search=search,
        min_price=min_price,
        max_price=max_price,
        min_rating=min_rating,
        sort_by=sort_by,
        descending=order == "desc",
    )
    return Page(
        items=rows,
        page=page,
        page_size=page_size,
        total=total,
        total_pages=max(1, math.ceil(total / page_size)),
    )


@router.get("/facets")
def get_facets() -> dict[str, list[str]]:
    return warehouse.facets()


@router.get("/{product_id}", response_model=ProductSummary)
def get_product(product_id: int):
    product = warehouse.get_product(product_id)
    if not product:
        raise HTTPException(404, f"product {product_id} not found")
    return product


@router.get("/{product_id}/price-history", response_model=list[PricePoint])
def get_price_history(product_id: int):
    if not warehouse.get_product(product_id):
        raise HTTPException(404, f"product {product_id} not found")
    return warehouse.price_history(product_id)


@router.get("/{product_id}/forecast", response_model=list[ForecastPoint])
def get_forecast(product_id: int, target: Literal["price", "sales_velocity"] = "price"):
    return warehouse.forecast(product_id, target)


@router.get("/{product_id}/recommendations", response_model=list[Recommendation])
def get_recommendations(product_id: int):
    return warehouse.recommendations(product_id)
