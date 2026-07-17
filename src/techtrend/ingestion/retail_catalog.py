"""Retail catalog batch connector.

Lands the TechTrend retail extract (product catalog + daily price/stock
observations) into the raw layer. Two modes:

* **sample** -- the bundled slice in ``data/samples`` (default; keyless,
  runs anywhere including CI),
* **kaggle** -- a full dataset pulled via the Kaggle CLI when
  ``KAGGLE_USERNAME``/``KAGGLE_KEY`` are configured.

Either way the landing contract is identical: immutable partition,
manifest, schema fingerprint.
"""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from techtrend.common.logging import get_logger
from techtrend.ingestion.base import LandingManifest, land_raw

log = get_logger(__name__)

SOURCE = "retail_catalog"
DATASETS = ("products", "facts", "time")


def extract(
    sample_dir: str | Path = "data/samples",
    load_date: str | None = None,
    kaggle_dataset: str | None = None,
) -> list[LandingManifest]:
    """Land all catalog datasets raw; returns one manifest per dataset."""
    load_date = load_date or datetime.now(UTC).strftime("%Y-%m-%d")
    src_dir = Path(sample_dir)

    if kaggle_dataset:
        src_dir = _download_kaggle(kaggle_dataset)

    manifests: list[LandingManifest] = []
    for dataset in DATASETS:
        csv_path = src_dir / f"kaggle_{dataset}.csv"
        if not csv_path.exists():
            raise FileNotFoundError(
                f"expected {csv_path}; run `make demo` or configure a Kaggle dataset"
            )
        df = pl.read_csv(csv_path, infer_schema_length=10_000)
        if dataset == "time" and kaggle_dataset is None:
            # Demo-fixture rebase: shift the bundled sample so its history
            # ends yesterday. Freshness SLOs, forecasts, and "last 7 days"
            # insights then behave exactly as they would in production.
            # Real Kaggle ingestions are never re-dated.
            df = _rebase_dates(df)
        manifests.append(
            land_raw(
                df,
                source=SOURCE,
                dataset=dataset,
                load_date=load_date,
                params={"origin": str(csv_path), "mode": "batch"},
            )
        )
    return manifests


def _download_kaggle(dataset: str) -> Path:
    """Fetch a dataset with the Kaggle CLI (credentials from environment)."""
    target = Path("data/kaggle") / dataset.replace("/", "__")
    target.mkdir(parents=True, exist_ok=True)
    log.info("kaggle_download_start", dataset=dataset)
    subprocess.run(
        ["kaggle", "datasets", "download", "-d", dataset, "-p", str(target), "--unzip"],
        check=True,
    )
    return target


def _rebase_dates(time_df: pl.DataFrame) -> pl.DataFrame:
    from datetime import UTC, datetime, timedelta

    dates = time_df.with_columns(
        pl.col("full_date").cast(pl.Utf8).str.slice(0, 10).str.to_date("%Y-%m-%d")
    )
    max_date = dates.select(pl.col("full_date").max()).item()
    shift = (datetime.now(UTC).date() - timedelta(days=1)) - max_date
    log.info("sample_dates_rebased", shift_days=shift.days)
    return dates.with_columns(
        (pl.col("full_date") + pl.duration(days=shift.days)).dt.strftime("%Y-%m-%d")
    )
