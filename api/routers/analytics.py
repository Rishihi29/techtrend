"""Executive analytics, ML surfaces, and data-quality endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from api.repositories import warehouse
from api.schemas.models import Anomaly, CategoryDaily, Deal, Insight, Kpis, QualityReport

router = APIRouter(tags=["analytics"])


@router.get("/analytics/kpis", response_model=Kpis)
def get_kpis():
    return warehouse.kpis()


@router.get("/analytics/categories/daily", response_model=list[CategoryDaily])
def get_category_daily():
    return warehouse.category_daily()


@router.get("/analytics/insights", response_model=list[Insight])
def get_insights():
    out = []
    for row in warehouse.insights():
        pct = row.get("pct_change_7d")
        if pct is None:
            continue
        verb = "rose" if row["direction"] == "up" else "fell"
        row["headline"] = f"{row['category']} prices {verb} {abs(pct):.1f}% over the last 7 days"
        out.append(row)
    return out


@router.get("/deals", response_model=list[Deal])
def get_deals(limit: int = Query(20, ge=1, le=100)):
    return warehouse.top_deals(limit)


@router.get("/anomalies", response_model=list[Anomaly])
def get_anomalies(limit: int = Query(50, ge=1, le=500)):
    return warehouse.anomalies(limit)


@router.get("/quality", response_model=QualityReport)
def get_quality():
    kpis = warehouse.kpis()
    if not kpis.get("quality"):
        raise HTTPException(404, "no quality report published yet")
    return kpis["quality"]
