"""End-to-end pipeline composition.

Airflow DAGs and the local CLI both call these functions -- orchestration
code contains zero business logic, and business logic knows nothing about
its orchestrator. That separation is what makes the platform portable
between `make demo`, Airflow, and any future scheduler.
"""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path

from techtrend.common.logging import configure_logging, get_logger
from techtrend.config.settings import get_settings
from techtrend.ingestion import open_prices, retail_catalog
from techtrend.lake import bronze, gold, silver
from techtrend.ml import anomaly, forecasting, recommend
from techtrend.quality import score as quality_score

log = get_logger(__name__)


def today() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def run_ingestion(load_date: str) -> None:
    retail_catalog.extract(load_date=load_date)
    open_prices.extract(load_date=load_date)


def run_lake(load_date: str) -> None:
    bronze_counts = bronze.build(load_date)
    silver.build(load_date)
    gold.build()
    obs = gold.load_observations()
    report = quality_score.compute(obs, rejected_rows=bronze_counts["rejected"])
    quality_score.persist(report)


def run_ml() -> None:
    forecasting.train_and_forecast(target="price")
    forecasting.train_and_forecast(target="sales_velocity")
    anomaly.detect()
    recommend.build()


def run_dbt(*commands: str) -> None:
    """Invoke dbt against the configured target from the repo root."""
    settings = get_settings()
    project_dir = Path("dbt/techtrend_dw")
    base = [
        "dbt",
        "--no-use-colors",
        *commands,
        "--project-dir",
        str(project_dir),
        "--profiles-dir",
        str(project_dir / "profiles"),
        "--vars",
        f"{{lake_root: {settings.lake_root}}}",
    ]
    log.info("dbt_invoke", command=" ".join(commands))
    subprocess.run(base, check=True)


def run_all(load_date: str | None = None) -> None:
    """The full platform run: ingest -> medallion -> ML -> warehouse."""
    configure_logging()
    load_date = load_date or today()
    settings = get_settings()
    Path(settings.duckdb_path).parent.mkdir(parents=True, exist_ok=True)

    log.info("pipeline_start", load_date=load_date)
    run_ingestion(load_date)
    run_lake(load_date)
    run_ml()
    run_dbt("snapshot")
    run_dbt("build")
    log.info("pipeline_complete", load_date=load_date)


if __name__ == "__main__":
    run_all()
