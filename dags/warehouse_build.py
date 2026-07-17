"""Warehouse DAG: dbt snapshot (SCD2) + dbt build, triggered by silver."""

from datetime import datetime, timedelta

from airflow.datasets import Dataset
from airflow.decorators import dag, task

SILVER = Dataset("lake://silver/price_observations")
MARTS = Dataset("warehouse://analytics/marts")

DEFAULTS = {"retries": 2, "retry_delay": timedelta(minutes=3), "owner": "analytics-eng"}


@dag(
    dag_id="warehouse_build",
    schedule=[SILVER],
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args=DEFAULTS,
    tags=["dbt", "warehouse"],
)
def warehouse_build():
    @task
    def snapshot() -> None:
        from techtrend.pipeline import run_dbt

        run_dbt("snapshot")

    @task(outlets=[MARTS])
    def build() -> None:
        from techtrend.pipeline import run_dbt

        run_dbt("build")

    snapshot() >> build()


warehouse_build()
