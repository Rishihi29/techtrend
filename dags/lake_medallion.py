"""Medallion DAG: raw -> bronze -> silver -> gold + data-quality gate.

Triggered by the raw Dataset. The DQ score gates the run: below the SLO
the pipeline fails loudly instead of publishing bad data downstream.
"""

from datetime import datetime, timedelta

from airflow.datasets import Dataset
from airflow.decorators import dag, task

RAW = Dataset("lake://raw/retail")
SILVER = Dataset("lake://silver/price_observations")

DQ_SLO = 0.90

DEFAULTS = {"retries": 2, "retry_delay": timedelta(minutes=3), "owner": "data-platform"}


@dag(
    dag_id="lake_medallion",
    schedule=[RAW],
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args=DEFAULTS,
    tags=["lake", "medallion", "quality"],
)
def lake_medallion():
    @task
    def to_bronze(ds: str | None = None) -> dict:
        from techtrend.lake import bronze

        return bronze.build(ds)

    @task(outlets=[SILVER])
    def to_silver(counts: dict, ds: str | None = None) -> dict:
        from techtrend.lake import silver

        silver.build(ds)
        return counts

    @task
    def to_gold(counts: dict) -> dict:
        from techtrend.lake import gold

        gold.build()
        return counts

    @task
    def quality_gate(counts: dict) -> None:
        from techtrend.lake import gold
        from techtrend.quality import score

        report = score.compute(gold.load_observations(), rejected_rows=counts["rejected"])
        score.persist(report)
        if report.composite_score < DQ_SLO:
            raise ValueError(
                f"DQ score {report.composite_score} below SLO {DQ_SLO}; halting publish"
            )

    quality_gate(to_gold(to_silver(to_bronze())))


lake_medallion()
