"""Pydantic response models -- the API's public contract."""

from __future__ import annotations

from datetime import date, datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    page: int
    page_size: int
    total: int
    total_pages: int


class ProductSummary(BaseModel):
    product_id: int
    product_name: str
    category: str
    subcategory: str | None = None
    brand: str | None = None
    audience: str | None = None
    image_url: str | None = None
    segment_name: str | None = None
    avg_price: float
    min_price: float
    max_price: float
    avg_rating: float | None = None
    base_rating: float | None = None
    total_reviews: int | None = None
    avg_discount: float | None = None
    price_volatility: float | None = None
    data_points: int


class PricePoint(BaseModel):
    observed_date: date
    price: float
    original_price: float | None = None
    discount_percentage: float | None = None
    rating: float | None = None
    sales_velocity: float | None = None


class ForecastPoint(BaseModel):
    forecast_date: date
    yhat: float
    yhat_lower: float
    yhat_upper: float
    model_run_id: str


class Recommendation(BaseModel):
    product_id: int
    product_name: str
    category: str
    brand: str | None = None
    image_url: str | None = None
    rank: int
    similarity: float
    reason: str
    avg_price: float
    avg_rating: float | None = None


class Anomaly(BaseModel):
    product_id: int
    product_name: str
    category: str
    observed_date: date
    price: float
    price_pct_change: float
    robust_z: float
    iforest_score: float
    anomaly_type: str


class Deal(BaseModel):
    product_id: int
    product_name: str
    category: str
    brand: str | None = None
    image_url: str | None = None
    current_price: float
    original_price: float | None = None
    discount_percentage: float
    rating: float | None = None
    observed_date: date


class QualityReport(BaseModel):
    computed_at: datetime
    completeness: float
    uniqueness: float
    validity: float
    consistency: float
    freshness: float
    composite_score: float
    rows_evaluated: int
    rejected_rows: int


class Kpis(BaseModel):
    products: int
    categories: int
    brands: int
    warehouse_rows: int
    active_deals: int
    anomalies: int
    avg_price: float | None = None
    avg_discount: float | None = None
    quality: QualityReport | None = None


class Insight(BaseModel):
    category: str
    pct_change_7d: float | None = None
    direction: str
    headline: str = Field(default="")


class CategoryDaily(BaseModel):
    category: str
    full_date: date
    products_observed: int
    avg_price: float
    min_price: float
    max_price: float
    avg_discount: float | None = None
    total_sales_velocity: float | None = None
