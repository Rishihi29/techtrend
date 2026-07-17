"""Silver -> Gold: analytics-ready feature sets and aggregates.

Gold artifacts and their consumers:

* ``product_daily_features`` -- lag/rolling/calendar features consumed by
  every ML pipeline (single feature definition, no train/serve skew),
* ``category_daily``         -- category-level market aggregates,
* ``product_segments``       -- K-Means segmentation (the original
  TechTrend clustering, preserved as a governed feature rather than a
  headline "AI" claim), consumed by the recommender and the API.
"""

from __future__ import annotations

import polars as pl
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from techtrend.common.lake_io import scan_parquet, write_parquet
from techtrend.common.logging import get_logger

log = get_logger(__name__)

SEGMENT_LABELS = ["Value", "Premium", "Deal-Driven", "Standard"]


def load_observations() -> pl.DataFrame:
    return (
        scan_parquet("silver", "price_observations", "month=*", "*.parquet")
        .collect()
        .sort(["product_id", "observed_date"])
    )


def build() -> dict[str, int]:
    obs = load_observations()
    products = scan_parquet("silver", "products", "products.parquet").collect()

    features = _product_daily_features(obs)
    write_parquet(features, "gold", "features", "product_daily_features.parquet")

    category_daily = (
        obs.join(products.select("product_id", "category"), on="product_id")
        .group_by(["category", "observed_date"])
        .agg(
            pl.len().alias("products_observed"),
            pl.col("price").mean().alias("avg_price"),
            pl.col("price").min().alias("min_price"),
            pl.col("price").max().alias("max_price"),
            pl.col("discount_percentage").mean().alias("avg_discount"),
            pl.col("sales_velocity").sum().alias("total_sales_velocity"),
        )
        .sort(["category", "observed_date"])
    )
    write_parquet(category_daily, "gold", "aggregates", "category_daily.parquet")

    segments = _product_segments(obs, products)
    write_parquet(segments, "gold", "segments", "product_segments.parquet")

    counts = {
        "product_daily_features": features.height,
        "category_daily": category_daily.height,
        "product_segments": segments.height,
    }
    log.info("gold_complete", **counts)
    return counts


def _product_daily_features(obs: pl.DataFrame) -> pl.DataFrame:
    return obs.sort(["product_id", "observed_date"]).with_columns(
        pl.col("price").shift(1).over("product_id").alias("price_lag_1"),
        pl.col("price").shift(7).over("product_id").alias("price_lag_7"),
        pl.col("price").rolling_mean(7).over("product_id").alias("price_ma_7"),
        pl.col("price").rolling_mean(30).over("product_id").alias("price_ma_30"),
        pl.col("price").rolling_std(7).over("product_id").alias("price_std_7"),
        (pl.col("price").pct_change().over("product_id") * 100).alias("price_pct_change"),
        pl.col("sales_velocity").shift(1).over("product_id").alias("velocity_lag_1"),
        pl.col("sales_velocity").rolling_mean(7).over("product_id").alias("velocity_ma_7"),
        pl.col("observed_date").dt.weekday().alias("day_of_week"),
        (pl.col("observed_date").dt.weekday() >= 6).alias("is_weekend"),
        pl.col("observed_date").dt.month().alias("month_num"),
    )


def _product_segments(obs: pl.DataFrame, products: pl.DataFrame) -> pl.DataFrame:
    profile = obs.group_by("product_id").agg(
        pl.col("price").mean().alias("avg_price"),
        (pl.col("price").std() / pl.col("price").mean()).alias("price_volatility"),
        pl.col("discount_percentage").mean().alias("avg_discount"),
        pl.col("rating").mean().alias("avg_rating"),
        pl.col("sales_velocity").mean().alias("avg_velocity"),
    )
    feature_cols = ["avg_price", "price_volatility", "avg_discount", "avg_rating", "avg_velocity"]
    profile = profile.with_columns([pl.col(c).fill_null(0.0).fill_nan(0.0) for c in feature_cols])
    x = StandardScaler().fit_transform(profile.select(feature_cols).to_numpy())
    k = min(len(SEGMENT_LABELS), max(2, profile.height // 25))
    model = KMeans(n_clusters=k, n_init=10, random_state=42)
    labels = model.fit_predict(x)

    profile = profile.with_columns(pl.Series("segment_id", labels))
    # rank clusters by avg price so labels are stable & interpretable
    order = (
        profile.group_by("segment_id")
        .agg(pl.col("avg_price").mean())
        .sort("avg_price")
        .with_row_index("rank")
        .select("segment_id", "rank")
    )
    profile = (
        profile.join(order, on="segment_id")
        .with_columns(
            pl.col("rank")
            .map_elements(
                lambda r: SEGMENT_LABELS[min(r, len(SEGMENT_LABELS) - 1)], return_dtype=pl.Utf8
            )
            .alias("segment_name")
        )
        .drop("rank")
    )

    return profile.join(
        products.select("product_id", "product_name", "category", "brand"), on="product_id"
    )
