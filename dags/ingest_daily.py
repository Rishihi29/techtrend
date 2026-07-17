"""Daily ingestion DAG: land source deltas in the raw layer.

Publishes the `raw` Airflow Dataset so downstream pipelines are
data-aware-scheduled rather than clock-coupled.
"""

from datetime import datetime, timedelta

from airflow.datasets import Dataset
from airflow.decorators import dag, task

RAW = Dataset("lake://raw/retail")

DEFAULTS = {
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "retry_exponential_backoff": True,
    "owner": "data-platform",
}


@dag(
    dag_id="ingest_daily",
    schedule="0 2 * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args=DEFAULTS,
    tags=["ingestion", "raw"],
)
def ingest_daily():
    @task(outlets=[RAW])
    def extract_sources(ds: str | None = None) -> None:
        from techtrend.ingestion import open_prices, retail_catalog

        retail_catalog.extract(load_date=ds)
        open_prices.extract(load_date=ds)

    extract_sources()


ingest_daily()
