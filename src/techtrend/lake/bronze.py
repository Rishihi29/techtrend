"""Raw -> Bronze promotion.

Bronze is *typed, deduplicated, contract-validated* data -- structurally
trustworthy but not yet business-conformed. Rows failing their contract
are quarantined (never silently dropped) and counted for the DQ score.
"""

from __future__ import annotations

import polars as pl

from techtrend.common.lake_io import read_parquet, write_parquet
from techtrend.common.logging import get_logger
from techtrend.quality.schemas import (
    PriceObservationContract,
    ProductContract,
    validate_split,
)

log = get_logger(__name__)


def _quarantine(rejected: pl.DataFrame, source: str, dataset: str, load_date: str) -> None:
    if rejected.height:
        write_parquet(
            rejected.with_columns(pl.lit(load_date).alias("_load_date")),
            "raw",
            "_rejected",
            source,
            f"dt={load_date}",
            f"{dataset}.parquet",
        )
        log.warning("rows_quarantined", source=source, dataset=dataset, rows=rejected.height)


def build(load_date: str) -> dict[str, int]:
    """Promote all retail_catalog datasets for one load date. Idempotent."""
    rejected_total = 0

    products = read_parquet("raw", "retail_catalog", f"dt={load_date}", "products.parquet")
    products = products.unique(subset=["product_id"], keep="last")
    products_ok, products_bad = validate_split(products, ProductContract)
    _quarantine(products_bad, "retail_catalog", "products", load_date)
    rejected_total += products_bad.height
    write_parquet(products_ok, "bronze", "products", f"dt={load_date}", "products.parquet")

    time_dim = read_parquet("raw", "retail_catalog", f"dt={load_date}", "time.parquet")
    time_dim = time_dim.unique(subset=["time_id"], keep="last").with_columns(
        # sources ship dates as either YYYY-MM-DD or full timestamps;
        # normalise defensively rather than trusting the extract
        pl.col("full_date").cast(pl.Utf8).str.slice(0, 10).str.to_date("%Y-%m-%d")
    )
    write_parquet(time_dim, "bronze", "time", f"dt={load_date}", "time.parquet")

    facts = read_parquet("raw", "retail_catalog", f"dt={load_date}", "facts.parquet")
    facts = facts.unique(subset=["fact_id"], keep="last")
    facts_ok, facts_bad = validate_split(facts, PriceObservationContract)
    _quarantine(facts_bad, "retail_catalog", "facts", load_date)
    rejected_total += facts_bad.height
    write_parquet(facts_ok, "bronze", "price_facts", f"dt={load_date}", "facts.parquet")

    counts = {
        "products": products_ok.height,
        "time": time_dim.height,
        "price_facts": facts_ok.height,
        "rejected": rejected_total,
    }
    log.info("bronze_complete", load_date=load_date, **counts)
    return counts
