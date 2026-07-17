"""Data quality scoring.

Computes the five classic DQ dimensions over the silver layer --
completeness, uniqueness, validity, consistency, freshness -- and rolls
them into a weighted composite score. The result is written to the gold
layer and surfaced through both the API and the Grafana dashboard.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime

import polars as pl

from techtrend.common.lake_io import lake_path, write_parquet
from techtrend.common.logging import get_logger

log = get_logger(__name__)

WEIGHTS = {
    "completeness": 0.25,
    "uniqueness": 0.25,
    "validity": 0.20,
    "consistency": 0.15,
    "freshness": 0.15,
}


@dataclass(frozen=True)
class QualityReport:
    computed_at: str
    completeness: float
    uniqueness: float
    validity: float
    consistency: float
    freshness: float
    composite_score: float
    rows_evaluated: int
    rejected_rows: int


def compute(observations: pl.DataFrame, rejected_rows: int = 0) -> QualityReport:
    n = observations.height or 1

    critical = ["product_id", "observed_date", "price"]
    completeness = float(
        1
        - observations.select(
            pl.mean_horizontal([pl.col(c).is_null().cast(pl.Float64) for c in critical])
        )
        .mean()
        .item()
    )

    uniqueness = float(observations.select(["product_id", "observed_date"]).unique().height / n)

    validity = float(
        observations.filter(
            (pl.col("price") > 0)
            & (pl.col("discount_percentage").is_between(0, 95))
            & (pl.col("rating").is_between(0, 5) | pl.col("rating").is_null())
        ).height
        / n
    )

    # consistency: discounted price should not exceed original price
    with_orig = observations.filter(pl.col("original_price").is_not_null())
    consistency = float(
        with_orig.filter(pl.col("price") <= pl.col("original_price") * 1.001).height
        / (with_orig.height or 1)
    )

    latest: date = observations.select(pl.col("observed_date").max()).item()
    staleness_days = (datetime.now(UTC).date() - latest).days if latest else 999
    freshness = max(0.0, 1 - staleness_days / 30)  # linear decay over 30 days

    dims = {
        "completeness": round(completeness, 4),
        "uniqueness": round(uniqueness, 4),
        "validity": round(validity, 4),
        "consistency": round(consistency, 4),
        "freshness": round(freshness, 4),
    }
    composite = round(sum(WEIGHTS[k] * v for k, v in dims.items()), 4)

    report = QualityReport(
        computed_at=datetime.now(UTC).isoformat(),
        composite_score=composite,
        rows_evaluated=observations.height,
        rejected_rows=rejected_rows,
        **dims,
    )
    log.info("quality_report", **asdict(report))
    return report


def persist(report: QualityReport) -> None:
    df = pl.DataFrame([asdict(report)])
    write_parquet(df, "gold", "quality", "quality_report.parquet")
    path = lake_path("gold", "quality", "quality_report.json")
    if not path.startswith("s3://"):
        from pathlib import Path

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(asdict(report), indent=2))
