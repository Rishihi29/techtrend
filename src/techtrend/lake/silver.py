"""Bronze -> Silver conformance.

Silver holds business-conformed entities at an explicitly declared grain:

* ``products``            -- one row per product (current attributes)
* ``price_observations``  -- one row per product per observed calendar day

Surrogate ``time_id`` indirection from the source system is resolved here;
downstream consumers only ever see real dates.
"""

from __future__ import annotations

import polars as pl

from techtrend.common.lake_io import read_parquet, write_parquet
from techtrend.common.logging import get_logger
from techtrend.lake.conform import conform_products

log = get_logger(__name__)


def build(load_date: str) -> dict[str, int]:
    products = read_parquet("bronze", "products", f"dt={load_date}", "products.parquet")
    time_dim = read_parquet("bronze", "time", f"dt={load_date}", "time.parquet")
    facts = read_parquet("bronze", "price_facts", f"dt={load_date}", "facts.parquet")

    products_silver = conform_products(products)
    write_parquet(products_silver, "silver", "products", "products.parquet")

    observations = (
        facts.join(time_dim.select("time_id", "full_date"), on="time_id", how="inner")
        .rename({"full_date": "observed_date"})
        # enforce grain: one observation per product-day (latest fact wins)
        .sort("fact_id")
        .unique(subset=["product_id", "observed_date"], keep="last")
        .select(
            "product_id",
            "observed_date",
            "price",
            "original_price",
            "discount_percentage",
            "availability",
            "stock_level",
            "rating",
            "review_count",
            "sales_velocity",
            "is_trending",
        )
        .sort(["product_id", "observed_date"])
    )

    # Hive-style monthly partitions: silver/price_observations/month=YYYY-MM/
    observations = observations.with_columns(
        pl.col("observed_date").dt.strftime("%Y-%m").alias("month")
    )
    for (month,), part in observations.partition_by("month", as_dict=True).items():
        write_parquet(
            part.drop("month"),
            "silver",
            "price_observations",
            f"month={month}",
            "observations.parquet",
        )

    counts = {"products": products_silver.height, "price_observations": observations.height}
    log.info("silver_complete", load_date=load_date, **counts)
    return counts
